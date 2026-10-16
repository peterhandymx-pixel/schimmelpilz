import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app as api,billing
from server.tests import test_inbox


class ControlTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case=None
    test_ownership_validation_stale_updates_and_single_assignment=None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies=None
    test_atomic_assignment_rollback_and_failed_upload_cleanup=None
    test_correction_guards_and_atomic_rollback=None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back=None

    def test_scoped_team_access_actor_identity_revocation_and_invitation_replay(self):
        with TestClient(api.app) as owner,TestClient(api.app) as member,TestClient(api.app) as stranger:
            self.login(owner);self.login(member,'member@example.invalid');self.login(stranger,'stranger@example.invalid')
            me=owner.get('/api/auth/me').json();person=member.get('/api/auth/me').json()
            first=self.case(owner);second=self.case(owner)
            document=owner.post(f'/api/cases/{first}/documents',files={'file':('Synthetic.pdf',test_inbox.synthetic_pdf(),'application/pdf')}).json()
            hidden=owner.post(f'/api/cases/{second}/documents',files={'file':('Other.pdf',test_inbox.synthetic_pdf(),'application/pdf')}).json()
            invite=owner.post('/api/team/invites',json={'email':person['email'],'role':'editor','case_ids':[first]})
            self.assertEqual(invite.status_code,200,invite.text);token=invite.json()['token']
            self.assertEqual(stranger.post('/api/team/join',json={'token':token}).status_code,404)
            self.assertEqual(member.post('/api/team/join',json={'token':token}).status_code,200)
            self.assertEqual(member.post('/api/team/join',json={'token':token}).status_code,404)
            self.assertEqual(member.post('/api/team/switch',json={'owner_id':me['id']}).status_code,200)
            self.assertEqual([c['id'] for c in member.get('/api/cases').json()],[first])
            self.assertEqual(member.get('/api/cases/'+second).status_code,404)
            self.assertEqual(member.get(f'/api/cases/{first}/documents/{document["id"]}/download').content,test_inbox.synthetic_pdf())
            self.assertEqual(member.get(f'/api/cases/{second}/documents/{hidden["id"]}/download').status_code,404)
            self.assertEqual(member.get('/api/inbox').status_code,403)
            self.assertEqual(member.get('/api/contacts').status_code,403)
            self.assertEqual(member.get('/api/cost-reviews').status_code,403)
            self.assertEqual(member.get('/api/cost-reviews?case_id='+second).status_code,403)
            self.assertEqual(member.get('/api/cost-reviews?case_id='+first).status_code,200)
            self.assertEqual(member.get('/api/tasks/calendar.ics').status_code,403)
            self.assertEqual(member.get('/api/tasks/calendar.ics?case_id='+first).status_code,200)
            self.assertEqual(member.post('/api/cases',json={'title':'Forbidden new case','description':'Synthetic test'}).status_code,403)
            self.assertEqual(member.post('/api/team/invites',json={'email':'x@example.invalid'}).status_code,403)
            draft=member.post(f'/api/cases/{first}/drafts',json={'body':'Synthetic shared draft by real actor'})
            self.assertEqual(draft.status_code,201,draft.text)
            with api.db() as c:
                self.assertEqual(c.execute('SELECT actor_id FROM draft_versions WHERE draft_id=?',(draft.json()['id'],)).fetchone()[0],person['id'])
            members=owner.get('/api/team').json()['members'];entry=members[0]
            change={'role':'viewer','case_ids':[first],'enabled':True,'expected_version':entry['version']}
            self.assertEqual(owner.put('/api/team/members/'+person['id'],json=change).status_code,200)
            self.assertEqual(member.post(f'/api/cases/{first}/drafts',json={'body':'Forbidden viewer write'}).status_code,403)
            self.assertEqual(member.get('/api/cases/'+first).status_code,200)
            self.assertEqual(owner.put('/api/team/members/'+person['id'],json=change).status_code,409)
            self.assertEqual(owner.put('/api/team/members/'+person['id'],json={**change,'enabled':False,'expected_version':2}).status_code,200)
            self.assertEqual(member.get('/api/cases/'+first).status_code,403)
            self.assertEqual(member.post('/api/team/switch',json={'owner_id':None}).status_code,200)
            self.assertEqual(member.get('/api/cases').json(),[])

    def test_admin_is_explicit_audited_and_disabled_accounts_lose_sessions(self):
        with TestClient(api.app) as admin,TestClient(api.app) as other:
            self.login(admin);self.login(other,'controlled@example.invalid')
            actor=admin.get('/api/auth/me').json();target=other.get('/api/auth/me').json();case=self.case(other)
            self.assertEqual(admin.get('/api/admin').status_code,403)
            with api.db() as c:c.execute('UPDATE users SET is_admin=1 WHERE id=?',(actor['id'],))
            self.assertEqual(admin.get('/api/admin').status_code,200)
            self.assertEqual(admin.post('/api/team/switch',json={'owner_id':target['id']}).status_code,200)
            self.assertEqual(admin.get('/api/cases/'+case).status_code,200)
            update={'disabled':True,'is_admin':False,'expected_version':0,'reason':'Synthetic account suspension test'}
            self.assertEqual(other.put('/api/admin/users/'+actor['id'],json=update).status_code,403)
            self.assertEqual(admin.put('/api/admin/users/'+actor['id'],json=update).status_code,409)
            self.assertEqual(admin.put('/api/admin/users/'+target['id'],json=update).status_code,200)
            self.assertEqual(other.get('/api/auth/me').status_code,401)
            log=admin.get('/api/admin').json()['audit']
            self.assertIn('workspace_selected',[r['action'] for r in log]);self.assertIn('user_control',[r['action'] for r in log])

    def test_operator_switches_are_versioned_and_stop_new_work_without_destroying_files(self):
        with TestClient(api.app) as client:
            self.login(client);me=client.get('/api/auth/me').json();case=self.case(client)
            self.assertEqual(client.put('/api/admin/system',json={'ai_enabled':False,'registrations_enabled':False,'expected_version':0,'reason':'Synthetic operator controls'}).status_code,403)
            with api.db() as c:c.execute('UPDATE users SET is_admin=1 WHERE id=?',(me['id'],))
            settings={'ai_enabled':False,'registrations_enabled':False,'expected_version':0,'reason':'Synthetic operator controls'}
            self.assertEqual(client.put('/api/admin/system',json=settings).status_code,200)
            self.assertEqual(client.put('/api/admin/system',json=settings).status_code,409)
            with patch.object(api,'generate_answer') as model:
                result=client.post(f'/api/cases/{case}/research',json={'request_id':'00000000-0000-0000-0000-000000000001','question':'Synthetic disabled AI question'})
            self.assertEqual(result.status_code,503);model.assert_not_called()
            self.assertEqual(client.get('/api/cases/'+case).status_code,200)
            blocked=client.post('/api/auth/register',json={'email':'paused@example.invalid','password':'Synthetic-registration-2026!','audience':'consumer','full_name':'Synthetic Paused','street':'Test 1','postal_code':'12345','city':'Test','country':'Test'})
            self.assertEqual(blocked.status_code,403)
            self.assertEqual(client.put('/api/admin/system',json={**settings,'ai_enabled':True,'registrations_enabled':True,'expected_version':1}).status_code,200)

    def test_trial_is_once_expiry_keeps_reads_and_operator_can_restore_pilot(self):
        with TestClient(api.app) as client:
            self.login(client);case=self.case(client);me=client.get('/api/auth/me').json()
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'pilot')
            trial=client.post('/api/billing/trial',json={'plan':'firm'})
            self.assertEqual(trial.status_code,200,trial.text)
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'trial')
            self.assertEqual(client.post('/api/billing/trial',json={'plan':'firm'}).status_code,409)
            with api.db() as c:c.execute("UPDATE subscriptions SET trial_end='2000-01-01T00:00:00+00:00' WHERE user_id=?",(me['id'],))
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'expired')
            self.assertEqual(client.get('/api/cases/'+case).status_code,200)
            self.assertEqual(client.post(f'/api/cases/{case}/drafts',json={'body':'Must be read only'}).status_code,402)
            self.assertEqual(client.get('/api/cases/'+case+'/export.zip').status_code,200)
            self.assertEqual(client.post('/api/billing/checkout',json={'plan':'personal','consent':False}).status_code,422)
            with patch.dict(os.environ,{'STRIPE_SECRET_KEY':''}):self.assertEqual(client.post('/api/billing/checkout',json={'plan':'personal','consent':True}).status_code,503)
            with api.db() as c:c.execute('UPDATE users SET is_admin=1 WHERE id=?',(me['id'],))
            row=client.get('/api/billing').json()
            self.assertEqual(client.put('/api/admin/billing/'+me['id'],json={'pilot':True,'reason':'Synthetic pilot restore test','expected_version':row['version']}).status_code,200)
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'pilot')

    def test_hosted_checkout_signed_webhooks_replay_and_cancellation_state(self):
        config={'STRIPE_SECRET_KEY':'sk_test_synthetic','STRIPE_WEBHOOK_SECRET':'whsec_synthetic','PUBLIC_APP_URL':'https://example.invalid','STRIPE_PRICE_PERSONAL':'price_personal','STRIPE_PRICE_BUSINESS':'price_business','STRIPE_PRICE_FIRM':'price_firm'}
        with patch.dict(os.environ,config),TestClient(api.app) as client:
            self.login(client);me=client.get('/api/auth/me').json()
            with patch.object(billing,'stripe',side_effect=[{'unit_amount':990,'currency':'eur','recurring':{'interval':'month','interval_count':1},'tax_behavior':'inclusive'},{'id':'cs_test_1','url':'https://checkout.stripe.com/synthetic'}]) as provider:
                checkout=client.post('/api/billing/checkout',json={'plan':'personal','consent':True})
                self.assertEqual(checkout.status_code,200,checkout.text)
                self.assertEqual(provider.call_args.args[1]['line_items[0][price]'],'price_personal')
                order=provider.call_args.args[1]['subscription_data[metadata][order_id]']
            obj={'id':'sub_synthetic','customer':'cus_synthetic','status':'active','metadata':{'user_id':me['id'],'order_id':order},'items':{'data':[{'price':{'id':'price_personal'},'quantity':1,'current_period_end':int(time.time())+86400}]},'cancel_at_period_end':True}
            body=json.dumps({'id':'evt_synthetic','type':'customer.subscription.updated','data':{'object':{'id':'sub_synthetic'}}}).encode();stamp=str(int(time.time()));sig=hmac.new(config['STRIPE_WEBHOOK_SECRET'].encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
            headers={'stripe-signature':f't={stamp},v1={sig}','Content-Type':'application/json'}
            client.headers.pop('X-Schimmelpilz-Request',None)
            with patch.object(billing,'stripe',return_value=obj) as provider:
                self.assertEqual(client.post('/api/billing/webhook',content=body,headers={'stripe-signature':'invalid'}).status_code,400)
                result=client.post('/api/billing/webhook',content=body,headers=headers);self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(client.post('/api/billing/webhook',content=body,headers=headers).status_code,200)
                self.assertEqual(provider.call_count,1)
            status=client.get('/api/billing').json();self.assertEqual(status['effective_status'],'active');self.assertTrue(status['cancel_at_period_end'])
            self.assertFalse(billing.signature(body,f't=1,v1={sig}',config['STRIPE_WEBHOOK_SECRET']))
            canceled={**obj,'status':'canceled','cancel_at_period_end':False}
            late=json.dumps({'id':'evt_late','type':'customer.subscription.updated','data':{'object':{'id':'sub_synthetic','status':'active'}}}).encode()
            signature=hmac.new(config['STRIPE_WEBHOOK_SECRET'].encode(),stamp.encode()+b'.'+late,hashlib.sha256).hexdigest()
            with patch.object(billing,'stripe',return_value=canceled):
                self.assertEqual(client.post('/api/billing/webhook',content=late,headers={'stripe-signature':f't={stamp},v1={signature}'}).status_code,200)
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'canceled')



if __name__=='__main__':unittest.main()
