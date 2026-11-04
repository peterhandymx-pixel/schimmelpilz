from datetime import date, timedelta
from fastapi.testclient import TestClient
from server import app as api
from server.tests import test_inbox


class BookkeepingTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_client_money_fee_settlement_vat_and_export(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            ledger = client.get('/api/ledger').json()
            self.assertEqual([a['kind'] for a in ledger['accounts']], ['office', 'trust', 'cash'])
            office, trust, cash = (a['id'] for a in ledger['accounts'])
            book = lambda **body: client.post('/api/ledger/entries', json={'day': '2026-11-02', 'text': 'Buchung', **body})

            # Client money belongs to a case, stays on the trust account and never goes below zero.
            self.assertEqual(book(account_id=trust, direction='in', amount='1000', category='trust_in').status_code, 422)
            self.assertEqual(book(account_id=office, direction='in', amount='1000', category='trust_in', case_id=case_id).json()['detail'], 'client_money_only_on_trust_account')
            self.assertEqual(book(account_id=trust, direction='in', amount='100', category='other_income').json()['detail'], 'office_booking_on_trust_account')
            self.assertEqual(book(account_id=trust, direction='in', amount='1000', category='trust_in', case_id=case_id, counterparty='Gegner GmbH').status_code, 201)
            self.assertEqual(book(account_id=trust, direction='out', amount='1200', category='trust_out', case_id=case_id).json()['detail'], 'client_money_insufficient')
            out = book(account_id=trust, direction='out', amount='400', category='trust_out', case_id=case_id, counterparty='Mandant').json()
            self.assertEqual(client.get('/api/ledger').json()['trust'][0]['balance_minor'], 60000)

            # Settling client money against an invoice pays the invoice and books fee income with its VAT share.
            invoice = client.post('/api/invoices', json={'case_id': case_id, 'recipient': 'Max Mustermann, Hauptstr. 1', 'issued_on': '2026-11-02', 'value': '10000', 'fees': [{'code': '2300', 'rate': '1.3'}]}).json()
            self.assertEqual((invoice['result']['gross'], invoice['result']['vat']), ('1032.44', '164.84'))
            self.assertEqual(book(account_id=trust, direction='out', amount='600', category='trust_to_fees', case_id=case_id, invoice_id=invoice['id']).status_code, 201)
            self.assertEqual(client.get('/api/invoices').json()['invoices'][0]['open_minor'], 43244)
            paid = client.post(f'/api/invoices/{invoice["id"]}/payments', json={'paid_on': '2026-11-03', 'amount': '432.44'}).json()
            self.assertEqual(paid['status'], 'paid')
            ledger = client.get('/api/ledger').json()
            fee_entries = [e for e in ledger['entries'] if e['category'] == 'fee_income']
            self.assertEqual(sorted(e['vat_minor'] for e in fee_entries), [6904, 9580])
            self.assertEqual(ledger['trust'], [])                 # the case's client money is fully used
            balances = {a['kind']: a['balance_minor'] for a in ledger['accounts']}
            self.assertEqual((balances['office'], balances['trust']), (103244, 0))

            book(account_id=office, direction='out', amount='119', category='expense', vat_rate='19', counterparty='Bürobedarf', day='2026-11-04')
            vat = client.get('/api/ledger/vat', params={'year': 2026, 'period': 'Q4'}).json()
            self.assertEqual((vat['kz81_minor'], vat['output_vat_minor'], vat['kz66_minor'], vat['kz83_minor']), (86760, 16484, 1900, 14584))

            # Reversal books the opposite amount once; the original stays.
            self.assertEqual(client.post(f'/api/ledger/entries/{out["id"]}/reverse', json={'reason': 'Falsch gebucht'}).status_code, 200)
            self.assertEqual(client.post(f'/api/ledger/entries/{out["id"]}/reverse', json={'reason': 'Falsch gebucht'}).json()['detail'], 'already_reversed')
            self.assertEqual(client.get('/api/ledger').json()['trust'][0]['balance_minor'], 40000)

            csv = client.get('/api/ledger/datev.csv', params={'year': 2026}).content.decode('utf-8-sig')
            self.assertIn('1810', csv)     # trust account (SKR04 default)
            self.assertIn('4400', csv)     # revenue 19 %
            stats = client.get('/api/ledger/statistics', params={'year': 2026}).json()
            self.assertEqual(stats['fees_by_month'][10]['net_minor'], 86760)

    def test_client_money_held_too_long_is_flagged(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            trust = client.get('/api/ledger').json()['accounts'][1]['id']
            old = (date.today() - timedelta(days=20)).isoformat()
            client.post('/api/ledger/entries', json={'account_id': trust, 'day': old, 'direction': 'in', 'amount': '50', 'category': 'trust_in', 'case_id': case_id, 'text': 'Zahlung Gegner'})
            held = client.get('/api/ledger').json()['trust'][0]
            self.assertTrue(held['overdue'])
            self.assertEqual(held['days'], 20)
