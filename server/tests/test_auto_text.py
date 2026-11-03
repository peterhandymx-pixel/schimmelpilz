import io
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from server import app as api, auto_text, document_ocr
from server.tests import test_case_tools
from server.tests.test_inbox import synthetic_pdf
from server.tests.test_ocr import scan

REAL_RUN = subprocess.run


def scanned_pdf(pages=2):
    output = io.BytesIO(); writer = canvas.Canvas(output)
    for _ in range(pages):
        writer.drawImage(ImageReader(io.BytesIO(scan())), 40, 550, width=510, height=160); writer.showPage()
    writer.save(); return output.getvalue()


class FakeOcr:
    """Answers OCR worker calls like the real engine; every other subprocess (text-layer extraction) runs for real."""
    def __init__(self):
        self.calls = []

    def __call__(self, args, *rest, **options):
        if len(args) > 2 and args[2] == 'server.document_ocr':
            job = json.loads(args[4]); self.calls.append((job['start_page'], job['count'], job['language']))
            kind = 'page' if args[3].endswith('.pdf') else 'image'
            units = [{'unit_no': page, 'text': f'Erkannter Text Seite {page}', 'confidence': 88} for page in range(job['start_page'], job['start_page'] + job['count'])]
            return SimpleNamespace(stdout=json.dumps({'units': units, 'truncated': False, 'unit_kind': kind, 'total_pages': 2, 'engine': 'tesseract.js-7.0.0', 'language': job['language'], 'models': {}}).encode())
        return REAL_RUN(args, *rest, **options)


class AutoTextUnitTests(unittest.TestCase):
    def test_runs_group_consecutive_pages_in_small_batches(self):
        self.assertEqual(auto_text.runs([1, 2, 3, 7]), [(1, 3), (7, 1)])
        self.assertEqual(auto_text.runs(list(range(1, 10))), [(1, 4), (5, 4), (9, 1)])

    def test_targets_only_unreviewed_pages_without_text_layer(self):
        rows = [{'unit_no': 1, 'original_text': 'Ein echter Textabsatz mit genug Inhalt.', 'reviewed_text': None, 'reviewed_at': None},
                {'unit_no': 2, 'original_text': '- 2 -', 'reviewed_text': None, 'reviewed_at': None},
                {'unit_no': 3, 'original_text': '', 'reviewed_text': 'manuell', 'reviewed_at': '2026-10-23'}]
        self.assertEqual(auto_text.ocr_targets('.pdf', rows, 4), [2, 4])
        self.assertEqual(auto_text.ocr_targets('.jpg', [], 1), [1])
        self.assertEqual(auto_text.ocr_targets('.docx', [], 1), [])


class AutoTextApiTests(test_case_tools.CaseToolsTests):
    test_archive_restore_version_and_persistence = None
    test_export_originals_versions_hashes_and_isolation = None
    test_export_fails_for_missing_or_unsafe_original = None

    def upload(self, client, case, name, content, mime):
        response = client.post(f'/api/cases/{case["id"]}/documents', files={'file': (name, content, mime)})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def document(self, client, case, document_id):
        return next(item for item in client.get(f'/api/cases/{case["id"]}').json()['documents'] if item['id'] == document_id)

    def text(self, client, case, document_id):
        return client.get(f'/api/cases/{case["id"]}/documents/{document_id}/text').json()

    def test_photo_and_scanned_pdf_are_read_with_ocr_text_pdf_without(self):
        fake = FakeOcr()
        with TestClient(api.app) as client, patch('server.document_ocr.available', return_value=True), patch('server.ocr_routes.subprocess.run', side_effect=fake):
            self.login(client); case = self.case(client)
            photo = self.upload(client, case, 'brief.jpg', scan(), 'image/jpeg')
            self.assertEqual(fake.calls, [(1, 1, 'deu+eng')])
            unit = self.text(client, case, photo)['units'][0]
            self.assertEqual((unit['original_text'], unit['origin'], unit['reviewed_at']), ('Erkannter Text Seite 1', 'ocr', None))
            listed = self.document(client, case, photo)
            self.assertEqual((listed['auto_text_status'], listed['auto_text_ocr_pages'], listed['extraction_status']), ('done', 1, 'ready'))

            fake.calls.clear()
            scanned = self.upload(client, case, 'scan.pdf', scanned_pdf(2), 'application/pdf')
            self.assertEqual(fake.calls, [(1, 2, 'deu+eng')])
            self.assertEqual([u['original_text'] for u in self.text(client, case, scanned)['units']], ['Erkannter Text Seite 1', 'Erkannter Text Seite 2'])
            self.assertEqual(self.document(client, case, scanned)['auto_text_status'], 'done')

            fake.calls.clear()
            typed = self.upload(client, case, 'rechnung.pdf', synthetic_pdf(), 'application/pdf')
            self.assertEqual(fake.calls, [])
            self.assertIn('TEST-778', self.text(client, case, typed)['units'][0]['original_text'])
            self.assertEqual(self.document(client, case, typed)['auto_text_status'], 'done')

    def test_missing_ocr_engine_keeps_upload_and_reports_status(self):
        with TestClient(api.app) as client, patch('server.document_ocr.available', return_value=False):
            self.login(client); case = self.case(client)
            photo = self.upload(client, case, 'foto.png', scan(), 'image/png')
            self.assertEqual(self.document(client, case, photo)['auto_text_status'], 'ocr_unavailable')
            self.assertEqual(client.get(f'/api/cases/{case["id"]}/documents/{photo}/download').content, scan())

    def test_inbox_assignment_reads_the_photo(self):
        fake = FakeOcr()
        with TestClient(api.app) as client, patch('server.document_ocr.available', return_value=True), patch('server.ocr_routes.subprocess.run', side_effect=fake):
            self.login(client); case = self.case(client)
            entry = client.post('/api/inbox', data={'received_on': '2026-10-23', 'subject': 'Foto vom Handy', 'sender': '', 'note': ''},
                                files={'file': ('foto.jpg', scan(), 'image/jpeg')}).json()
            self.assertEqual(fake.calls, [])
            assigned = client.post(f'/api/inbox/{entry["id"]}/assign', json={'case_id': case['id'], 'expected_version': entry['version']})
            self.assertEqual(assigned.status_code, 200, assigned.text)
            self.assertEqual(fake.calls, [(1, 1, 'deu+eng')])
            self.assertEqual(self.text(client, case, entry['id'])['units'][0]['original_text'], 'Erkannter Text Seite 1')

    @unittest.skipUnless(document_ocr.available(), 'Local OCR runtime/models not installed')
    def test_real_engine_reads_an_uploaded_photo(self):
        with TestClient(api.app) as client:
            self.login(client); case = self.case(client)
            photo = self.upload(client, case, 'foto.png', scan(), 'image/png')
            self.assertIn('SYNTHETIC LOCAL OCR TEST', self.text(client, case, photo)['units'][0]['original_text'])


if __name__ == '__main__':
    unittest.main()
