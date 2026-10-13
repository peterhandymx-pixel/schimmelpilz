import hashlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from fastapi.testclient import TestClient
from server import app as api


class CaseToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.paths=api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH
        api.DATA_DIR=Path(self.temp.name);api.UPLOAD_DIR=api.DATA_DIR/'uploads';api.DB_PATH=api.DATA_DIR/'app.db';api.failed_logins.clear()

    def tearDown(self):
        api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH=self.paths;self.temp.cleanup()

    def login(self,client,email='case-tools@example.invalid'):
        client.headers['X-Schimmelpilz-Request']='1'
        response=client.post('/api/auth/register',json=dict(email=email,password='Synthetic-case-tools-2026!',audience='consumer',full_name='Synthetic Person',street='Testweg 1',postal_code='10115',city='Berlin',country='Deutschland'))
        if response.status_code==409:
            response=client.post('/api/auth/login',json={'email':email,'password':'Synthetic-case-tools-2026!'})
        self.assertIn(response.status_code,[200,201],response.text)

    def case(self,client,title='Synthetic case'):
        return client.post('/api/cases',json={'title':title,'description':'Test only.'}).json()

    def test_archive_restore_version_and_persistence(self):
        with TestClient(api.app) as client:
            self.login(client);case=self.case(client);endpoint=f'/api/cases/{case["id"]}/archive'
            self.assertEqual(case['archive_version'],0)
            archived=client.put(endpoint,json={'archived':True,'expected_version':0})
            self.assertEqual(archived.status_code,200,archived.text)
            self.assertTrue(archived.json()['archived_at']);self.assertEqual(archived.json()['archive_version'],1)
            self.assertEqual(client.put(endpoint,json={'archived':False,'expected_version':0}).status_code,409)
            self.assertEqual(client.put(endpoint,json={'archived':True,'expected_version':1}).json()['archive_version'],1)
        with TestClient(api.app) as client:
            self.login(client)
            restored=client.put(endpoint,json={'archived':False,'expected_version':1}).json()
            self.assertIsNone(restored['archived_at']);self.assertEqual(restored['archive_version'],2)
            self.assertEqual(restored['reference'],case['reference'])
            self.assertIn('case_archived',[row['action'] for row in restored['activities']])
            self.assertIn('case_restored',[row['action'] for row in restored['activities']])

    def test_export_originals_versions_hashes_and_isolation(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'other-case-tools@example.invalid')
            case=self.case(owner);second=self.case(owner,'Must not appear in export')
            data=b'%PDF-synthetic-original'
            doc=owner.post(f'/api/cases/{case["id"]}/documents',files={'file':('../test.pdf',data,'application/pdf')}).json()
            draft=owner.post(f'/api/cases/{case["id"]}/drafts',json={'body':'Original draft'}).json()
            owner.put(f'/api/cases/{case["id"]}/drafts/{draft["id"]}',json={'body':'Revised draft','expected_version':1})
            owner.post('/api/contacts',json={'name':'Synthetic contact','case_links':[{'case_id':case['id'],'role':'client'},{'case_id':second['id'],'role':'other'}]})
            endpoint=f'/api/cases/{case["id"]}/export.zip'
            self.assertEqual(other.get(endpoint).status_code,404)
            self.assertEqual(other.put(f'/api/cases/{case["id"]}/archive',json={'archived':True,'expected_version':0}).status_code,404)
            response=owner.get(endpoint)
            self.assertEqual(response.status_code,200,response.text if response.status_code!=200 else '')
            with ZipFile(io.BytesIO(response.content)) as archive:
                records=json.loads(archive.read('case.json'))
                self.assertEqual(records['case']['id'],case['id'])
                self.assertEqual(len(records['draft_versions']),2)
                self.assertEqual(records['contacts'][0]['name'],'Synthetic contact')
                self.assertNotIn(second['id'],archive.read('case.json').decode())
                self.assertFalse({'users','sessions'} & records.keys())
                self.assertNotIn('password_hash',archive.read('case.json').decode())
                self.assertEqual(archive.read('documents/'+doc['id']+'.pdf'),data)
                for entry in json.loads(archive.read('manifest.json')):
                    content=archive.read(entry['path'])
                    self.assertEqual(len(content),entry['bytes'])
                    self.assertEqual(hashlib.sha256(content).hexdigest(),entry['sha256'])
                self.assertTrue(all(not name.startswith('/') and '..' not in Path(name).parts for name in archive.namelist()))

    def test_export_fails_for_missing_or_unsafe_original(self):
        with TestClient(api.app) as client:
            self.login(client);case=self.case(client)
            doc=client.post(f'/api/cases/{case["id"]}/documents',files={'file':('test.pdf',b'%PDF-test','application/pdf')}).json()
            with api.db() as connection:
                stored=connection.execute('SELECT stored_name FROM documents WHERE id=?',(doc['id'],)).fetchone()[0]
            path=api.UPLOAD_DIR/stored;path.unlink()
            self.assertEqual(client.get(f'/api/cases/{case["id"]}/export.zip').status_code,503)
            with api.db() as connection:
                connection.execute('UPDATE documents SET stored_name=? WHERE id=?',('../outside.pdf',doc['id']))
            self.assertEqual(client.get(f'/api/cases/{case["id"]}/export.zip').status_code,503)


if __name__=='__main__':
    unittest.main()
