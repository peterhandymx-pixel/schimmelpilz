import unittest
from decimal import Decimal, ROUND_CEILING
from fastapi.testclient import TestClient
from server import app as api
from server import fee_tables as fees
from server.tests import test_case_tools


def basis(statute='rvg',value='5000'):
    return {'statute':statute,'version':fees.VERSION,'value':value,'applicability_confirmed':True,'applicability_note':'Synthetic test: selected version reviewed separately.'}


class FeeTableUnitTests(unittest.TestCase):
    def test_all_brackets_against_statutory_step_formula(self):
        for statute in ['rvg','gkg','famgkg']:
            steps=[(2000,500,'41.50'),(10000,1000,'59.50'),(25000,3000,'55'),(50000,5000,'86'),(200000,15000,'99.50'),(500000,30000,'140')] if statute=='rvg' else [(2000,500,'21'),(10000,1000,'22.50'),(25000,3000,'30.50'),(50000,5000,'40.50'),(200000,15000,'140'),(500000,30000,'210')]
            def rule(value):
                amount=Decimal('51.50' if statute=='rvg' else '40');lower=500
                for upper,increment,increase in steps:
                    span=max(Decimal(0),min(value,Decimal(upper))-lower)
                    amount+=(span/increment).to_integral_value(rounding=ROUND_CEILING)*Decimal(increase)
                    if value<=upper:
                        break
                    lower=upper
                return amount
            for index,value in enumerate(fees.VALUES):
                for candidate in [Decimal(value),Decimal(fees.VALUES[index-1])+Decimal('0.01') if index else Decimal('0.01')]:
                    result=fees.lookup(fees.FeeBasis(**basis(statute,str(candidate))))
                    self.assertEqual(Decimal(result['base_fee']),rule(candidate),(statute,candidate))
                    self.assertEqual(result['bracket'],str(value))
        self.assertEqual(fees.lookup(fees.FeeBasis(**basis()))['base_fee'],'354.50')


class FeeTableApiTests(test_case_tools.CaseToolsTests):
    test_archive_restore_version_and_persistence=None
    test_export_originals_versions_hashes_and_isolation=None
    test_export_fails_for_missing_or_unsafe_original=None

    def test_table_line_provenance_and_rejection_of_tampering(self):
        with TestClient(api.app) as client:
            self.login(client);case=self.case(client)
            result=client.post('/api/fee-tables/calculate',json=basis())
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['base_fee'],'354.50')
            payload={'title':'Synthetic sourced fee','case_id':case['id'],'kind':'lawyer','billed_total':'460.85','lines':[{'description':'Fee basis, manual multiplier','quantity':'1.3','unit_net':'354.50','fee_basis':basis()}]}
            saved=client.post('/api/cost-reviews',json=payload)
            self.assertEqual(saved.status_code,201,saved.text)
            source=saved.json()['result']['lines'][0]['fee_source']
            self.assertEqual(source['source']['table'],'https://www.gesetze-im-internet.de/rvg/anlage_2.html')
            self.assertEqual(source['source_checked_on'],'2026-10-13')
            self.assertEqual(len(source['table_sha256']),64)
            self.assertEqual(saved.json()['result']['difference'],'0.00')
            changed={**payload,'lines':[{**payload['lines'][0],'unit_net':'999'}]}
            self.assertEqual(client.post('/api/cost-reviews',json=changed).status_code,422)
            self.assertEqual(client.post('/api/cost-reviews',json={**payload,'currency':'MXN'}).status_code,422)
            with api.db() as connection:
                connection.execute('UPDATE cases SET details=? WHERE id=?',('{"jurisdiction":"MX"}',case['id']))
            self.assertEqual(client.post('/api/cost-reviews',json=payload).status_code,422)
            self.assertEqual(len(client.get('/api/cost-reviews').json()),1)

    def test_input_scope_and_explicit_review(self):
        with TestClient(api.app) as client:
            client.headers['X-Schimmelpilz-Request']='1'
            self.assertEqual(client.post('/api/fee-tables/calculate',json=basis()).status_code,401)
            self.login(client)
            for patch in [{'value':'500000.01'},{'value':'0'},{'value':'NaN'},{'value':5000},{'version':'old'},{'applicability_confirmed':False},{'applicability_note':'          '}]:
                self.assertEqual(client.post('/api/fee-tables/calculate',json={**basis(),**patch}).status_code,422,patch)


if __name__=='__main__':
    unittest.main()
