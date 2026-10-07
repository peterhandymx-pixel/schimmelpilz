import json
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from server import app as api


class DraftReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.paths = api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH
        api.DATA_DIR = Path(self.temp.name)
        api.UPLOAD_DIR = api.DATA_DIR / 'uploads'
        api.DB_PATH = api.DATA_DIR / 'app.db'
        api.failed_logins.clear()
        self.client = TestClient(api.app)
        self.client.__enter__()
        self.client.headers['X-Schimmelpilz-Request'] = '1'
        self.user = self.register(self.client)
        self.case = self.client.post('/api/cases', json={'title':'Review fixture','description':'Only synthetic test data','language':'de'}).json()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH = self.paths
        self.temp.cleanup()

    def register(self, client, email='review@example.invalid'):
        result = client.post('/api/auth/register', json={'email':email,'password':'Synthetic-review-password-2026','audience':'consumer','full_name':'Synthetic Reviewer','street':'Teststraße 1','postal_code':'10115','city':'Berlin','country':'Deutschland'})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def create(self, **extra):
        result = self.client.post(f"/api/cases/{self.case['id']}/drafts", json={'body':'Synthetic facts for review.','recipient':'Internal synthetic test',**extra})
        self.assertEqual(result.status_code, 201, result.text)
        self.path = f"/api/cases/{self.case['id']}/drafts/{result.json()['id']}"
        return result.json()

    def review(self):
        result = self.client.get(self.path+'/review')
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def action(self, action, state=None, status=200, **extra):
        state = state or self.review()
        draft = state['draft']
        result = self.client.post(self.path+'/review', json={'action':action,'expected_version':draft['version'],'expected_review_revision':draft['review_revision'],**extra})
        self.assertEqual(result.status_code, status, result.text)
        return result.json()

    def check_all(self):
        state = self.action('begin')
        for item in state['checks']:
            state = self.action('check',check_id=item['id'],checked=True,note='Synthetic functional test; no real legal assessment.')
        return state

    def approve(self):
        self.check_all()
        return self.action('approve',confirmed=True,note='Synthetic workflow approval only; no real legal document.')

    def test_approval_edit_reset_and_immutable_history_survive_restart(self):
        draft = self.create()
        approved = self.approve()
        self.assertEqual(approved['draft']['review_status'], 'approved')
        self.assertTrue(approved['draft']['approved_at'])
        self.assertEqual(approved['draft']['approved_name'], 'Synthetic Reviewer')
        event = next(item for item in approved['events'] if item['action']=='approve')
        self.assertEqual(len(event['evidence']['checks']), 5)
        self.assertEqual(event['evidence']['sha256'], approved['versions'][0]['sha256'])
        same = self.client.put(self.path,json={'body':draft['body'],'expected_version':1}).json()
        self.assertEqual((same['version'],same['review_status']), (1,'approved'))
        result = self.client.put(self.path,json={'body':'Changed synthetic facts.','expected_version':1})
        self.assertEqual(result.status_code,200,result.text)
        changed = result.json()
        self.assertEqual((changed['version'],changed['review_status']), (2,'draft'))
        self.assertIsNone(changed['approved_by'])
        self.assertIsNone(changed['approved_at'])
        state = self.review()
        self.assertEqual(state['unresolved'],5)
        self.assertTrue(all(item['review'] is None for item in state['checks']))
        old = self.client.get(self.path+'/versions/1').json()
        self.assertEqual(old['snapshot']['body'],draft['body'])
        self.assertEqual(old['sha256'],event['evidence']['sha256'])
        self.action('approve',state=approved,status=409,confirmed=True,note='Stale approval must be rejected.')
        api.init_db()
        after = self.review()
        self.assertEqual(len(after['versions']),2)
        self.assertEqual(next(e for e in after['events'] if e['action']=='approve'),event)
        pdf = self.client.get(self.path+'/pdf')
        self.assertEqual(pdf.status_code,200,pdf.text if pdf.status_code !=200 else '')
        self.assertEqual(pdf.headers['X-Draft-Version'],'2')
        self.assertEqual(pdf.headers['X-Draft-Review-Status'],'draft')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_hard_blocks_are_not_overridden_by_check_notes(self):
        self.create(body='[Datum] Evidence [L99]',recipient='')
        state = self.check_all()
        self.assertEqual({item['kind'] for item in state['hard_blocks']},{'placeholder','unknown_citation','missing_recipient'})
        self.assertEqual(state['unresolved'],0)
        self.assertFalse(state['can_approve'])
        self.action('approve',status=409,confirmed=True,note='Synthetic confirmation cannot override missing data.')

    def test_validation_and_concurrent_review_revision_protect_writes(self):
        self.create()
        state = self.action('begin')
        self.action('check',status=422,check_id='forged',checked=True,note='Synthetic test note')
        self.action('check',status=422,check_id='facts',checked=True,note='short')
        self.action('approve',status=422,confirmed=False,note='Missing explicit confirmation.')
        payload = {'action':'check','expected_version':1,'expected_review_revision':state['draft']['review_revision'],'check_id':'facts','checked':True,'note':'Concurrent synthetic review note.'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _:self.client.post(self.path+'/review',json=payload).status_code,range(2)))
        self.assertEqual(sorted(results),[200,409])
        self.action('check',state=state,status=409,check_id='facts',checked=False)
        self.client.put(self.path,json={'body':'New content','expected_version':1})
        stale = self.client.put(self.path,json={'body':'Stale content','expected_version':1})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.review()['draft']['body'],'New content')

    def test_recipient_language_kind_and_letterhead_changes_reset_approval(self):
        with patch('server.app.draft_letterhead',return_value=(None,'old-layout')):
            draft = self.create()
        for change in ({'recipient':'Other internal recipient'},{'language':'en'},{'kind':'response'}):
            self.approve()
            draft = self.client.put(self.path,json={'body':draft['body'],'expected_version':draft['version'],**change}).json()
            self.assertEqual(draft['review_status'],'draft')
            self.assertIsNone(draft['approved_at'])
        # The draft's saved letterhead differs from the account's current empty template.
        self.approve()
        draft = self.client.put(self.path,json={'body':draft['body'],'expected_version':draft['version'],'use_current_letterhead':True}).json()
        self.assertEqual(draft['review_status'],'draft')
        self.assertIsNone(draft['letterhead_layout'])

    def test_server_source_snapshot_and_account_case_isolation(self):
        run_id = str(uuid.uuid4())
        source = {'citation_id':'L1','title':'Synthetic original','pinpoint':'§ Test','url':'https://example.invalid','text':'Original synthetic passage','review_status':'checked','metadata':{},'fetched_at':'2026-10-07'}
        with api.db() as connection:
            connection.execute("INSERT INTO research_runs(id,case_id,question,language,workflow,status,model,created_at,answer,legal_sources) VALUES(?,?,?,'de','research','completed','synthetic',?,?,?)",(run_id,self.case['id'],'Fixture?',api.now(),'Fixture answer',json.dumps([source])))
        draft = self.create(body='Synthetic statement [L1]',research_run_id=run_id,source_context={'legal_sources':[{'text':'forged'}]})
        state = self.review()
        self.assertEqual(state['checks'][-1]['sources'][0]['text'],source['text'])
        self.assertFalse(state['hard_blocks'])
        with api.db() as connection:
            connection.execute("UPDATE research_runs SET legal_sources='[]' WHERE id=?",(run_id,))
        self.assertEqual(self.review()['checks'][-1]['sources'][0]['text'],source['text'])
        second = self.client.post('/api/cases',json={'title':'Other file','description':'Synthetic other file','language':'de'}).json()
        other = f"/api/cases/{second['id']}/drafts"
        self.assertEqual(self.client.post(other,json={'body':'Other file','research_run_id':run_id}).status_code,404)
        self.assertEqual(self.client.get(other+f"/{draft['id']}/review").status_code,404)
        with TestClient(api.app) as outsider:
            outsider.headers['X-Schimmelpilz-Request']='1'
            self.register(outsider,'outsider@example.invalid')
            self.assertEqual(outsider.get(self.path+'/review').status_code,404)
            self.assertEqual(outsider.get(self.path+'/versions/1').status_code,404)
            self.assertEqual(outsider.post(self.path+'/review',json={'action':'begin','expected_version':1,'expected_review_revision':0}).status_code,404)

    def test_legacy_draft_backfill_is_idempotent_and_does_not_trust_text_ledger(self):
        self.create(body='Legacy text [L1]\n\nRECHTSQUELLEN DIESER ANFRAGE\n[L1] Editable, untrusted source')
        with api.db() as connection:
            connection.execute('DELETE FROM draft_versions WHERE draft_id=?',(self.path.split('/')[-1],))
        api.init_db()
        api.init_db()
        state=self.review()
        self.assertEqual(len(state['versions']),1)
        self.assertEqual(state['source_context'],{})
        self.assertEqual(state['hard_blocks'][0]['kind'],'unknown_citation')
        self.assertEqual(state['versions'][0]['actor_name'],'')


if __name__ == '__main__':
    unittest.main()
