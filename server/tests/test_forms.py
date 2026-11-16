import io
from datetime import date

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server import app as api, forms
from server.tests import test_inbox

USER = {'full_name': 'Dr. Petra Recht', 'organisation': 'Kanzlei Recht', 'street': 'Domstraße 1', 'postal_code': '50667', 'city': 'Köln', 'email': 'kanzlei@example.invalid'}


def test_bodies_use_case_data_and_placeholders():
    case = {'reference': '12/26', 'title': 'Kündigungsschutz', 'details': {'client_name': 'Anna Weber', 'opponent_name': 'Rheinland Logistik GmbH', 'legal_area': 'employment', 'dispute_value': 9000}}
    vollmacht = forms.body('vollmacht', case, USER)
    assert 'Dr. Petra Recht, Kanzlei Recht, Domstraße 1, 50667 Köln' in vollmacht
    assert 'Anna Weber ./. Rheinland Logistik GmbH' in vollmacht
    assert '[Anschrift des Mandanten]' in vollmacht
    fees = forms.body('kostenhinweis', case, USER)
    assert '§ 49b Abs. 5 BRAO' in fees and '§ 12a Abs. 1 Satz 1 ArbGG' in fees and '9.000,00 €' in fees
    civil = forms.body('kostenhinweis', {**case, 'details': {**case['details'], 'legal_area': 'contract', 'dispute_value': None}}, USER)
    assert '12a' not in civil and '[wird nach Prüfung mitgeteilt]' in civil
    confirmation = forms.body('mandatsbestaetigung', case, USER, today=date(2026, 11, 16))
    assert '16.11.2026' in confirmation and 'Unser Zeichen: 12/26' in confirmation
    assert '§ 50 Abs. 1 BRAO' in forms.body('datenschutz', case, USER)
    assert 'Schweigepflicht' in forms.body('schweigepflicht', case, USER)


class FormsApiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_form_pdf_and_owner_check(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client, 'forms@example.invalid')
            case = client.post('/api/cases', json={'title': 'Mietminderung', 'description': 'Synthetische Akte für Formulare.', 'details': {'client_name': 'Anna Weber'}}).json()
            self.assertEqual(len(client.get('/api/forms').json()), 5)
            for kind in forms.FORMS:
                response = client.get(f"/api/cases/{case['id']}/forms/{kind}.pdf")
                self.assertEqual(response.status_code, 200, kind)
                self.assertIn('attachment', response.headers['content-disposition'])
            text = ''.join(page.extract_text() for page in PdfReader(io.BytesIO(client.get(f"/api/cases/{case['id']}/forms/vollmacht.pdf").content)).pages)
            self.assertIn('VOLLMACHT', text)
            self.assertIn('Anna Weber', text)
            self.assertEqual(client.get(f"/api/cases/{case['id']}/forms/unbekannt.pdf").status_code, 404)
            self.login(other, 'forms-other@example.invalid')
            self.assertEqual(other.get(f"/api/cases/{case['id']}/forms/vollmacht.pdf").status_code, 404)
