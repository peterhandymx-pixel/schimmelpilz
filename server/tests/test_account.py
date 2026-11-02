import email
from email import policy
import os
import re
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import account, app as api
from server.tests import test_inbox

PASSWORD = 'Synthetic-inbox-password-2026!'


class AccountTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def setUp(self):
        super().setUp()
        account.mail_requests.clear()
        self.outbox = Path(self.temp.name) / 'outbox'
        self.env = patch.dict(os.environ, {'MAIL_OUTBOX_DIR': str(self.outbox), 'PUBLIC_APP_URL': 'https://app.example.invalid'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def mails(self):
        return [email.message_from_bytes(path.read_bytes(), policy=policy.default) for path in sorted(self.outbox.glob('*.eml'), key=lambda item: item.stat().st_mtime_ns)] if self.outbox.exists() else []

    def link_token(self, message, name):
        body = message.get_body().get_content()
        return re.search(name + r'=([A-Za-z0-9_-]+)', body).group(1)

    def test_profile_email_and_password_changes(self):
        with TestClient(api.app) as client, TestClient(api.app) as other_device:
            self.login(client); self.login(other_device)
            self.assertEqual(len(self.mails()), 1)  # registration confirmation
            profile = {'full_name': 'Renamed Person', 'street': 'Neue Straße 2', 'postal_code': '20095', 'city': 'Hamburg', 'country': 'Deutschland', 'phone': '+49 40 1'}
            updated = client.put('/api/auth/profile', json=profile).json()
            self.assertEqual((updated['full_name'], updated['city']), ('Renamed Person', 'Hamburg'))
            self.assertEqual(client.put('/api/auth/profile', json={**profile, 'audience': 'law_firm'}).status_code, 422)

            self.assertEqual(client.put('/api/auth/email', json={'email': 'new@example.invalid', 'password': 'wrong-password'}).status_code, 403)
            changed = client.put('/api/auth/email', json={'email': 'New@Example.invalid', 'password': PASSWORD}).json()
            self.assertEqual((changed['email'], changed['email_verified']), ('new@example.invalid', False))
            self.assertEqual(self.mails()[-1]['To'], 'new@example.invalid')

            self.assertEqual(client.put('/api/auth/password', json={'current_password': 'wrong', 'new_password': 'Another-password-2026!'}).status_code, 403)
            self.assertEqual(client.put('/api/auth/password', json={'current_password': PASSWORD, 'new_password': 'Another-password-2026!'}).status_code, 200)
            self.assertEqual(client.get('/api/auth/me').status_code, 200)
            self.assertEqual(other_device.get('/api/auth/me').status_code, 401)
            with TestClient(api.app) as fresh:
                fresh.headers['X-Schimmelpilz-Request'] = '1'
                self.assertEqual(fresh.post('/api/auth/login', json={'email': 'new@example.invalid', 'password': PASSWORD}).status_code, 401)
                self.assertEqual(fresh.post('/api/auth/login', json={'email': 'new@example.invalid', 'password': 'Another-password-2026!'}).status_code, 200)

    def test_email_verification_and_password_reset(self):
        with TestClient(api.app) as client:
            self.login(client)
            self.assertFalse(client.get('/api/auth/me').json()['email_verified'])
            token = self.link_token(self.mails()[0], 'verify')
            self.assertTrue(self.mails()[0].get_body().get_content().count('https://app.example.invalid/?verify='))
            self.assertEqual(client.post('/api/auth/verify-email/confirm', json={'token': 'x' * 30}).status_code, 400)
            self.assertEqual(client.post('/api/auth/verify-email/confirm', json={'token': token}).status_code, 200)
            self.assertTrue(client.get('/api/auth/me').json()['email_verified'])
            self.assertEqual(client.post('/api/auth/verify-email/confirm', json={'token': token}).status_code, 400)

        with TestClient(api.app) as anonymous:
            anonymous.headers['X-Schimmelpilz-Request'] = '1'
            before = len(self.mails())
            # Unknown addresses get the same answer and no mail.
            self.assertEqual(anonymous.post('/api/auth/password-reset/request', json={'email': 'nobody@example.invalid'}).status_code, 202)
            self.assertEqual(len(self.mails()), before)
            self.assertEqual(anonymous.post('/api/auth/password-reset/request', json={'email': 'INBOX-test@example.invalid'}).status_code, 202)
            token = self.link_token(self.mails()[-1], 'reset')
            self.assertEqual(anonymous.post('/api/auth/password-reset/confirm', json={'token': token, 'password': 'short'}).status_code, 422)
            self.assertEqual(anonymous.post('/api/auth/password-reset/confirm', json={'token': token, 'password': 'Recovered-password-2026!'}).status_code, 200)
            self.assertEqual(anonymous.post('/api/auth/password-reset/confirm', json={'token': token, 'password': 'Recovered-password-2026!'}).status_code, 400)
            self.assertEqual(anonymous.post('/api/auth/login', json={'email': 'inbox-test@example.invalid', 'password': 'Recovered-password-2026!'}).status_code, 200)
            for _ in range(5):
                anonymous.post('/api/auth/password-reset/request', json={'email': 'inbox-test@example.invalid'})
            self.assertEqual(len([m for m in self.mails() if 'Passwort' in m['Subject']]), 3)  # per-address limit

    def test_reset_is_silent_without_mail_configuration(self):
        with patch.dict(os.environ, {'MAIL_OUTBOX_DIR': '', 'PUBLIC_APP_URL': ''}), TestClient(api.app) as client:
            client.headers['X-Schimmelpilz-Request'] = '1'
            self.assertEqual(client.get('/api/auth/capabilities').json(), {'mail': False})
            self.assertEqual(client.post('/api/auth/password-reset/request', json={'email': 'x@example.invalid'}).status_code, 202)
            self.assertFalse(self.outbox.exists())

    def test_two_factor_login_replay_and_recovery_codes(self):
        with TestClient(api.app) as client:
            self.login(client)
            self.assertEqual(client.post('/api/auth/mfa/setup', json={'password': 'wrong'}).status_code, 403)
            secret = client.post('/api/auth/mfa/setup', json={'password': PASSWORD}).json()['secret']
            self.assertEqual(client.post('/api/auth/mfa/enable', json={'code': '000000'}).status_code, 422)
            step = int(time.time() // 30)
            enabled = client.post('/api/auth/mfa/enable', json={'code': account.totp(secret, step)}).json()
            codes = enabled['recovery_codes']
            self.assertEqual(len(codes), 8)
            self.assertTrue(client.get('/api/auth/me').json()['mfa_enabled'])
        with TestClient(api.app) as device:
            device.headers['X-Schimmelpilz-Request'] = '1'
            login = {'email': 'inbox-test@example.invalid', 'password': PASSWORD}
            self.assertEqual(device.post('/api/auth/login', json=login).json()['detail'], 'mfa_required')
            self.assertEqual(device.get('/api/auth/me').status_code, 401)
            # The code used for enabling cannot be replayed.
            self.assertEqual(device.post('/api/auth/login', json={**login, 'mfa_code': account.totp(secret, step)}).json()['detail'], 'mfa_code_invalid')
            self.assertEqual(device.post('/api/auth/login', json={**login, 'mfa_code': account.totp(secret, step + 1)}).status_code, 200)
            device.post('/api/auth/logout')
            self.assertEqual(device.post('/api/auth/login', json={**login, 'mfa_code': codes[0].upper()}).status_code, 200)
            device.post('/api/auth/logout')
            self.assertEqual(device.post('/api/auth/login', json={**login, 'mfa_code': codes[0]}).status_code, 401)
            self.assertEqual(device.post('/api/auth/login', json={**login, 'mfa_code': codes[1]}).status_code, 200)
            self.assertEqual(device.post('/api/auth/mfa/disable', json={'password': PASSWORD, 'code': '123456'}).status_code, 422)
            self.assertEqual(device.post('/api/auth/mfa/disable', json={'password': PASSWORD, 'code': codes[2]}).status_code, 200)
            device.post('/api/auth/logout')
            self.assertEqual(device.post('/api/auth/login', json=login).status_code, 200)

    def test_account_deletion_removes_everything_owned(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client); self.login(other, 'keeps@example.invalid')
            case_id = self.case(client); kept = self.case(other)
            client.post(f'/api/cases/{case_id}/documents', files={'file': ('Own.pdf', test_inbox.synthetic_pdf(), 'application/pdf')})
            self.upload(client)
            client.post('/api/contacts', json={'name': 'Synthetic Contact'})
            other.post(f'/api/cases/{kept}/documents', files={'file': ('Other.pdf', test_inbox.synthetic_pdf(), 'application/pdf')})
            me = client.get('/api/auth/me').json()
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())), 3)
            self.assertEqual(client.post('/api/auth/account/delete', json={'password': 'wrong', 'confirm': 'DELETE'}).status_code, 403)
            self.assertEqual(client.post('/api/auth/account/delete', json={'password': PASSWORD, 'confirm': 'nope'}).status_code, 422)
            self.assertEqual(client.post('/api/auth/account/delete', json={'password': PASSWORD, 'confirm': 'LÖSCHEN'}).status_code, 204)
            self.assertEqual(client.get('/api/auth/me').status_code, 401)
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())), 1)
            with api.db() as connection:
                self.assertIsNone(connection.execute('SELECT 1 FROM users WHERE id=?', (me['id'],)).fetchone())
                for table in ('cases', 'contacts', 'inbox_documents', 'subscriptions'):
                    self.assertEqual(connection.execute(f'SELECT COUNT(*) FROM {table} WHERE user_id=?', (me['id'],)).fetchone()[0], 0, table)
            self.assertEqual(len(other.get('/api/cases').json()[0]['documents']), 1)
            client.headers['X-Schimmelpilz-Request'] = '1'
            self.assertEqual(client.post('/api/auth/login', json={'email': 'inbox-test@example.invalid', 'password': PASSWORD}).status_code, 401)

    def test_last_admin_blocks_deletion_and_payment_evidence_is_retained(self):
        with TestClient(api.app) as client:
            self.login(client)
            me = client.get('/api/auth/me').json()
            with api.db() as connection:
                connection.execute('UPDATE users SET is_admin=1 WHERE id=?', (me['id'],))
            self.assertEqual(client.post('/api/auth/account/delete', json={'password': PASSWORD, 'confirm': 'DELETE'}).json()['detail'], 'last_administrator')
            with api.db() as connection:
                connection.execute('UPDATE users SET is_admin=0 WHERE id=?', (me['id'],))
                connection.execute("INSERT INTO billing_payments(id,user_id,email,plan,months,amount_minor,currency,provider,reference,paid_on,period_start,period_end,recorded_by,created_at) VALUES('pay-1',?,?,'personal',1,990,'EUR','clip','clip-synthetic','2026-01-01','2026-01-01','2026-02-01','operator','2026-01-01')", (me['id'], me['email']))
            self.assertEqual(client.post('/api/auth/account/delete', json={'password': PASSWORD, 'confirm': 'DELETE'}).status_code, 204)
            with api.db() as connection:
                self.assertEqual(connection.execute("SELECT email FROM billing_payments WHERE id='pay-1'").fetchone()[0], me['email'])
