import json

from fastapi.testclient import TestClient

from server import app as api
from server.tests import test_inbox


class DeletionTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def files(self):
        return sorted(path.name for path in api.UPLOAD_DIR.iterdir())

    def test_case_deletion_needs_reference_removes_records_and_returns_inbox_originals(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id, other = self.case(client), self.case(client)
            reference = client.get('/api/cases/' + case_id).json()['reference']
            uploaded = client.post(f'/api/cases/{case_id}/documents', files={'file': ('Own.pdf', test_inbox.synthetic_pdf(), 'application/pdf')}).json()
            entry = self.upload(client)
            client.post(f"/api/inbox/{entry['id']}/assign", json={'case_id': case_id, 'expected_version': 1})
            client.post(f'/api/cases/{case_id}/drafts', json={'body': 'Synthetic draft to delete'})
            client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Synthetic task'})
            contact = client.post('/api/contacts', json={'name': 'Synthetic Contact', 'case_links': [{'case_id': case_id, 'role': 'client'}]}).json()
            self.assertEqual(len(self.files()), 2)

            self.assertEqual(client.delete(f'/api/cases/{case_id}').status_code, 422)
            self.assertEqual(client.delete(f'/api/cases/{case_id}?confirm=WRONG').status_code, 422)
            self.assertEqual(client.delete(f'/api/cases/{case_id}?confirm={reference.lower()}').status_code, 204)

            self.assertEqual(client.get('/api/cases/' + case_id).status_code, 404)
            self.assertEqual([item['id'] for item in client.get('/api/cases').json()], [other])
            with api.db() as connection:
                for table in ('documents', 'drafts', 'tasks', 'activities', 'contact_cases'):
                    self.assertEqual(connection.execute(f'SELECT COUNT(*) FROM {table} WHERE case_id=?', (case_id,)).fetchone()[0], 0, table)
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM draft_versions').fetchone()[0], 0)
            # The case-only upload is gone from disk; the inbox original is pending again and kept.
            self.assertNotIn(uploaded['id'] + '.pdf', self.files())
            self.assertEqual(self.files(), [entry['id'] + '.pdf'])
            pending = client.get('/api/inbox').json()[0]
            self.assertIsNone(pending['case_id'])
            self.assertEqual(client.get('/api/contacts').json()[0]['id'], contact['id'])

    def test_document_draft_task_contact_and_inbox_deletion(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            document = client.post(f'/api/cases/{case_id}/documents', files={'file': ('Own.pdf', test_inbox.synthetic_pdf(), 'application/pdf')}).json()
            client.post(f"/api/cases/{case_id}/documents/{document['id']}/extract")
            self.assertEqual(client.delete(f"/api/cases/{case_id}/documents/{document['id']}").status_code, 204)
            self.assertEqual(self.files(), [])
            self.assertEqual(client.delete(f"/api/cases/{case_id}/documents/{document['id']}").status_code, 404)
            with api.db() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM document_pages').fetchone()[0], 0)

            entry = self.upload(client)
            client.post(f"/api/inbox/{entry['id']}/assign", json={'case_id': case_id, 'expected_version': 1})
            self.assertEqual(client.delete(f"/api/inbox/{entry['id']}?expected_version=2").status_code, 409)
            # Removing the case copy keeps the inbox original and makes the entry deletable.
            self.assertEqual(client.delete(f"/api/cases/{case_id}/documents/{entry['id']}").status_code, 204)
            self.assertEqual(self.files(), [entry['id'] + '.pdf'])
            self.assertEqual(client.delete(f"/api/inbox/{entry['id']}?expected_version=2").status_code, 409)
            self.assertEqual(client.delete(f"/api/inbox/{entry['id']}?expected_version=3").status_code, 204)
            self.assertEqual(self.files(), [])

            draft = client.post(f'/api/cases/{case_id}/drafts', json={'body': 'Synthetic draft'}).json()
            self.assertEqual(client.delete(f"/api/cases/{case_id}/drafts/{draft['id']}?expected_version=2").status_code, 409)
            self.assertEqual(client.delete(f"/api/cases/{case_id}/drafts/{draft['id']}?expected_version=1").status_code, 204)
            task = client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Synthetic task'}).json()['tasks'][0]
            self.assertEqual(client.delete(f"/api/cases/{case_id}/tasks/{task['id']}").status_code, 204)
            contact = client.post('/api/contacts', json={'name': 'Synthetic Contact'}).json()
            self.assertEqual(client.delete(f"/api/contacts/{contact['id']}?expected_version=9").status_code, 409)
            self.assertEqual(client.delete(f"/api/contacts/{contact['id']}?expected_version={contact['version']}").status_code, 204)
            current = client.get('/api/cases/' + case_id).json()
            self.assertEqual((current['documents'], current['drafts'], current['tasks']), ([], [], []))
            self.assertTrue({'document_deleted', 'draft_deleted', 'task_deleted'} <= {item['action'] for item in current['activities']})

    def test_team_members_cannot_delete_and_expired_trial_still_can(self):
        with TestClient(api.app) as owner, TestClient(api.app) as member:
            self.login(owner); self.login(member, 'editor@example.invalid')
            case_id = self.case(owner)
            person = member.get('/api/auth/me').json()
            me = owner.get('/api/auth/me').json()
            token = owner.post('/api/team/invites', json={'email': person['email'], 'role': 'editor', 'case_ids': None}).json()['token']
            member.post('/api/team/join', json={'token': token})
            member.post('/api/team/switch', json={'owner_id': me['id']})
            task = owner.post(f'/api/cases/{case_id}/tasks', json={'title': 'Synthetic task'}).json()['tasks'][0]
            self.assertEqual(member.delete(f"/api/cases/{case_id}/tasks/{task['id']}").json()['detail'], 'workspace_owner_required_for_deletion')
            reference = owner.get('/api/cases/' + case_id).json()['reference']
            self.assertEqual(member.delete(f'/api/cases/{case_id}?confirm={reference}').status_code, 403)
            with api.db() as connection:
                connection.execute("UPDATE subscriptions SET status='trial',trial_end='2020-01-01T00:00:00+00:00' WHERE user_id=?", (me['id'],))
            self.assertEqual(owner.post(f'/api/cases/{case_id}/tasks', json={'title': 'Blocked after trial'}).status_code, 402)
            self.assertEqual(owner.delete(f"/api/cases/{case_id}/tasks/{task['id']}").status_code, 204)
            self.assertEqual(owner.delete(f'/api/cases/{case_id}?confirm={reference}').status_code, 204)
            with api.db() as connection:
                self.assertEqual(json.loads(connection.execute('SELECT case_ids FROM team_members').fetchone()[0] or 'null'), None)
