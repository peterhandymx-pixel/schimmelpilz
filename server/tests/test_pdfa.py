import io
import json

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from server import app as api, pdfa
from server.tests import test_inbox


def plain_helvetica_pdf():
    output = io.BytesIO()
    page = canvas.Canvas(output)
    page.drawString(100, 700, 'Klage gegen Müller Bau')
    page.save()
    return output.getvalue()


def test_ervb_filename_rules():
    assert pdfa.ervb_filename('SCH-2026/000001 Klage (Entwurf).v2') == 'SCH-2026-000001_Klage_Entwurf-v2.pdf'
    assert pdfa.ervb_filename('Äußerung über Gläubiger') == 'Äußerung_über_Gläubiger.pdf'
    assert len(pdfa.ervb_filename('x' * 200)) == 90
    assert pdfa.ervb_filename('///') == 'Schriftsatz.pdf'


def test_check_finds_unembedded_standard_font_and_pdfa_markers():
    report = pdfa.check(plain_helvetica_pdf())
    assert not report['ok'] and 'Helvetica' in report['issues'][0]
    marked = PdfReader(io.BytesIO(pdfa.to_pdfa(plain_helvetica_pdf(), 'Klage', 'Kanzlei')))
    root = marked.trailer['/Root']
    xmp = root['/Metadata'].get_object().get_data().decode('utf-8')
    assert '<pdfaid:part>2</pdfaid:part>' in xmp and '<pdfaid:conformance>B</pdfaid:conformance>' in xmp
    assert root['/OutputIntents'][0].get_object()['/S'] == '/GTS_PDFA1'
    assert len(marked.trailer['/ID']) == 2


class BeaDraftTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_saved_draft_as_bea_pdf(self):
        with TestClient(api.app) as client:
            self.login(client, 'bea@example.invalid')
            case = client.post('/api/cases', json={'title': 'Werklohn', 'description': 'Synthetische Akte für das beA-PDF.'}).json()
            draft = client.post(f"/api/cases/{case['id']}/drafts", json={'kind': 'claim', 'body': 'Landgericht Köln\n\nKLAGE\n\nÄußerst dringend.'}).json()
            response = client.get(f"/api/cases/{case['id']}/drafts/{draft['id']}/bea.pdf")
            self.assertEqual(response.status_code, 200)
            self.assertIn(f"{case['reference']}_Klage_v1.pdf", response.headers['content-disposition'])
            report = json.loads(response.headers['x-bea-check'])
            self.assertTrue(report['ok'], report)                                  # embedded Vera font, text layer
            reader = PdfReader(io.BytesIO(response.content))
            self.assertIn('Äußerst dringend', reader.pages[0].extract_text())
            self.assertIn('pdfaid:part', reader.trailer['/Root']['/Metadata'].get_object().get_data().decode())
            self.assertEqual(client.get(f"/api/cases/{case['id']}/drafts/unknown/bea.pdf").status_code, 404)
