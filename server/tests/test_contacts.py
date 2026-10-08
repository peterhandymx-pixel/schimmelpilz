import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from server import app as api


class ContactTests(unittest.TestCase):
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

    def login(self, client, email='contact-test@example.invalid'):
        client.headers['X-Schimmelpilz-Request'] = '1'
        data = dict(email=email,password='Synthetic-contact-test-2026!',audience='consumer',full_name='Synthetic Person',street='Testweg 1',postal_code='10115',city='Berlin',country='Deutschland')
        result = client.post('/api/auth/register', json=data)
        if result.status_code == 409:
            result = client.post('/api/auth/login', json={'email': email, 'password':data['password']})
        self.assertIn(result.status_code, [200,201], result.text)

    def case(self, client, title='Synthetic contact case'):
        result = client.post('/api/cases', json={'title':title,'description':'Only synthetic contact testing, no real parties.','details':{'client_name':'Original case name'}})
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def test_multiple_case_roles_persistence_and_draft_address_snapshot(self):
        with TestClient(api.app) as client:
            self.login(client)
            first, second = self.case(client), self.case(client,'Second synthetic case')
            payload = {'name':'Synthetic Court','kind':'court','attention':'Test department','address':'Teststraße 10\n10115 Berlin','email':'court@example.invalid','note':'Internal note must stay out of the address block','case_links':[{'case_id':first['id'],'role':'court'},{'case_id':second['id'],'role':'other'}]}
            contact = client.post('/api/contacts', json=payload)
            self.assertEqual(contact.status_code,201,contact.text)
            contact = contact.json()
            recipient = '\n'.join([contact['name'],contact['attention'],contact['address']])
            draft = client.post(f"/api/cases/{first['id']}/drafts",json={'body':'Synthetic letter\n'+recipient,'recipient':recipient}).json()
            updated = client.put('/api/contacts/'+contact['id'],json={**payload,'address':'New test address','expected_version':1,'case_links':[{'case_id':second['id'],'role':'counsel'}]})
            self.assertEqual(updated.status_code,200,updated.text)
            self.assertEqual(updated.json()['version'],2)
            self.assertEqual(client.get(f"/api/cases/{first['id']}").json()['details']['client_name'],'Original case name')
            self.assertEqual(client.get(f"/api/cases/{first['id']}").json()['drafts'][0]['recipient'],recipient)
            self.assertIn('contact_unlinked',[event['action'] for event in client.get('/api/cases/'+first['id']).json()['activities']])
        with TestClient(api.app) as client:
            self.login(client)
            saved = client.get('/api/contacts').json()
            self.assertEqual(len(saved),1)
            self.assertEqual(saved[0]['address'],'New test address')
            self.assertEqual(saved[0]['case_links'][0]['case_id'],second['id'])
            self.assertEqual(saved[0]['case_links'][0]['role'],'counsel')
            self.assertEqual(client.get(f"/api/cases/{first['id']}").json()['drafts'][0]['id'],draft['id'])

    def test_account_isolation_foreign_link_rollback_and_stale_edits(self):
        with TestClient(api.app) as owner, TestClient(api.app) as other:
            self.login(owner)
            self.login(other,'second-contact@example.invalid')
            case = self.case(owner)
            foreign_case = self.case(other)
            payload = {'name':'Owned contact','case_links':[{'case_id':case['id'],'role':'client'}]}
            contact = owner.post('/api/contacts',json=payload).json()
            self.assertEqual(other.get('/api/contacts').json(),[])
            self.assertEqual(other.get('/api/contacts/'+contact['id']).status_code,404)
            self.assertEqual(other.put('/api/contacts/'+contact['id'],json={**payload,'expected_version':1}).status_code,404)
            forbidden = owner.put('/api/contacts/'+contact['id'],json={'name':'Must not save','expected_version':1,'case_links':[{'case_id':foreign_case['id'],'role':'client'}]})
            self.assertEqual(forbidden.status_code,404)
            unchanged = owner.get('/api/contacts/'+contact['id']).json()
            self.assertEqual(unchanged['name'],'Owned contact')
            self.assertEqual(unchanged['case_links'][0]['case_id'],case['id'])
            self.assertEqual(owner.put('/api/contacts/'+contact['id'],json={**payload,'name':'Updated','expected_version':1}).status_code,200)
            self.assertEqual(owner.put('/api/contacts/'+contact['id'],json={**payload,'name':'Stale overwrite','expected_version':1}).status_code,409)
            self.assertEqual(owner.get('/api/contacts/'+contact['id']).json()['name'],'Updated')
            self.assertEqual(owner.post('/api/contacts',json={'name':'No foreign link','case_links':[{'case_id':foreign_case['id'],'role':'court'}]}).status_code,404)
            self.assertEqual(len(owner.get('/api/contacts').json()),1)

    def test_validation_authentication_and_request_guard(self):
        with TestClient(api.app) as client:
            self.assertEqual(client.get('/api/contacts').status_code,401)
            self.assertEqual(client.post('/api/contacts',json={'name':'Blocked'}).status_code,403)
            client.headers['X-Schimmelpilz-Request']='1'
            self.assertEqual(client.post('/api/contacts',json={'name':'Blocked'}).status_code,401)
            self.login(client)
            case = self.case(client)
            for payload in [{'name':'  '},{'name':'A','email':'bad email'},{'name':'A','address':'a'*501},{'name':'A','kind':'invalid'},{'name':'A\x00B'},{'name':'A','case_links':[{'case_id':case['id']},{'case_id':case['id']}]},{'name':'A','case_links':[{'case_id':case['id'],'role':'invalid'}]}]:
                self.assertEqual(client.post('/api/contacts',json=payload).status_code,422,payload)
            self.assertEqual(client.get('/api/contacts').json(),[])


if __name__ == '__main__':
    unittest.main()
