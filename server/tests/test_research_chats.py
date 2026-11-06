import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app as api
from server.tests import test_inbox

ANSWER = {'answer': '### Kurze Antwort\nJa.', 'input_tokens': 1, 'output_tokens': 1, 'truncated': False}


class ResearchChatTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def ask(self, client, case_id, question, thread_id=None):
        body = {'request_id': str(uuid.uuid4()), 'question': question}
        if thread_id:
            body['thread_id'] = thread_id
        return client.post(f'/api/cases/{case_id}/research', json=body)

    def test_chats_keep_their_own_history(self):
        with TestClient(api.app) as client, patch.object(api, 'prepare_messages', wraps=api.prepare_messages) as prepared, patch.object(api, 'generate_answer', return_value=ANSWER):
            self.login(client, 'chats@example.invalid')
            case_id = self.case(client)
            first = self.ask(client, case_id, 'Erste Frage zur Kaution?').json()
            self.assertEqual(first['thread_id'], first['id'])
            follow = self.ask(client, case_id, 'Und die Zinsen darauf?', first['thread_id']).json()
            self.assertEqual(follow['thread_id'], first['thread_id'])
            other = self.ask(client, case_id, 'Ganz anderes Thema: Kündigung?').json()
            self.assertNotEqual(other['thread_id'], first['thread_id'])
            # The new chat starts without the earlier questions as context.
            self.assertNotIn('Erste Frage zur Kaution?', str(prepared.call_args))
            self.ask(client, case_id, 'Noch eine Nachfrage zur Kaution?', first['thread_id'])
            self.assertIn('Und die Zinsen darauf?', str(prepared.call_args))
            self.assertNotIn('Kündigung', str(prepared.call_args))
            self.assertEqual(self.ask(client, case_id, 'Fremder Chat?', str(uuid.uuid4())).status_code, 404)
            runs = client.get(f'/api/cases/{case_id}/research').json()
            self.assertEqual(sorted({run['thread_id'] for run in runs}), sorted({first['thread_id'], other['thread_id']}))
