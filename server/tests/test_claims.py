from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from server import app as api, claims
from server.tests import test_inbox


def by_hand(amount, rate, days):
    return Decimal(amount) * Decimal(rate) / 100 * days / 365


class ClaimTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_default_interest_follows_the_base_rate(self):
        self.assertEqual(claims.base_rate(date(2026, 6, 30)), Decimal('1.27'))
        self.assertEqual(claims.base_rate(date(2026, 7, 1)), Decimal('1.52'))
        item = {'id': 'a', 'kind': 'principal', 'description': 'Rechnung', 'amount_minor': 100000, 'booked_on': '2026-01-01', 'interest_mode': 'consumer', 'interest_rate': None, 'interest_from': '2026-01-01'}
        result = claims.statement([item], [], date(2026, 12, 31))
        expected = by_hand(1000, '6.27', 181) + by_hand(1000, '6.52', 184)
        self.assertEqual(result['interest'], str(expected.quantize(Decimal('0.01'))))
        self.assertEqual(result['interest'], '63.96')
        self.assertFalse(result['rate_warning'])
        # Between businesses: 9 points over the base rate.
        business = claims.statement([{**item, 'interest_mode': 'business'}], [], date(2026, 12, 31))
        self.assertEqual(business['interest'], str((by_hand(1000, '10.27', 181) + by_hand(1000, '10.52', 184)).quantize(Decimal('0.01'))))
        self.assertTrue(claims.statement([item], [], date(2027, 2, 1))['rate_warning'])

    def test_payments_go_to_costs_then_interest_then_principal(self):
        principal = {'id': 'p', 'kind': 'principal', 'description': 'Kaufpreis', 'amount_minor': 100000, 'booked_on': '2026-01-01', 'interest_mode': 'consumer', 'interest_rate': None, 'interest_from': '2026-01-01'}
        cost = {'id': 'c', 'kind': 'cost', 'description': 'Mahnkosten', 'amount_minor': 5000, 'booked_on': '2026-01-10', 'interest_mode': 'none', 'interest_rate': None, 'interest_from': None}
        payment = {'paid_on': '2026-04-01', 'amount_minor': 30000, 'note': ''}
        result = claims.statement([principal, cost], [payment], date(2026, 12, 31))
        interest_before = by_hand(1000, '6.27', 90)                      # 1 Jan – 31 Mar
        remaining = Decimal(1000) - (Decimal(300) - Decimal(50) - interest_before)
        interest_after = by_hand(remaining, '6.27', 91) + by_hand(remaining, '6.52', 184)
        self.assertEqual(result['costs'], '0.00')
        self.assertEqual(result['principal'], str(remaining.quantize(Decimal('0.01'))))
        self.assertEqual(result['interest'], str(interest_after.quantize(Decimal('0.01'))))
        self.assertEqual(result['total'], str((remaining + interest_after).quantize(Decimal('0.01'))))
        self.assertIn('Kosten 50,00 €', [entry for entry in result['entries'] if entry['day'] == '2026-04-01'][0]['text'])

    def test_claim_routes_and_report(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            self.assertEqual(client.post(f'/api/cases/{case_id}/claim/items', json={'kind': 'principal', 'description': 'Rechnung 12', 'amount': '1000', 'booked_on': '2026-01-01', 'interest_mode': 'consumer'}).status_code, 422)
            client.post(f'/api/cases/{case_id}/claim/items', json={'kind': 'principal', 'description': 'Rechnung 12', 'amount': '1000', 'booked_on': '2026-01-01', 'interest_mode': 'consumer', 'interest_from': '2026-01-01'})
            data = client.post(f'/api/cases/{case_id}/claim/payments', json={'paid_on': '2026-04-01', 'amount': '100'}).json()
            self.assertEqual((len(data['items']), len(data['payments'])), (1, 1))
            statement = client.get(f'/api/cases/{case_id}/claim', params={'as_of': '2026-12-31'}).json()['statement']
            self.assertEqual(Decimal(statement['principal']) < 1000, True)
            pdf = client.get(f'/api/cases/{case_id}/claim/report.pdf', params={'as_of': '2026-12-31'})
            self.assertEqual((pdf.status_code, pdf.headers['content-type']), (200, 'application/pdf'))
            payment_id = data['payments'][0]['id']
            self.assertEqual(client.delete(f'/api/cases/{case_id}/claim/payments/{payment_id}').status_code, 204)
            self.assertEqual(client.get(f'/api/cases/{case_id}/claim').json()['payments'], [])


def test_bundesbank_series_parsing_and_merge(tmp_path=None):
    import tempfile
    from datetime import date as day
    from pathlib import Path
    from unittest import mock
    from server import claims
    sample = '﻿"";BBIN1.M.DE.BBK.BBKBAS2.EUR.ME\nEinheit;% p.a.;\n2026-12;1,52;\n2027-01;1,77;Bemerkung\n2027-02;1,77;\n'
    rates, until = claims.parse_rates(sample)
    assert rates[-1] == (day(2027, 2, 1), '1.77') and until == day(2027, 6, 30)
    folder = Path(tempfile.mkdtemp())

    class Reply:
        def __init__(self, text): self.text = text
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit): return self.text.encode('utf-8')

    with mock.patch.object(claims, 'RATE_CACHE', folder / 'base-rates.json'), mock.patch.dict(claims._FETCHED, {'rates': None, 'until': None, 'checked': 0.0}), \
            mock.patch.dict('os.environ', {'BASE_RATE_FETCH_IN_TESTS': '1'}), mock.patch.object(claims, 'urlopen', lambda request, timeout: Reply(sample)):
        assert claims.refresh_rates() is True
        assert claims.refresh_rates() is False                      # at most once a day
        assert claims.base_rate(day(2027, 3, 15)) == claims.Decimal('1.77')
        assert claims.base_rate(day(2024, 3, 15)) == claims.Decimal('3.62')   # built-in history still applies
        assert claims.known_until() == day(2027, 6, 30)
        assert (folder / 'base-rates.json').is_file()
    # A failed download keeps the built-in table and never raises.
    with mock.patch.dict(claims._FETCHED, {'rates': [], 'until': None, 'checked': 0.0}), mock.patch.dict('os.environ', {'BASE_RATE_FETCH_IN_TESTS': '1'}), \
            mock.patch.object(claims, 'RATE_CACHE', folder / 'other.json'), mock.patch.object(claims, 'urlopen', side_effect=OSError('offline')):
        assert claims.refresh_rates(force=True) is False
        assert claims.known_until() == claims.KNOWN_UNTIL
