import struct
from pathlib import Path

from fastapi.testclient import TestClient

from server import app as api
from server.tests import test_inbox


def wav(seconds=2.0, rate=16000):
    frames = int(seconds * rate)
    data = b''.join(struct.pack('<h', (index % 200) * 100 - 10000) for index in range(frames))
    return b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(data)) + data


class DictationTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def record(self, client, case_id, priority='urgent', seconds=2.0):
        return client.post(f'/api/cases/{case_id}/dictations', data={'priority': priority, 'note': 'Schriftsatz ans Gericht'}, files={'file': ('diktat.wav', wav(seconds), 'audio/wav')})

    def test_record_take_complete_with_case_history(self):
        with TestClient(api.app) as client:
            self.login(client, 'dictation@example.invalid')
            case_id = self.case(client)
            created = self.record(client, case_id)
            self.assertEqual(created.status_code, 201, created.text)
            item = created.json()
            self.assertEqual((item['status'], item['priority'], item['duration_ms']), ('open', 'urgent', 2000))
            self.assertNotIn('stored_name', item)
            audio = client.get(f"/api/dictations/{item['id']}/audio")
            self.assertEqual(audio.status_code, 200)
            self.assertEqual(audio.content[:4], b'RIFF')
            pool = client.get('/api/dictations').json()
            self.assertEqual([entry['id'] for entry in pool['items']], [item['id']])
            self.assertEqual(pool['authors'][0]['author_name'], 'Synthetic Person')
            self.assertEqual(client.get('/api/dictations', params={'author_id': 'someone-else'}).json()['items'], [])
            # Stale versions are refused; taking twice is refused.
            self.assertEqual(client.post(f"/api/dictations/{item['id']}/take", json={'expected_version': 9}).status_code, 409)
            taken = client.post(f"/api/dictations/{item['id']}/take", json={'expected_version': 1}).json()
            self.assertEqual((taken['status'], taken['assignee_name']), ('in_progress', 'Synthetic Person'))
            self.assertEqual(client.post(f"/api/dictations/{item['id']}/take", json={'expected_version': 2}).status_code, 409)
            self.assertEqual(client.delete(f"/api/dictations/{item['id']}").status_code, 409)
            released = client.post(f"/api/dictations/{item['id']}/release", json={'expected_version': 2}).json()
            self.assertEqual(released['status'], 'open')
            client.post(f"/api/dictations/{item['id']}/take", json={'expected_version': 3})
            done = client.post(f"/api/dictations/{item['id']}/complete", json={'expected_version': 4, 'note': 'zur Unterschrift vorgelegt'}).json()
            self.assertEqual((done['status'], done['done_by_name'], done['done_note']), ('done', 'Synthetic Person', 'zur Unterschrift vorgelegt'))
            self.assertTrue(done['done_at'])
            self.assertEqual(client.get('/api/dictations').json()['items'], [])
            self.assertEqual(len(client.get('/api/dictations', params={'status': 'done'}).json()['items']), 1)
            history = {entry['action']: entry['detail'] for entry in client.get(f'/api/cases/{case_id}').json()['activities']}
            for action in ('dictation_created', 'dictation_taken', 'dictation_released', 'dictation_done'):
                self.assertIn(action, history)
            self.assertIn('geschrieben von Synthetic Person', history['dictation_done'])
            self.assertIn('Priorität eilig', history['dictation_created'])

    def test_rejects_non_wav_short_and_foreign_access_and_cleans_up_on_withdraw(self):
        with TestClient(api.app) as client:
            self.login(client, 'dictation-owner@example.invalid')
            case_id = self.case(client)
            bad = client.post(f'/api/cases/{case_id}/dictations', files={'file': ('x.wav', b'not audio at all, just text' * 4, 'audio/wav')})
            self.assertEqual(bad.status_code, 415)
            self.assertEqual(self.record(client, case_id, seconds=0.2).status_code, 422)
            self.assertEqual(self.record(client, case_id, priority='whenever').status_code, 422)
            item = self.record(client, case_id).json()
            stored = list(Path(api.UPLOAD_DIR).glob('dictation-*.wav'))
            self.assertEqual(len(stored), 1)
            self.login(client, 'dictation-stranger@example.invalid')
            self.assertEqual(client.get(f"/api/dictations/{item['id']}/audio").status_code, 404)
            self.assertEqual(client.post(f"/api/dictations/{item['id']}/take", json={'expected_version': 1}).status_code, 404)
            self.assertEqual(self.record(client, case_id).status_code, 404)
            self.assertEqual(client.get('/api/dictations').json()['items'], [])
            self.login(client, 'dictation-owner@example.invalid')
            self.assertEqual(client.delete(f"/api/dictations/{item['id']}").status_code, 204)
            self.assertFalse(stored[0].exists())
            self.assertIn('dictation_deleted', [entry['action'] for entry in client.get(f'/api/cases/{case_id}').json()['activities']])

    def test_team_member_takes_lawyers_dictation_only_in_granted_cases(self):
        with TestClient(api.app) as owner, TestClient(api.app) as member:
            self.login(owner, 'kanzlei@example.invalid'); self.login(member, 'sekretariat@example.invalid')
            me = owner.get('/api/auth/me').json(); person = member.get('/api/auth/me').json()
            first = self.case(owner); second = self.case(owner)
            granted = self.record(owner, first).json(); hidden = self.record(owner, second, priority='normal').json()
            token = owner.post('/api/team/invites', json={'email': person['email'], 'role': 'editor', 'case_ids': [first]}).json()['token']
            member.post('/api/team/join', json={'token': token}); member.post('/api/team/switch', json={'owner_id': me['id']})
            pool = member.get('/api/dictations').json()
            self.assertEqual([item['id'] for item in pool['items']], [granted['id']])
            self.assertEqual(member.get(f"/api/dictations/{hidden['id']}/audio").status_code, 404)
            taken = member.post(f"/api/dictations/{granted['id']}/take", json={'expected_version': 1}).json()
            self.assertEqual(taken['assignee_id'], person['id'])
            self.assertNotEqual(taken['author_id'], taken['assignee_id'])
            # The lawyer cannot withdraw a dictation that is already being typed.
            self.assertEqual(owner.delete(f"/api/dictations/{granted['id']}").status_code, 409)
            self.assertEqual(member.post(f"/api/dictations/{granted['id']}/complete", json={'expected_version': 2}).json()['status'], 'done')
            # Deleting a case removes its dictation audio from disk.
            files = {path.name for path in Path(api.UPLOAD_DIR).glob('dictation-*.wav')}
            self.assertEqual(len(files), 2)
            reference = owner.get(f'/api/cases/{second}').json()['reference']
            deleted = owner.delete(f'/api/cases/{second}', params={'confirm': reference})
            self.assertIn(deleted.status_code, (200, 204), deleted.text)
            self.assertEqual(len(list(Path(api.UPLOAD_DIR).glob('dictation-*.wav'))), 1)
