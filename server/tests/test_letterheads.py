import io
import unittest
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from server import app as api
from server.letterheads import compose_pdf, normalize, office_path


def paper(label='HEADER VERSION ONE', count=2):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(210 * mm, 297 * mm))
    for index in range(count):
        pdf.drawString(25 * mm, 275 * mm, label if index == 0 else 'CONTINUATION HEADER')
        pdf.drawString(25 * mm, 15 * mm, 'SYNTHETIC FOOTER')
        pdf.showPage()
    pdf.save()
    return output.getvalue()


class LetterheadTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.paths = api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH
        api.DATA_DIR = Path(self.temp.name)
        api.UPLOAD_DIR = api.DATA_DIR / 'uploads'
        api.DB_PATH = api.DATA_DIR / 'app.db'
        api.failed_logins.clear()

    def tearDown(self):
        api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH = self.paths
        self.temp.cleanup()

    def register(self, client, email='letterhead@example.invalid', audience='business'):
        client.headers['X-Schimmelpilz-Request'] = '1'
        payload = dict(email=email, password='Only-a-synthetic-test-2026', audience=audience, organisation='Example only', full_name='Example Person', street='Example 1', postal_code='10115', city='Berlin', country='Deutschland', profile={'legal_form':'GmbH' if audience == 'business' else 'PartG', 'role':'management' if audience == 'business' else 'staff', 'register_number':'TEST-ONLY', 'bar_association':'Example chamber'})
        response = client.post('/api/auth/register', json=payload)
        if response.status_code == 409:
            response = client.post('/api/auth/login', json=dict(email=email, password=payload['password']))
        self.assertIn(response.status_code, [200,201], response.text)
        return response.json()

    def upload(self, client, data=None):
        response = client.post('/api/auth/letterheads', files={'file':('Letterhead.pdf', data or paper(), 'application/pdf')})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_profiles_versions_exports_and_account_isolation(self):
        with TestClient(api.app) as client:
            user = self.register(client)
            self.assertEqual(user['profile']['register_number'], 'TEST-ONLY')
            self.assertIsNone(user['letterhead_id'])
            head = self.upload(client)
            path = f'/api/auth/letterheads/{head["id"]}'
            self.assertEqual(client.put(path + '/activate', json={'confirmed':False}).status_code, 422)
            self.assertEqual(client.put(path + '/activate', json={'confirmed':True, 'top_mm':160, 'bottom_mm':120}).status_code, 422)
            self.assertEqual(client.put(path + '/activate', json={'confirmed':True}).status_code, 200)
            self.assertEqual(client.put(path + '/activate', json={'confirmed':True}).status_code, 409)
            case = client.post('/api/cases', json={'title':'Synthetic letterhead case','description':'Example only'}).json()
            draft = client.post(f'/api/cases/{case["id"]}/drafts', json={'body':'DRAFT BODY ONE <literal text> ÄÖÜ ß €','kind':'claim'}).json()
            self.assertEqual(draft['letterhead_id'], head['id'])
            endpoint = f'/api/cases/{case["id"]}/drafts/{draft["id"]}/pdf'
            first = client.get(endpoint)
            self.assertEqual(first.status_code, 200, first.text[:100])
            self.assertIn('HEADER VERSION ONE', PdfReader(io.BytesIO(first.content)).pages[0].extract_text())
            second_head = self.upload(client, paper('HEADER VERSION TWO', count=1))
            client.put(f'/api/auth/letterheads/{second_head["id"]}/activate', json={'confirmed':True})
            retained = PdfReader(io.BytesIO(client.get(endpoint).content)).pages[0].extract_text()
            self.assertIn('HEADER VERSION ONE', retained)
            self.assertNotIn('HEADER VERSION TWO', retained)
            preview = client.post(f'/api/cases/{case["id"]}/drafts/preview-pdf', json={'draft_id':draft['id'], 'body':'UNSAVED EDITOR TEXT', 'use_current_letterhead':True})
            self.assertIn('UNSAVED EDITOR TEXT', PdfReader(io.BytesIO(preview.content)).pages[0].extract_text())
            client.put(f'/api/cases/{case["id"]}/drafts/{draft["id"]}', json={'body':'REVISED BODY','use_current_letterhead':True})
            revised = PdfReader(io.BytesIO(client.get(endpoint).content)).pages[0].extract_text()
            self.assertIn('HEADER VERSION TWO', revised)
            self.assertIn('REVISED BODY', revised)
            self.register(client, 'lawfirm@example.invalid', 'law_firm')
            self.assertEqual(client.get(path + '/pdf').status_code, 404)
            self.assertEqual(client.post(path + '/preview', json={}).status_code, 404)
            self.assertEqual(client.put(path + '/activate', json={'confirmed':True}).status_code, 404)
            self.assertEqual(client.get(endpoint).status_code, 404)
        with TestClient(api.app) as client:
            self.register(client)
            self.assertEqual(client.get('/api/auth/me').json()['letterhead_id'], second_head['id'])
            self.assertEqual(client.get('/api/auth/me').json()['profile']['legal_form'], 'GmbH')
            self.assertIn('HEADER VERSION TWO', PdfReader(io.BytesIO(client.get(endpoint).content)).pages[0].extract_text())

    def test_continuation_pages_do_not_accumulate_prior_body_text(self):
        source = Path(self.temp.name) / 'paper.pdf'
        original = paper()
        source.write_bytes(original)
        result = compose_pdf('\n'.join(f'UNIQUE LINE {index:03d}' for index in range(90)), source, api.LetterheadLayout().model_dump())
        pages = PdfReader(io.BytesIO(result)).pages
        self.assertGreaterEqual(len(pages), 3)
        extracted = [page.extract_text() for page in pages]
        self.assertIn('HEADER VERSION ONE', extracted[0])
        for text in extracted[1:]:
            self.assertIn('CONTINUATION HEADER', text)
            self.assertNotIn('UNIQUE LINE 000', text)
        # Every body line appears exactly once across all pages, including repeated template pages.
        all_text = '\n'.join(extracted)
        for index in range(90):
            self.assertEqual(all_text.count(f'UNIQUE LINE {index:03d}'), 1)
        self.assertEqual(all_text.count('SYNTHETIC FOOTER'), len(pages))
        self.assertEqual(source.read_bytes(), original)

    def test_invalid_upload_and_unavailable_converter_leave_active_head_unchanged(self):
        with TestClient(api.app) as client:
            self.register(client)
            head = self.upload(client)
            client.put(f'/api/auth/letterheads/{head["id"]}/activate', json={'confirmed':True})
            for filename, data, expected in [('bad.pdf',b'not a pdf',422), ('three.pdf',paper(count=3),422), ('bad.exe',b'bad',415), ('empty.pdf',b'',422), ('too-big.pdf',b'x' * (api.MAX_UPLOAD_BYTES+1),413)]:
                self.assertEqual(client.post('/api/auth/letterheads',files={'file':(filename,data)}).status_code, expected)
            with patch('server.letterheads.office_path', return_value=None):
                self.assertEqual(client.post('/api/auth/letterheads', files={'file':('test.docx', b'example')}).status_code, 503)
            self.assertEqual(client.get('/api/auth/letterheads').json()['active_id'], head['id'])

    @unittest.skipUnless(office_path(), 'LibreOffice is not installed')
    def test_word_letterhead_is_converted_locally(self):
        source = Path(self.temp.name) / 'word.docx'
        with ZipFile(source, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>SYNTHETIC WORD LETTERHEAD</w:t></w:r></w:p><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>')
        output = source.with_suffix('.pdf')
        geometry = normalize(source, output)
        self.assertEqual(geometry['pages'], 1)
        self.assertIn('SYNTHETIC WORD LETTERHEAD', PdfReader(output).pages[0].extract_text())
        subprocess.run([office_path(), '-env:UserInstallation=' + (Path(self.temp.name) / 'doc-conversion-profile').as_uri(), '--headless', '--convert-to', 'doc:MS Word 97', '--outdir', self.temp.name, str(source)], check=True, timeout=60, capture_output=True)
        legacy = source.with_suffix('.doc')
        self.assertTrue(legacy.is_file())
        legacy_pdf = Path(self.temp.name) / 'legacy.pdf'
        self.assertEqual(normalize(legacy, legacy_pdf)['pages'], 1)
        self.assertIn('SYNTHETIC WORD LETTERHEAD', PdfReader(legacy_pdf).pages[0].extract_text())


if __name__ == '__main__':
    unittest.main()
