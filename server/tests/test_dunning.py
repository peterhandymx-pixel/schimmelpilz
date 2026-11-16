import io

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server import app as api
from server.tests.test_invoices import InvoiceTests


class DunningTests(InvoiceTests):
    test_court_fees_with_credit_flat_rate_and_vat = None
    test_advance_payment_final_invoice_cancel_and_open_items = None
    test_time_entries_become_one_invoice = None

    def test_three_levels_tasks_pdf_and_payment(self):
        with TestClient(api.app) as client:
            self.login(client, 'dunning@example.invalid')
            case_id = client.post('/api/cases', json={'title': 'Honorar', 'description': 'Synthetische Akte für das Mahnwesen.'}).json()['id']
            old = client.post('/api/invoices', json=self.base(case_id, issued_on='2026-08-03', value='10000', fees=[{'code': '2300', 'rate': '1.3'}])).json()
            fresh = client.post('/api/invoices', json=self.base(case_id, value='5000', fees=[{'code': '2300', 'rate': '1.3'}], issued_on=api.now()[:10])).json()
            due = client.get('/api/invoices', params={'status': 'dunning'}).json()['invoices']
            self.assertEqual([item['number'] for item in due], [old['number']])           # 30 days passed only for the old one
            self.assertEqual(due[0]['next_level'], 1)
            for level in (1, 2, 3):
                item = client.post(f"/api/invoices/{old['id']}/reminders", json={'pay_within_days': 10, 'bank': 'IBAN DE00 0000 0000 0000 0000 00'}).json()
                self.assertEqual(item['dunning_level'], level)
            self.assertIsNone(item['next_level']); self.assertFalse(item['dunning_due'])
            self.assertEqual(client.post(f"/api/invoices/{old['id']}/reminders", json={}).status_code, 409)
            text = PdfReader(io.BytesIO(client.get(f"/api/invoices/{old['id']}/reminders/3/pdf").content)).pages[0].extract_text()
            self.assertIn('LETZTE MAHNUNG', text); self.assertIn('§ 11 RVG', text); self.assertIn('Verwendungszweck', text)
            first = PdfReader(io.BytesIO(client.get(f"/api/invoices/{old['id']}/reminders/1/pdf").content)).pages[0].extract_text()
            self.assertIn('ZAHLUNGSERINNERUNG', first)
            self.assertEqual(client.get(f"/api/invoices/{old['id']}/reminders/4/pdf").status_code, 404)
            tasks = client.get(f'/api/cases/{case_id}').json()['tasks']
            self.assertEqual(sum('Zahlungseingang prüfen' in task['title'] for task in tasks), 3)
            client.post(f"/api/invoices/{fresh['id']}/payments", json={'paid_on': api.now()[:10], 'amount': str(fresh['payable_minor'] / 100)})
            self.assertEqual(client.post(f"/api/invoices/{fresh['id']}/reminders", json={}).status_code, 409)
