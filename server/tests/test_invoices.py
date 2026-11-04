from fastapi.testclient import TestClient
from server import app as api
from server.tests import test_inbox


class InvoiceTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def base(self, case_id, **extra):
        return {'case_id': case_id, 'recipient': 'Max Mustermann\nHauptstr. 1\n80331 München', 'issued_on': '2026-11-04', **extra}

    def test_court_fees_with_credit_flat_rate_and_vat(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            body = self.base(case_id, value='10000', fees=[{'code': '3100', 'rate': '1.3'}, {'code': '3104', 'rate': '1.2'}], credit={'rate': '1.3', 'value': '10000'})
            result = client.post('/api/invoices/calculate', json=body).json()
            self.assertEqual([line['amount'] for line in result['lines']], ['847.60', '782.40', '-423.80', '20.00'])
            self.assertEqual((result['net'], result['vat'], result['gross'], result['payable']), ('1226.20', '232.98', '1459.18', '1459.18'))
            # The credit is half the business fee, at most 0.75.
            capped = client.post('/api/invoices/calculate', json={**body, 'credit': {'rate': '2.5', 'value': '10000'}}).json()
            self.assertEqual(capped['lines'][2]['amount'], '-489.00')
            # Rates outside the range of a fee event are refused; values above the table too.
            self.assertEqual(client.post('/api/invoices/calculate', json={**body, 'fees': [{'code': '3100', 'rate': '2.0'}]}).status_code, 422)
            self.assertEqual(client.post('/api/invoices/calculate', json={**body, 'value': '600000'}).status_code, 422)
            # Small business fee: the flat rate is 20 % of the fees.
            small = client.post('/api/invoices/calculate', json=self.base(case_id, value='500', fees=[{'code': '2300', 'rate': '1.3'}])).json()
            self.assertEqual([line['amount'] for line in small['lines']], ['66.95', '13.39'])

    def test_advance_payment_final_invoice_cancel_and_open_items(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            advance = client.post('/api/invoices', json=self.base(case_id, kind='advance', advance_net='500')).json()
            self.assertEqual((advance['number'], advance['result']['gross'], advance['open_minor']), ('2026-0001', '595.00', 59500))
            paid = client.post(f'/api/invoices/{advance["id"]}/payments', json={'paid_on': '2026-11-05', 'amount': '595.00'}).json()
            self.assertEqual((paid['status'], paid['open_minor']), ('paid', 0))

            final = client.post('/api/invoices', json=self.base(case_id, value='10000', fees=[{'code': '2300', 'rate': '1.3'}])).json()
            self.assertEqual(final['number'], '2026-0002')
            self.assertEqual(final['result']['gross'], '1032.44')        # (847.60 + 20.00) × 1.19
            self.assertEqual(final['result']['advances'], [{'number': '2026-0001', 'amount': '595.00'}])
            self.assertEqual(final['result']['payable'], '437.44')
            # The advance is credited only once.
            again = client.post('/api/invoices/calculate', json=self.base(case_id, value='10000', fees=[{'code': '2300', 'rate': '1.3'}])).json()
            self.assertEqual(again['advances'], [])
            self.assertEqual(client.get('/api/invoices', params={'status': 'open'}).json()['open_total_minor'], 43744)

            # Cancelling keeps the number and frees the advance again.
            self.assertEqual(client.post(f'/api/invoices/{final["id"]}/cancel', json={'reason': 'Falscher Gegenstandswert'}).json()['status'], 'cancelled')
            self.assertEqual(client.post(f'/api/invoices/{final["id"]}/payments', json={'paid_on': '2026-11-06', 'amount': '1'}).status_code, 409)
            self.assertEqual(client.post('/api/invoices/calculate', json=self.base(case_id, value='10000', fees=[{'code': '2300', 'rate': '1.3'}])).json()['advances'][0]['number'], '2026-0001')
            third = client.post('/api/invoices', json=self.base(case_id, kind='advance', advance_net='100')).json()
            self.assertEqual(third['number'], '2026-0003')

            pdf = client.get(f'/api/invoices/{final["id"]}/pdf')
            self.assertEqual((pdf.status_code, pdf.headers['content-type']), (200, 'application/pdf'))
            csv = client.get('/api/invoices.csv').content.decode('utf-8-sig')
            self.assertIn('2026-0002', csv)
            self.assertIn('storniert', csv)

    def test_time_entries_become_one_invoice(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            client.post(f'/api/cases/{case_id}/time-entries', json={'day': '2026-11-03', 'minutes': 90, 'activity': 'Besprechung mit Mandant', 'hourly_rate': '200'})
            entries = client.post(f'/api/cases/{case_id}/time-entries', json={'day': '2026-11-04', 'minutes': 20, 'activity': 'Telefonat Gegenseite', 'hourly_rate': '180'}).json()
            self.assertEqual(len(entries), 2)
            invoice = client.post('/api/invoices', json=self.base(case_id, kind='time')).json()
            self.assertEqual([line['amount'] for line in invoice['result']['lines']], ['300.00', '60.00'])
            self.assertEqual(invoice['result']['gross'], '428.40')
            # Billed entries cannot be billed twice or deleted.
            self.assertEqual(client.post('/api/invoices', json=self.base(case_id, kind='time')).json()['detail'], 'no_unbilled_time')
            entry = client.get(f'/api/cases/{case_id}/time-entries').json()[0]
            self.assertEqual(entry['invoice_number'], invoice['number'])
            self.assertEqual(client.delete(f'/api/cases/{case_id}/time-entries/{entry["id"]}').status_code, 409)
