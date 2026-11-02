import os
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
            # Operator powers stay locked until the administrator uses a second factor.
            self.assertEqual(admin.get('/api/admin').json()['detail'],'admin_mfa_required')
            with api.db() as c:c.execute("UPDATE users SET mfa_enabled_at='2026-01-01',mfa_secret='JBSWY3DPEHPK3PXP' WHERE id=?",(actor['id'],))
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
            with api.db() as c:c.execute("UPDATE users SET is_admin=1,mfa_enabled_at='2026-01-01',mfa_secret='JBSWY3DPEHPK3PXP' WHERE id=?",(me['id'],))
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

    def test_starting_plan_follows_account_type(self):
        with TestClient(api.app) as client:
            client.headers['X-Schimmelpilz-Request']='1'
            for audience,plan in [('consumer','personal'),('business','business'),('law_firm','firm')]:
                payload={'email':f'plan-{audience}@example.invalid','password':'Synthetic-plan-password-2026!','audience':audience,'organisation':'Example only','full_name':'Synthetic Person','street':'Testweg 1','postal_code':'10115','city':'Berlin','country':'Deutschland'}
                self.assertEqual(client.post('/api/auth/register',json=payload).status_code,201)
                self.assertEqual(client.get('/api/billing').json()['plan'],plan)
            # Untouched pilot rows written with the old 'personal' default are realigned on startup.
            with api.db() as c:
                c.execute("UPDATE subscriptions SET plan='personal'")
                c.execute("UPDATE subscriptions SET trial_started='2026-01-01T00:00:00+00:00' WHERE user_id=(SELECT id FROM users WHERE email='plan-business@example.invalid')")
                billing.migrate(c)
                plans=dict(c.execute('SELECT u.email,s.plan FROM subscriptions s JOIN users u ON u.id=s.user_id').fetchall())
            self.assertEqual(plans['plan-law_firm@example.invalid'],'firm')
            self.assertEqual(plans['plan-business@example.invalid'],'personal')

    def test_trial_is_once_expiry_keeps_reads_and_operator_can_restore_pilot(self):
        with TestClient(api.app) as client:
            self.login(client);case=self.case(client);me=client.get('/api/auth/me').json()
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'pilot')
            self.assertEqual(client.post('/api/billing/trial',json={'plan':'firm'}).status_code,409)
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'pilot')
            with api.db() as c:c.execute("UPDATE subscriptions SET status='expired' WHERE user_id=?",(me['id'],))
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
            with patch.dict(os.environ,{'CLIP_LINK_PERSONAL':''}):self.assertEqual(client.post('/api/billing/checkout',json={'plan':'personal','consent':True}).status_code,503)
            with api.db() as c:c.execute("UPDATE users SET is_admin=1,mfa_enabled_at='2026-01-01',mfa_secret='JBSWY3DPEHPK3PXP' WHERE id=?",(me['id'],))
            row=client.get('/api/billing').json()
            self.assertEqual(client.put('/api/admin/billing/'+me['id'],json={'pilot':True,'reason':'Synthetic pilot restore test','expected_version':row['version']}).status_code,200)
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'pilot')

    def admin(self,client,email='billing-admin@example.invalid'):
        self.login(client,email);me=client.get('/api/auth/me').json()
        with api.db() as c:c.execute("UPDATE users SET is_admin=1,mfa_enabled_at='2026-01-01',mfa_secret='JBSWY3DPEHPK3PXP' WHERE id=?",(me['id'],))

    def test_clip_link_checkout_and_operator_recorded_prepaid_months(self):
        config={'CLIP_LINK_PERSONAL':'https://pago.clip.mx/synthetic-personal','CLIP_LINK_BUSINESS':'','CLIP_LINK_FIRM':'http://insecure.invalid/link','PRICE_CURRENCY':'MXN','PRICE_PERSONAL':'199.00','PRICE_BUSINESS':'599','PRICE_FIRM':'999.50'}
        with patch.dict(os.environ,config),TestClient(api.app) as client,TestClient(api.app) as operator:
            self.login(client);case=self.case(client);me=client.get('/api/auth/me').json();self.admin(operator)
            self.assertEqual(client.get('/api/public/pricing').json(),{'currency':'MXN','plans':{'personal':19900,'business':59900,'firm':99950},'trial_days':7})
            # Pilot accounts are free and are never sent to a payment page.
            self.assertEqual(client.post('/api/billing/checkout',json={'plan':'personal','consent':True}).status_code,409)
            with api.db() as c:c.execute("UPDATE subscriptions SET status='expired' WHERE user_id=?",(me['id'],))
            status=client.get('/api/billing').json()
            self.assertEqual(status['links_ready'],{'personal':True,'business':False,'firm':False})
            self.assertEqual(client.post('/api/billing/checkout',json={'plan':'firm','consent':True}).status_code,503)
            opened=client.post('/api/billing/checkout',json={'plan':'personal','consent':True})
            self.assertEqual(opened.json(),{'url':config['CLIP_LINK_PERSONAL'],'reference':me['email']})
            self.assertEqual(client.post('/api/billing/checkout',json={'plan':'personal','consent':True}).status_code,200)
            with api.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM billing_orders WHERE user_id=? AND completed_at IS NULL',(me['id'],)).fetchone()[0],1)
            # Opening the link grants nothing; writes stay blocked until the operator records the payment.
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'expired')
            self.assertEqual(client.post(f'/api/cases/{case}/drafts',json={'body':'Blocked before payment'}).status_code,402)
            today=billing.datetime.now(billing.UTC).date().isoformat()
            self.assertEqual(client.post(f'/api/admin/billing/{me["id"]}/payments',json={'plan':'personal','months':1,'amount':'199','reference':'clip-1','paid_on':today,'expected_version':0}).status_code,403)
            row=next(item for item in operator.get('/api/admin/billing').json()['subscriptions'] if item['user_id']==me['id'])
            self.assertEqual(row['pending_payment']['plan'],'personal')
            pay=lambda **values:operator.post(f'/api/admin/billing/{me["id"]}/payments',json={'plan':'personal','months':1,'amount':'199','reference':'clip-1','paid_on':today,'expected_version':row['version'],**values})
            self.assertEqual(pay(amount='100').json()['detail'],'amount_does_not_match_plan_price')
            self.assertEqual(pay(expected_version=row['version']+5).status_code,409)
            self.assertEqual(pay(paid_on='2001-01-01').status_code,422)
            first=pay();self.assertEqual(first.status_code,201,first.text)
            status=client.get('/api/billing').json()
            self.assertEqual((status['effective_status'],status['plan'],status['pending_payment'],len(status['payments'])),('active','personal',None,1))
            self.assertFalse(status['renewal_due'])
            self.assertEqual(client.post(f'/api/cases/{case}/drafts',json={'body':'Allowed after payment'}).status_code,201)
            self.assertEqual(pay(expected_version=status['version']).json()['detail'],'payment_already_recorded')
            # Paying early adds months after the running period instead of overlapping it.
            second=pay(months=2,amount='398,00',reference='clip-2',expected_version=status['version'])
            self.assertEqual(second.status_code,201,second.text)
            self.assertEqual(second.json()['period_end'],billing.add_months(billing.datetime.fromisoformat(first.json()['period_end']),2).isoformat())
            self.assertEqual(client.post('/api/billing/trial',json={'plan':'personal'}).status_code,409)
            with api.db() as c:c.execute("UPDATE subscriptions SET period_end=? WHERE user_id=?",((billing.datetime.now(billing.UTC)+billing.timedelta(days=3)).isoformat(),me['id']))
            self.assertTrue(client.get('/api/billing').json()['renewal_due'])
            with api.db() as c:c.execute("UPDATE subscriptions SET period_end='2000-01-01T00:00:00+00:00' WHERE user_id=?",(me['id'],))
            self.assertEqual(client.get('/api/billing').json()['effective_status'],'expired')
            self.assertEqual(client.post(f'/api/cases/{case}/drafts',json={'body':'Blocked after expiry'}).status_code,402)
            self.assertEqual(client.get('/api/cases/'+case).status_code,200)

    def test_calendar_months_and_paid_time_start(self):
        moment=billing.datetime(2027,1,31,10,tzinfo=billing.UTC)
        self.assertEqual(billing.add_months(moment,1),billing.datetime(2027,2,28,10,tzinfo=billing.UTC))
        self.assertEqual(billing.add_months(moment,13),billing.datetime(2028,2,29,10,tzinfo=billing.UTC))
        later=(billing.datetime.now(billing.UTC)+billing.timedelta(days=4)).isoformat()
        self.assertEqual(billing.paid_from({'status':'trial','trial_end':later,'period_end':None}).isoformat(),later)
        self.assertLess(billing.paid_from({'status':'expired','trial_end':later,'period_end':later}),billing.datetime.fromisoformat(later))
        with patch.dict(os.environ,{'PRICE_PERSONAL':'abc','PRICE_BUSINESS':'-3','PRICE_FIRM':'1.234','PRICE_CURRENCY':'pesos'}):
            self.assertEqual((billing.plans(),billing.currency()),({'personal':990,'business':2990,'firm':4990},'EUR'))

    def test_public_operator_particulars_come_only_from_configuration(self):
        with TestClient(api.app) as client:
            with patch.dict(os.environ,{'OPERATOR_NAME':'','OPERATOR_ADDRESS':'','OPERATOR_EMAIL':''}):
                self.assertFalse(client.get('/api/public/operator').json()['complete'])
            with patch.dict(os.environ,{'OPERATOR_NAME':'Synthetic Operator','OPERATOR_ADDRESS':'Testweg 1; 10115 Berlin','OPERATOR_EMAIL':'operator@example.invalid'}):
                result=client.get('/api/public/operator').json()
            self.assertTrue(result['complete']);self.assertEqual(result['address'],['Testweg 1','10115 Berlin'])


if __name__=='__main__':unittest.main()
