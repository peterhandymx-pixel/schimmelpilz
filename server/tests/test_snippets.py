from fastapi.testclient import TestClient
from server import app as api
from server.tests import test_inbox


class SnippetAndInsurerTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_text_blocks_are_private_to_the_office(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client); self.login(other, 'snippet-other@example.invalid')
            items = client.post('/api/snippets', json={'title': 'Schlussformel', 'category': 'Klage', 'body': 'Es wird gebeten, {gegner} die Kosten aufzuerlegen.'}).json()
            self.assertEqual([s['title'] for s in items], ['Schlussformel'])
            self.assertEqual(client.post('/api/snippets', json={'title': 'x', 'body': ''}).status_code, 422)
            snippet_id = items[0]['id']
            self.assertEqual(other.get('/api/snippets').json(), [])
            self.assertEqual(other.put(f'/api/snippets/{snippet_id}', json={'title': 'Fremd', 'body': 'Fremder Text'}).status_code, 404)
            updated = client.put(f'/api/snippets/{snippet_id}', json={'title': 'Schlussformel Klage', 'category': 'Klage', 'body': 'Neu'}).json()
            self.assertEqual(updated[0]['title'], 'Schlussformel Klage')
            self.assertEqual(client.delete(f'/api/snippets/{snippet_id}').status_code, 204)
            self.assertEqual(client.get('/api/snippets').json(), [])

    def test_legal_expenses_insurer_is_stored_with_the_case(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            case = client.get(f'/api/cases/{case_id}').json()
            details = {**case['details'], 'insurer_name': 'ARAG SE, ARAG Platz 1, 40472 Düsseldorf', 'insurer_policy': ' 123-456 ', 'insurer_claim': 'S-99'}
            saved = client.put(f'/api/cases/{case_id}', json={'title': case['title'], 'description': case['description'], 'language': 'de', 'details': details}).json()
            self.assertEqual((saved['details']['insurer_policy'], saved['details']['insurer_claim']), ('123-456', 'S-99'))
