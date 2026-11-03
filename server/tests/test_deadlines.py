import unittest
from datetime import date

from fastapi.testclient import TestClient

from server import app as api, deadlines
from server.tests import test_inbox


class DeadlineRuleTests(unittest.TestCase):
    def end(self, start, amount, unit, start_type='event', state=None, shift=True):
        return deadlines.calculate(date.fromisoformat(start), amount, unit, start_type, state, shift)

    def test_easter_and_movable_holidays(self):
        self.assertEqual([deadlines.easter(year) for year in (2024, 2025, 2026, 2027)],
                         [date(2024, 3, 31), date(2025, 4, 20), date(2026, 4, 5), date(2027, 3, 28)])
        names = deadlines.holidays(2026, 'SN')
        self.assertEqual(names[date(2026, 11, 18)], 'Buß- und Bettag')
        self.assertEqual(deadlines.holidays(2026, 'BY')[date(2026, 6, 4)], 'Fronleichnam')
        self.assertNotIn(date(2026, 6, 4), deadlines.holidays(2026, 'NI'))
        self.assertIn(date(2017, 10, 31), deadlines.holidays(2017, 'BY'))  # one-off nationwide
        self.assertNotIn(date(2016, 10, 31), deadlines.holidays(2016, 'HH'))  # Hamburg only since 2018
        self.assertIn(date(2026, 10, 31), deadlines.holidays(2026, 'HH'))
        self.assertIn(date(2026, 3, 8), deadlines.holidays(2026, 'MV'))
        self.assertNotIn(date(2022, 3, 8), deadlines.holidays(2022, 'MV'))

    def test_period_rules_and_shifting(self):
        # § 187 Abs. 1, § 188 Abs. 2: same weekday; Karfreitag, weekend and Ostermontag push to Tuesday.
        result = self.end('2026-03-20', 2, 'weeks')
        self.assertEqual((result['raw_end'], result['end'], result['shifted']), ('2026-04-03', '2026-04-07', True))
        self.assertEqual([item['reason'] for item in result['skipped']], ['Karfreitag', 'Samstag', 'Sonntag', 'Ostermontag'])
        self.assertEqual(self.end('2026-03-19', 2, 'weeks')['end'], '2026-04-02')
        # § 188 Abs. 3: no 31 April, so 30 April.
        month = self.end('2026-03-31', 1, 'months')
        self.assertEqual((month['end'], month['rule']), ('2026-04-30', '§ 188 Abs. 3 BGB'))
        # 28 February 2026 is a Saturday.
        self.assertEqual(self.end('2026-01-31', 1, 'months')['end'], '2026-03-02')
        self.assertEqual(self.end('2026-01-31', 1, 'months', shift=False)['end'], '2026-02-28')
        # § 187 Abs. 2: the day itself counts.
        self.assertEqual(self.end('2026-03-01', 1, 'months', 'day_start')['end'], '2026-03-31')
        self.assertEqual(self.end('2026-03-02', 3, 'days', 'day_start')['end'], '2026-03-04')
        self.assertEqual(self.end('2026-12-22', 3, 'days')['end'], '2026-12-28')
        self.assertEqual(self.end('2025-02-28', 1, 'years')['end'], '2026-03-02')
        # State holidays only where they apply.
        self.assertEqual(self.end('2026-05-21', 2, 'weeks', state='BY')['end'], '2026-06-05')
        self.assertEqual(self.end('2026-05-21', 2, 'weeks', state='NI')['end'], '2026-06-04')
        with self.assertRaises(ValueError):
            self.end('2034-06-01', 2, 'years')


class DeadlineApiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_endpoint(self):
        with TestClient(api.app) as client:
            client.headers['X-Schimmelpilz-Request'] = '1'
            self.assertEqual(client.post('/api/deadlines/calculate', json={'start_date': '2026-03-20', 'amount': 2, 'unit': 'weeks'}).status_code, 401)
            self.login(client)
            result = client.post('/api/deadlines/calculate', json={'start_date': '2026-03-20', 'amount': 2, 'unit': 'weeks', 'state': 'BE'}).json()
            self.assertEqual(result['end'], '2026-04-07')
            self.assertEqual(client.post('/api/deadlines/calculate', json={'start_date': '2040-01-01', 'amount': 1, 'unit': 'days'}).status_code, 422)
            self.assertEqual(client.post('/api/deadlines/calculate', json={'start_date': '2026-01-01', 'amount': 1, 'unit': 'hours'}).status_code, 422)
            self.assertEqual(len(client.get('/api/deadlines/holidays?year=2026&state=SN').json()), 11)
