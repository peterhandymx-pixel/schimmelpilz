import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app as api
from server.tests import test_control

REASON = 'Synthetic support request for testing'


class AdminTests(test_control.ControlTests):
    # Only the back-office tests run here; the inherited control tests already run in test_control.
    test_scoped_team_access_actor_identity_revocation_and_invitation_replay = None
    test_admin_is_explicit_audited_and_disabled_accounts_lose_sessions = None
    test_clip_link_checkout_and_operator_recorded_prepaid_months = None
    test_operator_switches_are_versioned_and_stop_new_work_without_destroying_files = None
    test_trial_starts_at_registration_expiry_keeps_reads_and_operator_can_end_access = None
    test_demo_payment_only_in_test_mode_and_books_one_month = None
    test_starting_plan_follows_account_type = None
    test_calendar_months_and_paid_time_start = None
    test_public_operator_particulars_come_only_from_configuration = None

    def test_allowlist_limits_operator_powers(self):
        with TestClient(api.app) as operator, TestClient(api.app) as other:
            self.admin(operator, 'owner-admin@example.invalid'); self.login(other, 'someone@example.invalid')
            target = other.get('/api/auth/me').json()
            with patch.dict(os.environ, {'ADMIN_EMAILS': 'owner-admin@example.invalid'}):
                self.assertEqual(operator.get('/api/admin/overview').status_code, 200)
                # The allowlist blocks granting admin rights to anyone else.
                self.assertEqual(operator.put(f'/api/admin/users/{target["id"]}', json={'disabled': False, 'is_admin': True, 'expected_version': 0, 'reason': REASON}).json()['detail'], 'admin_not_allowlisted')
            with patch.dict(os.environ, {'ADMIN_EMAILS': 'someone-else@example.invalid'}):
                self.assertEqual(operator.get('/api/admin/overview').json()['detail'], 'administrator_required')
            self.assertEqual(other.get('/api/admin/overview').status_code, 403)

    def test_user_management_billing_actions_and_audit(self):
        with TestClient(api.app) as operator, TestClient(api.app) as client:
            self.admin(operator); self.login(client, 'customer@example.invalid'); self.case(client)
            me = client.get('/api/auth/me').json(); uid = me['id']
            detail = operator.get(f'/api/admin/users/{uid}').json()
            self.assertEqual(detail['counts']['cases'], 1)
            self.assertEqual(detail['subscription']['effective_status'], 'trial')

            # A reason is always required.
            self.assertEqual(operator.post(f'/api/admin/users/{uid}/verify-email', json={'reason': 'short'}).status_code, 422)
            self.assertEqual(operator.post(f'/api/admin/users/{uid}/verify-email', json={'reason': REASON}).status_code, 200)

            edit = {'full_name': 'Renamed Customer', 'organisation': 'Org', 'email': 'renamed@example.invalid', 'phone': '1', 'audience': 'business', 'reason': REASON}
            version = operator.get(f'/api/admin/users/{uid}').json()['user']['control_version']
            self.assertEqual(operator.put(f'/api/admin/users/{uid}/profile', json={**edit, 'expected_version': version - 1}).status_code, 409)
            self.assertEqual(operator.put(f'/api/admin/users/{uid}/profile', json={**edit, 'expected_version': version}).status_code, 200)
            user = operator.get(f'/api/admin/users/{uid}').json()['user']
            self.assertEqual((user['email'], user['full_name'], user['email_verified_at']), ('renamed@example.invalid', 'Renamed Customer', None))

            reset = operator.post(f'/api/admin/users/{uid}/password-reset', json={'reason': REASON}).json()
            token = reset['link'].split('reset=')[1]
            self.assertEqual(client.post('/api/auth/password-reset/confirm', json={'token': token, 'password': 'A-new-synthetic-password-1'}).status_code, 200)

            sub = operator.get(f'/api/admin/users/{uid}').json()['subscription']
            extended = operator.post(f'/api/admin/billing/{uid}/extend-trial', json={'days': 10, 'reason': REASON, 'expected_version': sub['version']})
            self.assertEqual(extended.status_code, 200, extended.text)
            self.assertGreater(extended.json()['trial_end'], sub['trial_end'])
            sub = operator.get(f'/api/admin/users/{uid}').json()['subscription']
            self.assertEqual(operator.put(f'/api/admin/billing/{uid}/plan', json={'plan': 'firm', 'reason': REASON, 'expected_version': sub['version']}).status_code, 200)

            sub = operator.get(f'/api/admin/users/{uid}').json()['subscription']
            free = operator.post(f'/api/admin/billing/{uid}/free-months', json={'plan': 'firm', 'months': 2, 'reason': REASON, 'expected_version': sub['version']})
            self.assertEqual(free.status_code, 201, free.text)
            detail = operator.get(f'/api/admin/users/{uid}').json()
            self.assertEqual(detail['subscription']['effective_status'], 'active')
            payment = detail['payments'][0]
            self.assertEqual((payment['provider'], payment['amount_minor'], payment['months']), ('manual', 0, 2))

            # Reversing the only booking returns the account to its (extended, still running) trial.
            self.assertEqual(operator.post(f'/api/admin/payments/{payment["id"]}/reverse', json={'reason': REASON}).status_code, 200)
            self.assertEqual(operator.post(f'/api/admin/payments/{payment["id"]}/reverse', json={'reason': REASON}).json()['detail'], 'already_reversed')
            detail = operator.get(f'/api/admin/users/{uid}').json()
            self.assertEqual(detail['subscription']['effective_status'], 'trial')
            self.assertIsNone(detail['subscription']['period_end'])

            csv = operator.get('/api/admin/payments.csv')
            self.assertEqual(csv.status_code, 200)
            self.assertIn('Gutschrift', csv.text)
            self.assertIn('renamed@example.invalid', csv.text)

            overview = operator.get('/api/admin/overview').json()
            self.assertGreaterEqual(overview['counts']['users'], 2)
            audit = operator.get('/api/admin/audit', params={'q': uid}).json()
            actions = {entry['action'] for entry in audit['entries']}
            self.assertEqual({'admin_profile_edit', 'admin_password_reset', 'admin_trial_extended', 'admin_plan_changed', 'admin_free_months', 'admin_payment_reversed'} - actions, set())

            # Deleting needs the exact address; payments stay for bookkeeping.
            self.assertEqual(operator.delete(f'/api/admin/users/{uid}', params={'confirm': 'wrong@example.invalid', 'reason': REASON}).status_code, 422)
            self.assertEqual(operator.delete(f'/api/admin/users/{uid}', params={'confirm': 'renamed@example.invalid', 'reason': REASON}).status_code, 204)
            self.assertEqual(operator.get(f'/api/admin/users/{uid}').status_code, 404)
            with api.db() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM billing_payments WHERE user_id=?', (uid,)).fetchone()[0], 1)

    def test_operator_cannot_delete_or_reset_themselves_here(self):
        with TestClient(api.app) as operator:
            self.admin(operator); me = operator.get('/api/auth/me').json()
            self.assertEqual(operator.delete(f'/api/admin/users/{me["id"]}', params={'confirm': me['email'], 'reason': REASON}).status_code, 409)
            self.assertEqual(operator.post(f'/api/admin/users/{me["id"]}/reset-mfa', json={'reason': REASON}).status_code, 409)
            self.assertEqual(operator.get('/api/admin/tools').status_code, 200)
