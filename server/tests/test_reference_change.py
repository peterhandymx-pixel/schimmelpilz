from fastapi.testclient import TestClient

from server import app as api
from server.tests import test_inbox


class ReferenceChangeTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_manual_and_automatic_reference_with_history(self):
        with TestClient(api.app) as client:
            self.login(client, 'reference@example.invalid')
            case_id, other_id = self.case(client), self.case(client)
            original = client.get(f'/api/cases/{case_id}').json()['reference']
            changed = client.put(f'/api/cases/{case_id}/reference', json={'mode': 'existing', 'reference': ' 123/26 '})
            self.assertEqual(changed.status_code, 200, changed.text)
            self.assertEqual(changed.json()['reference'], '123/26')
            history = [entry for entry in changed.json()['activities'] if entry['action'] == 'reference_changed']
            self.assertEqual(history[0]['detail'], f'{original} → 123/26')
            # Another case may not take the same number (case-insensitive); the same case may keep it.
            self.assertEqual(client.put(f'/api/cases/{other_id}/reference', json={'mode': 'existing', 'reference': '123/26'}).status_code, 409)
            self.assertEqual(client.put(f'/api/cases/{case_id}/reference', json={'mode': 'existing', 'reference': '123/26'}).status_code, 200)
            self.assertEqual(client.put(f'/api/cases/{case_id}/reference', json={'mode': 'existing'}).status_code, 422)
            auto = client.put(f'/api/cases/{case_id}/reference', json={'mode': 'generate'}).json()['reference']
            self.assertTrue(auto.startswith('SCH-') and auto != original)
            self.assertEqual(client.put('/api/cases/does-not-exist/reference', json={'mode': 'generate'}).status_code, 404)
