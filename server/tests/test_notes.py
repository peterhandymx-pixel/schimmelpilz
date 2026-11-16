from fastapi.testclient import TestClient

from server import app as api
from server.tests import test_inbox


class NotesTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_note_with_follow_up_activity_search_and_isolation(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client, 'notes@example.invalid')
            case = client.post('/api/cases', json={'title': 'Mietminderung', 'description': 'Synthetische Akte für Notizen.'}).json()
            notes = client.post(f"/api/cases/{case['id']}/notes", json={'kind': 'call_in', 'person': 'Frau Weber', 'happened_at': '2026-11-16T10:15', 'minutes': 12,
                                                                        'note': 'Mandantin meldet Schimmel im Bad, schickt Fotos.', 'follow_up_on': '2026-11-23'}).json()
            self.assertEqual(notes[0]['kind_label'], 'Anruf eingehend')
            self.assertEqual(notes[0]['happened_at'], '2026-11-16T10:15')
            full = client.get(f"/api/cases/{case['id']}").json()
            self.assertEqual([(task['kind'], task['due_on']) for task in full['tasks']], [('resubmission', '2026-11-23')])
            self.assertIn('Wiedervorlage: Anruf eingehend mit Frau Weber', full['tasks'][0]['title'])
            self.assertIn('note_recorded', [entry['action'] for entry in full['activities']])
            hits = client.post('/api/search', json={'q': 'schimmel fotos'}).json()['groups'][0]['hits']
            self.assertIn(('note', 'notes'), [(hit['kind'], hit['tab']) for hit in hits])
            self.assertEqual(client.post(f"/api/cases/{case['id']}/notes", json={'happened_at': '2026-11-16T10:15', 'note': 'x'}).status_code, 422)
            self.login(other, 'notes-other@example.invalid')
            self.assertEqual(other.get(f"/api/cases/{case['id']}/notes").status_code, 404)
            self.assertEqual(other.delete(f"/api/cases/{case['id']}/notes/{notes[0]['id']}").status_code, 404)
            self.assertEqual(client.delete(f"/api/cases/{case['id']}/notes/{notes[0]['id']}").status_code, 204)
            self.assertEqual(client.get(f"/api/cases/{case['id']}/notes").json(), [])
