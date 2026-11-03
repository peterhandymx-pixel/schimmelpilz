import hashlib
import sqlite3
import unittest
import uuid
from unittest.mock import patch
from server.document_context import select_sources
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from server import app as api
from server.tests.test_document_research import synthetic_pdf


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.paths=api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH
        api.DATA_DIR=Path(self.temp.name);api.UPLOAD_DIR=api.DATA_DIR/'uploads';api.DB_PATH=api.DATA_DIR/'app.db'
        api.failed_logins.clear()

    def tearDown(self):
        api.DATA_DIR,api.UPLOAD_DIR,api.DB_PATH=self.paths
        self.temp.cleanup()

    def login(self,client,email='inbox-test@example.invalid'):
        client.headers['X-Schimmelpilz-Request']='1'
        payload={'email':email,'password':'Synthetic-inbox-password-2026!','audience':'consumer','full_name':'Synthetic Person','street':'Testweg 1','postal_code':'10115','city':'Berlin','country':'Deutschland'}
        result=client.post('/api/auth/register',json=payload)
        if result.status_code==409:
            result=client.post('/api/auth/login',json={'email':email,'password':payload['password']})
        self.assertIn(result.status_code,[200,201],result.text)

    def case(self,client):
        result=client.post('/api/cases',json={'title':'Synthetic inbox case','description':'Only synthetic testing, no real client data.'})
        self.assertEqual(result.status_code,201,result.text)
        return result.json()['id']

    def upload(self,client,content=None):
        result=client.post('/api/inbox',data={'received_on':'2026-10-07','subject':'Synthetic incoming invoice','sender':'Test Sender','note':'Only a test'},files={'file':('Incoming.pdf',content if content is not None else synthetic_pdf(),'application/pdf')})
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back(self):
        with TestClient(api.app) as client:
            self.login(client);first=self.case(client);second=self.case(client);entry=self.upload(client)
            endpoint=f"/api/inbox/{entry['id']}"
            client.post(endpoint+'/assign',json={'case_id':first,'expected_version':1})
            base=f"/api/cases/{first}/documents/{entry['id']}"
            client.post(base+'/extract');client.put(base+'/text/1',json={'text':'SYNTHETIC REVIEWED INVOICE 480 EUR','reviewed':True})
            question={'request_id':str(uuid.uuid4()),'question':'What is the invoice total?','document_ids':[entry['id']]}
            with patch.object(api,'generate_answer',return_value={'answer':'480 EUR','input_tokens':10,'output_tokens':3,'truncated':False}):
                answer=client.post(f'/api/cases/{first}/research',json=question)
            self.assertEqual(answer.status_code,201,answer.text)
            snapshot=answer.json()['sources']
            result=client.post(endpoint+'/correct',json={'case_id':second,'expected_version':2,'reason':'Synthetic correction of wrong case'})
            self.assertEqual(result.status_code,200,result.text);corrected=result.json()
            self.assertEqual(corrected['version'],3);self.assertEqual(corrected['reviewed_units'],0)
            self.assertNotEqual(corrected['document_id'],entry['id'])
            self.assertEqual(corrected['corrections'][0]['reason'],'Synthetic correction of wrong case')
            self.assertEqual(client.get(base+'/download').content,synthetic_pdf())
            self.assertEqual(client.get(base+'/text').json()['units'][0]['reviewed_text'],'SYNTHETIC REVIEWED INVOICE 480 EUR')
            # The new association starts unreviewed: only freshly read machine text, nothing carried over from the old case.
            fresh=client.get(f"/api/cases/{second}/documents/{corrected['document_id']}/text").json()['units']
            self.assertTrue(all(unit['reviewed_text'] is None and unit['reviewed_at'] is None for unit in fresh))
            with api.db() as connection:
                self.assertEqual(select_sources(connection,first,[entry['id']],'invoice'),[])
            repeat=client.post(f'/api/cases/{first}/research',json=question)
            self.assertEqual(repeat.json()['sources'],snapshot)
            self.assertEqual(client.post(f'/api/cases/{first}/research',json={**question,'request_id':str(uuid.uuid4())}).status_code,422)
            self.assertEqual(client.post(f'/api/cases/{first}/drafts',json={'body':'Synthetic adoption','research_run_id':answer.json()['id']}).status_code,422)
            with patch.object(api,'generate_answer',return_value={'answer':'Fresh synthetic response','input_tokens':10,'output_tokens':3,'truncated':False}) as model:
                fresh=client.post(f'/api/cases/{first}/research',json={'request_id':str(uuid.uuid4()),'question':'Fresh context without old assignment'})
            self.assertEqual(fresh.status_code,201,fresh.text)
            self.assertNotIn('What is the invoice total?',str(model.call_args.args[0]))
            previous=client.get('/api/cases/'+first).json()['documents'][0]
            self.assertTrue(previous['inbox_reassigned_at'])
            back=client.post(endpoint+'/correct',json={'case_id':first,'expected_version':3,'reason':'Synthetic reversal for original case'})
            self.assertEqual(back.status_code,200,back.text)
            self.assertEqual(back.json()['version'],4);self.assertEqual(len(back.json()['corrections']),2)
            self.assertEqual(back.json()['reviewed_units'],0)
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())),1)
            self.assertEqual(len(client.get('/api/cases/'+first).json()['documents']),2)

    def test_correction_guards_and_atomic_rollback(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'correction-other@example.invalid')
            first=self.case(owner);second=self.case(owner);foreign=self.case(other);entry=self.upload(owner)
            endpoint=f"/api/inbox/{entry['id']}/correct"
            payload={'case_id':second,'expected_version':2,'reason':'Synthetic wrong case correction'}
            self.assertEqual(owner.post(endpoint,json=payload).status_code,409)
            owner.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':first,'expected_version':1})
            self.assertEqual(other.post(endpoint,json=payload).status_code,404)
            self.assertEqual(owner.post(endpoint,json={**payload,'case_id':foreign}).status_code,404)
            self.assertEqual(owner.post(endpoint,json={**payload,'case_id':first}).status_code,409)
            self.assertEqual(owner.post(endpoint,json={**payload,'expected_version':1}).status_code,409)
            self.assertEqual(owner.post(endpoint,json={**payload,'reason':'   short  '}).status_code,422)
            with api.db() as connection:
                connection.execute("CREATE TRIGGER fail_correction BEFORE INSERT ON activities WHEN NEW.action='inbox_corrected' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):owner.post(endpoint,json=payload)
            self.assertEqual(owner.get('/api/inbox').json()[0]['version'],2)
            self.assertEqual(owner.get('/api/cases/'+second).json()['documents'],[])
            self.assertFalse(owner.get('/api/cases/'+first).json()['documents'][0]['inbox_reassigned_at'])
            with api.db() as connection:
                connection.execute('DROP TRIGGER fail_correction')
            stored=next(api.UPLOAD_DIR.iterdir());stored.write_bytes(b'changed bytes')
            self.assertEqual(owner.post(endpoint,json=payload).status_code,409)
            self.assertEqual(owner.get('/api/inbox').json()[0]['corrections'],[])

    def test_unassigned_persistence_then_exact_file_and_text_review_in_case(self):
        content=synthetic_pdf()
        with TestClient(api.app) as client:
            self.login(client)
            entry=self.upload(client,content)
            self.assertIsNone(entry['case_id'])
            self.assertEqual(client.get('/api/cases').json(),[])
            self.assertEqual(client.get(f"/api/inbox/{entry['id']}/download").content,content)
            self.assertEqual(entry['sha256'],hashlib.sha256(content).hexdigest())
            self.assertNotIn('stored_name',entry)
            self.assertNotIn('user_id',entry)
        with TestClient(api.app) as client:
            self.login(client)
            self.assertEqual(client.get('/api/inbox').json()[0]['subject'],'Synthetic incoming invoice')
            case_id=self.case(client)
            self.assertEqual(client.get(f"/api/cases/{case_id}/documents/{entry['id']}/text").status_code,404)
            result=client.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':case_id,'expected_version':1})
            self.assertEqual(result.status_code,200,result.text)
            assigned=result.json()
            self.assertEqual(assigned['version'],2)
            self.assertEqual(assigned['document_id'],entry['id'])
            self.assertEqual(client.get(f"/api/cases/{case_id}/documents/{entry['id']}/download").content,content)
            saved=client.get('/api/cases/'+case_id).json()
            self.assertEqual(len(saved['documents']),1)
            self.assertIn('inbox_assigned',[item['action'] for item in saved['activities']])
            base=f"/api/cases/{case_id}/documents/{entry['id']}"
            self.assertEqual(client.post(base+'/extract').json()['extraction']['status'],'ready')
            result=client.put(base+'/text/1',json={'text':'SYNTHETIC INVOICE TEST-778. Total: 480 EUR.','reviewed':True})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(client.get('/api/inbox').json()[0]['reviewed_units'],1)
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())),1)

    def test_ownership_validation_stale_updates_and_single_assignment(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'other-inbox@example.invalid')
            entry=self.upload(owner);case_id=self.case(owner);foreign=self.case(other)
            self.assertEqual(other.get('/api/inbox').json(),[])
            self.assertEqual(other.get(f"/api/inbox/{entry['id']}/download").status_code,404)
            self.assertEqual(other.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':foreign,'expected_version':1}).status_code,404)
            self.assertEqual(owner.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':foreign,'expected_version':1}).status_code,404)
            metadata={'subject':'Edited subject','sender':'Edited sender','received_on':'2026-10-06','note':'Synthetic note','expected_version':1}
            self.assertEqual(other.put('/api/inbox/'+entry['id'],json=metadata).status_code,404)
            self.assertEqual(owner.put('/api/inbox/'+entry['id'],json=metadata).status_code,200)
            self.assertEqual(owner.put('/api/inbox/'+entry['id'],json=metadata).status_code,409)
            self.assertEqual(owner.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':case_id,'expected_version':1}).status_code,409)
            self.assertEqual(owner.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':case_id,'expected_version':2}).status_code,200)
            self.assertEqual(owner.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':case_id,'expected_version':3}).status_code,409)
            self.assertEqual(owner.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':self.case(owner),'expected_version':3}).status_code,409)
            self.assertEqual(owner.put('/api/inbox/'+entry['id'],json={**metadata,'expected_version':3}).status_code,409)
            self.assertEqual(len(owner.get('/api/cases/'+case_id).json()['documents']),1)

    def test_rejected_uploads_leave_no_files_and_auth_guard_applies(self):
        with TestClient(api.app) as client:
            self.assertEqual(client.get('/api/inbox').status_code,401)
            self.assertEqual(client.post('/api/inbox',data={'received_on':'2026-10-07'},files={'file':('test.pdf',b'test')}).status_code,403)
            self.login(client)
            for name,content,data,status in [('script.exe',b'a',{'received_on':'2026-10-07'},415),('empty.pdf',b'',{'received_on':'2026-10-07'},422),('large.pdf',b'x'*(api.MAX_UPLOAD_BYTES+1),{'received_on':'2026-10-07'},413),('date.pdf',b'a',{'received_on':'invalid'},422),('subject.pdf',b'a',{'received_on':'2026-10-07','subject':'x'*161},422)]:
                result=client.post('/api/inbox',data=data,files={'file':(name,content)})
                self.assertEqual(result.status_code,status,result.text)
            self.assertEqual(client.get('/api/inbox').json(),[])
            self.assertEqual(list(api.UPLOAD_DIR.iterdir()),[])

    def test_atomic_assignment_rollback_and_failed_upload_cleanup(self):
        with TestClient(api.app) as client:
            self.login(client);entry=self.upload(client);case_id=self.case(client)
            with api.db() as connection:
                connection.execute("CREATE TRIGGER fail_inbox_activity BEFORE INSERT ON activities WHEN NEW.action='inbox_assigned' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                client.post(f"/api/inbox/{entry['id']}/assign",json={'case_id':case_id,'expected_version':1})
            self.assertEqual(client.get('/api/cases/'+case_id).json()['documents'],[])
            self.assertIsNone(client.get('/api/inbox').json()[0]['case_id'])
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())),1)
            with api.db() as connection:
                connection.execute("CREATE TRIGGER fail_inbox_upload BEFORE INSERT ON inbox_documents BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):
                self.upload(client)
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())),1)
            self.assertEqual(len(client.get('/api/inbox').json()),1)


if __name__=='__main__':
    unittest.main()
