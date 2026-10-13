import io
import unittest
from pypdf import PdfReader
from fastapi.testclient import TestClient
from server import app as api
from server import route_plans as plans
from server.tests import test_case_tools


def payload(**changes):
    return {'goal':'Synthetic payment claim for test data only.','category':'civil','claim_value':'10000','filing_date':'2026-10-13','special_jurisdiction':False,'opponent_place':'Synthetic address Berlin',**changes}


class RouteUnitTests(unittest.TestCase):
    def test_value_boundary_special_cases_history_and_cross_border(self):
        district=plans.prepare(plans.PlanInput(**payload()),'DE')
        regional=plans.prepare(plans.PlanInput(**payload(claim_value='10000.01')),'DE')
        self.assertEqual(district['court_candidate'],'Amtsgericht')
        self.assertEqual(regional['court_candidate'],'Landgericht')
        self.assertIn('§ 78',regional['representation'])
        for changes,jurisdiction in [({'special_jurisdiction':True},'DE'),({'filing_date':'2025-12-31'},'DE'),({'filing_date':None},'DE'),({'cross_border':True},'DE'),({},'MX'),({'claim_value':None},'DE')]:
            result=plans.prepare(plans.PlanInput(**payload(**changes)),jurisdiction)
            self.assertNotIn(result['court_candidate'],['Amtsgericht','Landgericht'])
            self.assertFalse(result['legal_approval'])
        foreign=plans.prepare(plans.PlanInput(**payload()),'MX')
        self.assertEqual(foreign['sources'],[])

    def test_tenancy_exclusive_route_and_missing_address(self):
        result=plans.prepare(plans.PlanInput(**payload(category='tenancy',claim_value='25000',property_place='Synthetic premises Berlin')),'DE')
        self.assertIn('Amtsgericht',result['court_candidate'])
        self.assertIn('§ 29a',result['venue'])
        self.assertIn('Ausnahmen',result['venue'])
        self.assertTrue(any(source['url'].endswith('/__29a.html') for source in result['sources']))


class RouteApiTests(test_case_tools.CaseToolsTests):
    test_archive_restore_version_and_persistence=None
    test_export_originals_versions_hashes_and_isolation=None
    test_export_fails_for_missing_or_unsafe_original=None

    def test_owned_versioned_working_paper_pdf_and_export(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'route-other@example.invalid');case=self.case(owner)
            base=f'/api/cases/{case["id"]}/route-plan'
            self.assertIsNone(owner.get(base).json())
            self.assertEqual(other.get(base).status_code,404)
            preview=owner.post(base+'/preview',json=payload())
            self.assertEqual(preview.status_code,200,preview.text)
            self.assertIsNone(owner.get(base).json())
            first=owner.put(base,json=payload(expected_version=0))
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.json()['version'],1)
            self.assertEqual(owner.put(base,json=payload(expected_version=0)).status_code,409)
            second=owner.put(base,json=payload(expected_version=1,claim_value='10001'))
            self.assertEqual(second.json()['version'],2)
            history=owner.get(base+'/versions').json()
            self.assertEqual(history[1]['result']['court_candidate'],'Amtsgericht')
            self.assertEqual(history[0]['result']['court_candidate'],'Landgericht')
            pdf=owner.get(base+'/report.pdf?version=1')
            self.assertEqual(pdf.status_code,200)
            text='\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
            self.assertIn('Amtsgericht',text);self.assertIn('2026-10-13',text)
            self.assertEqual(other.get(base+'/report.pdf').status_code,404)
            self.assertEqual(other.put(base,json=payload()).status_code,404)
            self.assertEqual(other.get(base+'/versions').status_code,404)
            self.assertEqual(owner.get(f'/api/cases/{case["id"]}/export.zip').status_code,200)


if __name__=='__main__':
    unittest.main()
