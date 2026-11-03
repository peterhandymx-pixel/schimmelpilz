import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from pypdf import PdfReader
from server import app as api
from server.costs import Invoice, calculate


def invoice(**changes):
    return {'title':'Synthetic invoice check','issuer':'Test supplier','invoice_number':'TEST-01',
            'billed_total':'248.00','lines':[{'description':'Test service','quantity':'2','unit_net':'100','tax_rate':'19','billed_net':'210.00','evidence':'Page 1'}],**changes}


class ArithmeticTests(unittest.TestCase):
    def test_discrepancies_and_gross_advance(self):
        result=calculate(Invoice(**invoice(credit_gross='20',billed_total='228')))
        self.assertEqual(result['net'],'200.00')
        self.assertEqual(result['tax'],'38.00')
        self.assertEqual(result['payable'],'218.00')
        self.assertEqual(result['difference'],'10.00')
        self.assertEqual(result['lines'][0]['difference'],'10.00')
        self.assertTrue(result['has_difference'])
        self.assertEqual(result['legal_assessment'],'not_performed')

    def test_decimal_rounding_by_tax_group_and_negative_credit(self):
        rows=[{'description':'A','unit_net':'0.005','tax_rate':'19'},{'description':'B','unit_net':'0.005','tax_rate':'19'},{'description':'C','unit_net':'100','tax_rate':'7'},{'description':'Credit','unit_net':'-10','tax_rate':'7'}]
        result=calculate(Invoice(**invoice(lines=rows,billed_total='96.32')))
        self.assertEqual(result['net'],'90.02')
        self.assertEqual(result['tax'],'6.30')
        self.assertEqual(result['difference'],'0.00')
        self.assertFalse(result['has_difference'])
        multiplied=calculate(Invoice(**invoice(lines=[{'description':'Manual fee','quantity':'1.3','unit_net':'100','tax_rate':'0'}],billed_total='130')))
        self.assertEqual(multiplied['payable'],'130.00')
        zero=calculate(Invoice(**invoice(lines=[{'description':'Zero','unit_net':'0','billed_net':'-0.00'}],billed_total='-0.00')))
        self.assertFalse(zero['has_difference'])
        self.assertEqual(zero['difference'],'0.00')


class CostApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.paths=api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH
        api.DATA_DIR=Path(self.temp.name);api.UPLOAD_DIR=api.DATA_DIR/'uploads';api.DB_PATH=api.DATA_DIR/'app.db'
        api.failed_logins.clear()

    def tearDown(self):
        api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH=self.paths
        self.temp.cleanup()

    def login(self,client,email='cost-test@example.invalid'):
        client.headers['X-Schimmelpilz-Request']='1'
        data=dict(email=email,password='Synthetic-cost-test-2026!',audience='consumer',full_name='Synthetic Person',street='Testweg 1',postal_code='10115',city='Berlin',country='Deutschland')
        response=client.post('/api/auth/register',json=data)
        if response.status_code==409:
            response=client.post('/api/auth/login',json={'email':email,'password':data['password']})
        self.assertIn(response.status_code,[200,201],response.text)

    def case(self,client):
        return client.post('/api/cases',json={'title':'Synthetic cost case','description':'Test data only.'}).json()['id']

    def test_save_restart_versions_pdf_and_activity(self):
        with TestClient(api.app) as client:
            self.login(client);case_id=self.case(client)
            payload={**invoice(), 'case_id':case_id}
            preview=client.post('/api/cost-reviews/calculate',json=invoice())
            self.assertEqual(preview.status_code,200,preview.text)
            saved=client.post('/api/cost-reviews',json=payload)
            self.assertEqual(saved.status_code,201,saved.text);saved=saved.json()
            changed=client.put('/api/cost-reviews/'+saved['id'],json={**payload,'billed_total':'238','expected_version':1})
            self.assertEqual(changed.status_code,200,changed.text)
            self.assertEqual(changed.json()['version'],2)
            self.assertEqual(client.put('/api/cost-reviews/'+saved['id'],json={**payload,'expected_version':1}).status_code,409)
            history=client.get('/api/cost-reviews/'+saved['id']+'/versions').json()
            self.assertEqual([row['version'] for row in history],[2,1])
            self.assertEqual(history[1]['result']['difference'],'10.00')
            self.assertEqual(history[0]['result']['difference'],'0.00')
            report=client.get('/api/cost-reviews/'+saved['id']+'/report.pdf?version=1&lang=en')
            self.assertEqual(report.status_code,200,report.text if report.status_code!=200 else '')
            text='\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(report.content)).pages)
            self.assertIn('248.00 EUR',text);self.assertIn('10.00 EUR',text)
            self.assertIn('Version 1',text);self.assertIn('No legal approval',text)
            self.assertEqual(client.get('/api/cost-reviews/'+saved['id']+'/report.pdf?version=99').status_code,404)
            self.assertIn('cost_review_saved',[row['action'] for row in client.get('/api/cases/'+case_id).json()['activities']])
        with TestClient(api.app) as client:
            self.login(client)
            rows=client.get('/api/cost-reviews').json()
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['version'],2)
            self.assertEqual(rows[0]['result']['payable'],'238.00')

    def test_ownership_document_links_and_atomic_edits(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'foreign-cost@example.invalid')
            case_id=self.case(owner);foreign=self.case(other);second=self.case(owner)
            doc=owner.post(f'/api/cases/{case_id}/documents',files={'file':('synthetic.pdf',b'%PDF-test','application/pdf')}).json()
            payload={**invoice(),'case_id':case_id,'document_id':doc['id']}
            saved=owner.post('/api/cost-reviews',json=payload)
            self.assertEqual(saved.status_code,201,saved.text);saved=saved.json()
            self.assertEqual(other.get('/api/cost-reviews').json(),[])
            self.assertEqual(other.get('/api/cost-reviews?case_id='+case_id).status_code,404)
            for suffix in ['/versions','/report.pdf']:
                self.assertEqual(other.get('/api/cost-reviews/'+saved['id']+suffix).status_code,404)
            self.assertEqual(other.put('/api/cost-reviews/'+saved['id'],json={**payload,'expected_version':1}).status_code,404)
            self.assertEqual(owner.post('/api/cost-reviews',json={**payload,'case_id':foreign}).status_code,404)
            self.assertEqual(owner.post('/api/cost-reviews',json={**payload,'case_id':second}).status_code,404)
            self.assertEqual(owner.put('/api/cost-reviews/'+saved['id'],json={**payload,'case_id':second,'document_id':None,'expected_version':1}).status_code,422)
            self.assertEqual(owner.get('/api/cost-reviews').json()[0]['version'],1)

    def test_validation_and_guards(self):
        with TestClient(api.app) as client:
            self.assertEqual(client.get('/api/cost-reviews').status_code,401)
            self.assertEqual(client.post('/api/cost-reviews/calculate',json=invoice()).status_code,403)
            self.login(client)
            for field,value in [('unit_net','NaN'),('unit_net','Infinity'),('unit_net','1e6'),('unit_net','1,25'),('unit_net',1.25),('tax_rate','101'),('quantity','-1'),('quantity','1000001'),('billed_net','0.001')]:
                row={**invoice()['lines'][0],field:value}
                self.assertEqual(client.post('/api/cost-reviews/calculate',json=invoice(lines=[row])).status_code,422,(field,value))
            for changes in [{'lines':[]},{'credit_gross':'-1'},{'billed_total':'1.001'},{'title':' '},{'invoice_date':'invalid'},{'currency':'XXX'},{'lines':invoice()['lines']*101}]:
                self.assertEqual(client.post('/api/cost-reviews/calculate',json=invoice(**changes)).status_code,422,changes)
            self.assertEqual(client.get('/api/cost-reviews').json(),[])


if __name__=='__main__':
    unittest.main()


class DisplayDateTests(unittest.TestCase):
    def test_documents_use_german_day_month_year(self):
        from server.dates import display_date
        self.assertEqual(display_date('2026-11-05'), '05.11.2026')
        self.assertEqual(display_date('2026-11-05', de=False), '05/11/2026')
        self.assertEqual(display_date('2026-10-21T22:30:00+00:00'), '22.10.2026')  # late UTC evening is already the next day in Berlin
        self.assertEqual(display_date(None), '-')
        self.assertEqual(display_date('not a date'), 'not a date')
