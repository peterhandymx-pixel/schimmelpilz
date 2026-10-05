import io
import uuid
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from server import app as api
from server.document_extraction import extract


def synthetic_pdf():
    writer = PdfWriter()
    for text in ["SYNTHETIC INVOICE TEST-778. Total: 480 EUR.", "UNREVIEWED PRIVATE MARKER. Do not supply this page."]:
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 50 780 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class DocumentResearchTests(unittest.TestCase):
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

    def login(self, client, email='document-test@example.invalid'):
        client.headers['X-Schimmelpilz-Request'] = '1'
        payload = {'email': email, 'password': 'Synthetic-testing-password-2026', 'audience': 'consumer', 'full_name': 'Test Person', 'street': 'Example 1', 'postal_code': '10115', 'city': 'Berlin', 'country': 'Deutschland'}
        response = client.post('/api/auth/register', json=payload)
        if response.status_code == 409:
            response = client.post('/api/auth/login', json={'email': email, 'password': payload['password']})
        self.assertIn(response.status_code, [200, 201], response.text)

    def case(self, client):
        response = client.post('/api/cases', json={'title': 'Synthetic document test', 'description': 'Example only, no real client data.'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def test_pdf_review_selection_and_immutable_generation_sources(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id, other_case = self.case(client), self.case(client)
            document = client.post(f'/api/cases/{case_id}/documents', files={'file': ('Invoice.pdf', synthetic_pdf(), 'application/pdf')}).json()
            base = f'/api/cases/{case_id}/documents/{document["id"]}'
            result = client.post(base + '/extract')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['extraction']['status'], 'ready')
            self.assertEqual(len(result.json()['units']), 2)
            self.assertIn('480 EUR', result.json()['units'][0]['original_text'])
            payload = {'request_id': str(uuid.uuid4()), 'question': 'What is the invoice total?', 'document_ids': [document['id']]}
            self.assertEqual(client.post(f'/api/cases/{case_id}/research', json=payload).status_code, 422)
            reviewed = 'SYNTHETIC INVOICE TEST-778. Total: 480 EUR. CORRECTED TEXT.'
            self.assertEqual(client.put(base + '/text/1', json={'text': reviewed, 'reviewed': True}).status_code, 200)
            self.assertEqual(client.put(base + '/text/2', json={'text': '  ', 'reviewed': True}).status_code, 422)
            model_result = {'answer': '480 EUR (Invoice.pdf, PDF page 1).', 'input_tokens': 50, 'output_tokens': 20, 'truncated': False}
            with patch.object(api, 'generate_answer', return_value=model_result) as model:
                result = client.post(f'/api/cases/{case_id}/research', json=payload)
                self.assertEqual(result.status_code, 201, result.text)
                messages = str(model.call_args.args[0])
                self.assertIn('CORRECTED TEXT', messages)
                self.assertNotIn('UNREVIEWED PRIVATE MARKER', messages)
                saved = result.json()
                self.assertEqual(saved['sources'][0]['unit_no'], 1)
                self.assertEqual(saved['sources'][0]['text'], reviewed)
                self.assertEqual(saved['sources'][0]['unit_kind'], 'page')
                self.assertEqual(len(saved['sources'][0]['text_sha256']), 64)
                client.put(base + '/text/1', json={'text': 'Changed later', 'reviewed': False})
                self.assertEqual(client.post(base + '/extract').json()['units'][0]['reviewed_text'], 'Changed later')
                repeated = client.post(f'/api/cases/{case_id}/research', json=payload)
                self.assertEqual(repeated.json()['sources'], saved['sources'])
                self.assertEqual(model.call_count, 1)
                conflict = client.post(f'/api/cases/{case_id}/research', json={**payload, 'document_ids': []})
                self.assertEqual(conflict.status_code, 409)
                self.assertEqual(client.post(f'/api/cases/{case_id}/research', json={**payload, 'request_id': str(uuid.uuid4())}).status_code, 422)
                self.assertEqual(client.post(f'/api/cases/{other_case}/research', json={**payload, 'request_id': str(uuid.uuid4())}).status_code, 404)
            self.assertEqual(client.get(f'/api/cases/{other_case}/documents/{document["id"]}/text').status_code, 404)
            self.login(client, 'other-account@example.invalid')
            for route, method in [('/text', client.get), ('/extract', client.post)]:
                self.assertEqual(method(base + route).status_code, 404)
        with TestClient(api.app) as client:
            self.login(client)
            history = client.get(f'/api/cases/{case_id}/research').json()
            self.assertEqual(history[0]['sources'], saved['sources'])
            self.assertEqual(client.get(base + '/text').json()['units'][0]['reviewed_text'], 'Changed later')

    def test_docx_sections_blank_pdf_and_processing_limits(self):
        path = Path(self.temp.name) / 'Example.docx'
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>First paragraph</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body></w:document>'
        with ZipFile(path, 'w') as archive:
            archive.writestr('word/document.xml', xml)
        result = extract(path)
        self.assertEqual(result['unit_kind'], 'section')
        self.assertEqual([unit['text'] for unit in result['units']], ['First paragraph', 'Second paragraph'])
        with patch('server.document_extraction.MAX_UNITS', 1):
            limited = extract(path)
            self.assertTrue(limited['truncated'])
            self.assertEqual(len(limited['units']), 1)
        with ZipFile(path, 'w') as archive:
            archive.writestr('word/document.xml', '<!DOCTYPE x [<!ENTITY bad "example">]>' + xml)
        with self.assertRaisesRegex(ValueError, 'invalid_document'):
            extract(path)
        pdf = Path(self.temp.name) / 'Blank.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.write(pdf)
        self.assertEqual(extract(pdf)['status'], 'no_text')
        writer.encrypt('synthetic-secret')
        writer.write(pdf)
        with self.assertRaisesRegex(ValueError, 'encrypted'):
            extract(pdf)
        self.assertEqual(extract(Path('Scan.jpg'))['status'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
