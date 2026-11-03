import email
import hashlib
import os
from email import policy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app as api
from server.tests import test_inbox


class DraftSendTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def setUp(self):
        super().setUp()
        api.SEND_LIMIT.clear()
        self.outbox = Path(self.temp.name) / 'outbox'

    def test_send_requires_mail_confirmation_and_current_version_then_records_evidence(self):
        with patch.dict(os.environ, {'MAIL_OUTBOX_DIR': '', 'SMTP_HOST': '', 'SMTP_FROM': ''}), TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            draft = client.post(f'/api/cases/{case_id}/drafts', json={'body': 'Sehr geehrte Damen und Herren,\n\nSynthetischer Text.', 'recipient': 'Gegner GmbH'}).json()
            send = {'to': 'opponent@example.invalid', 'subject': 'Ihr Zeichen 1', 'message': 'Anbei.', 'attachment': 'pdf', 'expected_version': 1, 'confirmed': True}
            self.assertEqual(client.post(f"/api/cases/{case_id}/drafts/{draft['id']}/send", json=send).json()['detail'], 'mail_not_configured')
        with patch.dict(os.environ, {'MAIL_OUTBOX_DIR': str(self.outbox)}), TestClient(api.app) as client:
            self.login(client)
            url = f"/api/cases/{case_id}/drafts/{draft['id']}/send"
            self.assertEqual(client.post(url, json={**send, 'confirmed': False}).status_code, 422)
            self.assertEqual(client.post(url, json={**send, 'to': 'a@example.invalid, b@example.invalid'}).status_code, 422)
            self.assertEqual(client.post(url, json={**send, 'subject': 'x\r\nBcc: evil@example.invalid'}).status_code, 422)
            self.assertEqual(client.post(url, json={**send, 'expected_version': 2}).status_code, 409)
            sent = client.post(url, json=send)
            self.assertEqual(sent.status_code, 200, sent.text)
            docx = client.post(url, json={**send, 'attachment': 'docx'}).json()
            self.assertTrue(docx['attachment'].endswith('-v1.docx'))
            messages = [email.message_from_bytes(path.read_bytes(), policy=policy.default) for path in self.outbox.glob('*.eml')]
            self.assertEqual(len(messages), 2)
            pdf_message = next(m for m in messages if any(part.get_filename().endswith('.pdf') for part in m.iter_attachments()))
            attachment = next(pdf_message.iter_attachments())
            self.assertEqual((pdf_message['To'], pdf_message['Reply-To'], pdf_message['Subject']), ('opponent@example.invalid', 'inbox-test@example.invalid', 'Ihr Zeichen 1'))
            self.assertTrue(attachment.get_content().startswith(b'%PDF'))
            with api.db() as connection:
                event = connection.execute("SELECT * FROM draft_review_events WHERE action='sent' ORDER BY created_at LIMIT 1").fetchone()
            import json
            evidence = json.loads(event['evidence'])
            self.assertEqual(evidence['attachment_sha256'], hashlib.sha256(attachment.get_content()).hexdigest())
            self.assertEqual(evidence['scope'], 'email_delivery_not_formal_filing')
            self.assertIn('draft_sent', [item['action'] for item in client.get('/api/cases/' + case_id).json()['activities']])
