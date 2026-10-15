import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image,ImageDraw,ImageFont
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import reportlab
from server import app as api,document_ocr as ocr
from server.document_context import select_sources
from server.tests import test_case_tools


def scan():
    image=Image.new('RGB',(1600,500),'white')
    font=ImageFont.truetype(str(Path(reportlab.__file__).parent/'fonts/Vera.ttf'),52)
    ImageDraw.Draw(image).text((80,100),'SYNTHETIC LOCAL OCR TEST',font=font,fill='black')
    output=io.BytesIO();image.save(output,format='PNG');image.close();return output.getvalue()


class OcrWorkerTests(unittest.TestCase):
    @unittest.skipUnless(ocr.available(),'Local OCR runtime/models not installed')
    def test_real_image_and_selected_scanned_pdf_page(self):
        with TemporaryDirectory() as temporary:
            path=Path(temporary)/'test.png';path.write_bytes(scan())
            result=ocr.recognize(path,1,1,'eng')
            self.assertIn('SYNTHETIC LOCAL OCR TEST',result['units'][0]['text'])
            self.assertEqual(result['unit_kind'],'image')
            pdf=io.BytesIO();writer=canvas.Canvas(pdf)
            for _ in range(2):
                writer.drawImage(ImageReader(io.BytesIO(scan())),40,550,width=510,height=160);writer.showPage()
            writer.save();paper=Path(temporary)/'scan.pdf';paper.write_bytes(pdf.getvalue())
            result=ocr.recognize(paper,2,1,'eng')
            self.assertEqual(result['units'][0]['unit_no'],2)
            self.assertIn('SYNTHETIC LOCAL OCR TEST',result['units'][0]['text'])
            self.assertTrue(result['truncated'])
            self.assertEqual(result['total_pages'],2)
            self.assertEqual(result['models']['eng'],ocr.MODELS['eng'])
            with self.assertRaisesRegex(ValueError,'invalid_range'):ocr.recognize(paper,3,1,'eng')


class OcrApiTests(test_case_tools.CaseToolsTests):
    test_archive_restore_version_and_persistence=None
    test_export_originals_versions_hashes_and_isolation=None
    test_export_fails_for_missing_or_unsafe_original=None

    def test_review_gate_provenance_original_bytes_and_no_overwrite(self):
        with TestClient(api.app) as client:
            self.login(client);case=self.case(client);original=scan()
            doc=client.post(f'/api/cases/{case["id"]}/documents',files={'file':('scan.png',original,'image/png')}).json()
            base=f'/api/cases/{case["id"]}/documents/{doc["id"]}'
            result={'units':[{'unit_no':1,'text':'OCR machine text','confidence':90}],'truncated':False,'unit_kind':'image','total_pages':1,'engine':'tesseract.js-7.0.0','language':'eng','models':{'eng':ocr.MODELS['eng']}}
            with patch('server.document_ocr.available',return_value=True),patch('server.ocr_routes.subprocess.run',return_value=SimpleNamespace(stdout=json.dumps(result).encode())):
                response=client.post(base+'/ocr',json={'language':'eng'})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['ocr']['written_units'],1)
                self.assertIsNone(response.json()['units'][0]['reviewed_at'])
                with api.db() as connection:self.assertEqual(select_sources(connection,case['id'],[doc['id']],'text'),[])
                reviewed=client.put(base+'/text/1',json={'text':'Reviewed OCR text','reviewed':True})
                self.assertEqual(reviewed.status_code,200,reviewed.text)
                result['units'][0]['text']='Must not replace reviewed text'
                again=client.post(base+'/ocr',json={'language':'eng'})
                self.assertEqual(again.json()['ocr']['written_units'],0)
                self.assertEqual(again.json()['ocr']['skipped_units'],[1])
                self.assertEqual(again.json()['units'][0]['reviewed_text'],'Reviewed OCR text')
            with api.db() as connection:
                source=select_sources(connection,case['id'],[doc['id']],'text')[0]
                self.assertEqual(source['extraction_origin'],'ocr');self.assertTrue(source['ocr_run_id'])
                self.assertEqual(source['unit_kind'],'image')
            self.assertEqual(client.get(base+'/download').content,original)

    def test_account_and_format_bounds_unavailable_and_failure_leave_text(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'ocr-foreign@example.invalid');case=self.case(owner)
            doc=owner.post(f'/api/cases/{case["id"]}/documents',files={'file':('scan.png',scan(),'image/png')}).json()
            base=f'/api/cases/{case["id"]}/documents/{doc["id"]}'
            self.assertEqual(other.post(base+'/ocr',json={}).status_code,404)
            self.assertEqual(other.get(base+'/ocr/status').status_code,404)
            for payload in [{'count':13},{'start_page':80,'count':2},{'language':'invalid'},{'start_page':2}]:
                self.assertEqual(owner.post(base+'/ocr',json=payload).status_code,422,payload)
            with patch('server.document_ocr.available',return_value=False):
                self.assertEqual(owner.post(base+'/ocr',json={}).status_code,503)
            with patch('server.document_ocr.available',return_value=True),patch('server.ocr_routes.subprocess.run',return_value=SimpleNamespace(stdout=b'{"error_code":"ocr_failed"}')):
                self.assertEqual(owner.post(base+'/ocr',json={}).status_code,503)
            self.assertEqual(owner.get(base+'/text').json()['units'],[])
            self.assertEqual(owner.get(base+'/download').content,scan())


if __name__=='__main__':unittest.main()
