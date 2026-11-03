import imaplib
import os
from email.message import EmailMessage
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app as api, mailbox
from server.tests import test_inbox


def message(message_id, attachments, subject='Rechnung 42'):
    item = EmailMessage()
    item['From'], item['To'], item['Subject'] = 'Vermieter GmbH <rechnung@example.invalid>', 'kanzlei@example.invalid', subject
    item['Date'], item['Message-ID'] = 'Tue, 13 Oct 2026 09:30:00 +0200', message_id
    item.set_content('Anbei die Unterlagen.')
    for name, content in attachments:
        item.add_attachment(content, maintype='application', subtype='octet-stream', filename=name)
    return bytes(item)


class FakeImap:
    messages = {}
    logins = []

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.host = host

    def login(self, username, password):
        if password != 'mailbox-secret':
            raise imaplib.IMAP4.error('auth failed')
        FakeImap.logins.append((username, password))

    def select(self, folder, readonly=False):
        assert readonly, 'mailbox must be opened read-only'
        return ('OK', [b'2']) if folder == '"INBOX"' else ('NO', [b''])

    def uid(self, command, uid, query):
        if command == 'SEARCH':
            return 'OK', [b' '.join(self.messages)]
        if query == '(RFC822.SIZE)':
            return 'OK', [f'1 (UID {uid.decode()} RFC822.SIZE {len(self.messages[uid])})'.encode()]
        assert query == '(BODY.PEEK[])', 'messages must stay unread'
        return 'OK', [(b'1 (UID BODY[] {1}', self.messages[uid]), b')']

    def logout(self):
        pass


class MailboxTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def setUp(self):
        super().setUp()
        FakeImap.logins = []
        FakeImap.messages = {
            b'7': message('<a@example.invalid>', [('Rechnung.pdf', test_inbox.synthetic_pdf()), ('script.exe', b'MZ')]),
            b'8': message('<b@example.invalid>', [], subject='Nur Text'),
        }

    def test_settings_encrypt_password_and_fetch_imports_attachments_once(self):
        settings = {'host': 'imap.example.invalid', 'port': 993, 'security': 'ssl', 'username': 'kanzlei@example.invalid', 'password': 'mailbox-secret'}
        with patch.object(mailbox, 'check_host', lambda host, port: None), patch.object(mailbox.imaplib, 'IMAP4_SSL', FakeImap), TestClient(api.app) as client:
            self.login(client)
            self.assertEqual(client.get('/api/inbox/mailbox').json(), {'configured': False})
            self.assertEqual(client.put('/api/inbox/mailbox', json={**settings, 'password': None}).status_code, 422)
            saved = client.put('/api/inbox/mailbox', json=settings).json()
            self.assertNotIn('password', saved)
            with api.db() as connection:
                stored = connection.execute('SELECT password_encrypted FROM mailbox_settings').fetchone()[0]
            self.assertNotIn('mailbox-secret', stored)
            # Saving without a password keeps the stored one.
            self.assertEqual(client.put('/api/inbox/mailbox', json={**settings, 'password': None, 'folder': 'INBOX'}).json()['version'], 2)

            result = client.post('/api/inbox/mailbox/fetch').json()
            self.assertEqual([item['name'] for item in result['imported']], ['Rechnung.pdf'])
            self.assertEqual(result['skipped_messages'], 1)
            entry = client.get('/api/inbox').json()[0]
            self.assertEqual((entry['subject'], entry['sender'], entry['received_on'], entry['case_id']),
                             ('Rechnung 42', 'Vermieter GmbH <rechnung@example.invalid>', '2026-10-13', None))
            self.assertEqual(client.get(f"/api/inbox/{entry['id']}/download").content, test_inbox.synthetic_pdf())
            # A second fetch does not duplicate.
            self.assertEqual(client.post('/api/inbox/mailbox/fetch').json()['imported'], [])
            self.assertEqual(len(client.get('/api/inbox').json()), 1)
            self.assertEqual(FakeImap.logins[0], ('kanzlei@example.invalid', 'mailbox-secret'))

            FakeImap.messages[b'9'] = message('<c@example.invalid>', [('Mahnung.pdf', test_inbox.synthetic_pdf())])
            with api.db() as connection:
                connection.execute("UPDATE mailbox_settings SET password_encrypted=?", (mailbox.cipher(api.DATA_DIR).encrypt(b'wrong').decode(),))
            self.assertEqual(client.post('/api/inbox/mailbox/fetch').json()['detail'], 'mailbox_login_failed')
            self.assertEqual(client.delete('/api/inbox/mailbox').status_code, 204)
            self.assertEqual(client.post('/api/inbox/mailbox/fetch').status_code, 409)

    def test_private_hosts_are_refused(self):
        with TestClient(api.app) as client, patch.dict(os.environ, {'MAILBOX_ALLOW_PRIVATE_HOSTS': ''}):
            self.login(client)
            for host in ('127.0.0.1', 'localhost', '10.0.0.5', '169.254.169.254'):
                response = client.put('/api/inbox/mailbox', json={'host': host, 'port': 993, 'username': 'x', 'password': 'y'})
                self.assertEqual(response.json()['detail'], 'mailbox_host_not_public', host)
            self.assertEqual(client.put('/api/inbox/mailbox', json={'host': 'imap.example.com', 'port': 25, 'username': 'x', 'password': 'y'}).status_code, 422)
