"""Explicit seven-day trial and Stripe-hosted subscriptions; no silent pilot conversion."""
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode, urlsplit
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from .control import audit

PLANS={'personal':990,'business':2990,'firm':4990}


def migrate(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS subscriptions(user_id TEXT PRIMARY KEY REFERENCES users(id),plan TEXT NOT NULL DEFAULT 'personal',status TEXT NOT NULL DEFAULT 'pilot',trial_started TEXT,trial_end TEXT,customer_id TEXT,subscription_id TEXT,period_end TEXT,cancel_at_period_end INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS billing_orders(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),plan TEXT NOT NULL,session_id TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS billing_events(id TEXT PRIMARY KEY,event_type TEXT NOT NULL,received_at TEXT NOT NULL);
    ''')


def ensure(c,user_id):
    c.execute('INSERT OR IGNORE INTO subscriptions(user_id,updated_at) VALUES(?,?)',(user_id,datetime.now(UTC).isoformat()))
    return dict(c.execute('SELECT * FROM subscriptions WHERE user_id=?',(user_id,)).fetchone())


def effective(row):
    if row['status']=='trial' and row['trial_end'] and datetime.fromisoformat(row['trial_end'])<=datetime.now(UTC):return 'expired'
    if row['status']=='active' and row['period_end'] and datetime.fromisoformat(row['period_end'])<=datetime.now(UTC):return 'expired'
    return row['status']


def enforce(c,user,request):
    if user.get('is_admin'):return
    if request.method in {'GET','HEAD'} or request.url.path.startswith(('/api/auth/','/api/team','/api/admin','/api/billing')):return
    row=ensure(c,user['id'])
    if effective(row) not in {'pilot','trial','active'}:raise HTTPException(402,'subscription_required_read_export_remains_available')


def configured():
    base=os.getenv('PUBLIC_APP_URL','')
    return bool(os.getenv('STRIPE_SECRET_KEY') and os.getenv('STRIPE_WEBHOOK_SECRET') and base.startswith('https://') and all(os.getenv('STRIPE_PRICE_'+key.upper()) for key in PLANS))


def stripe(path,values=None,idempotency=None):
    if not re.fullmatch(r'/v1/[A-Za-z0-9_/-]+',path):raise ValueError('Invalid provider path')
    headers={'Authorization':'Bearer '+os.getenv('STRIPE_SECRET_KEY',''),'Stripe-Version':'2025-03-31.basil'}
    if idempotency:headers['Idempotency-Key']=idempotency
    data=urlencode(values).encode() if values is not None else None
    try:
        with urlopen(UrlRequest('https://api.stripe.com'+path,data=data,headers=headers),timeout=20) as response:return json.loads(response.read(1024*1024))
    except Exception:raise HTTPException(503,'payment_provider_unavailable') from None


def signature(body,header,secret):
    try:
        pairs=[part.split('=',1) for part in header.split(',')];stamp=next(value for key,value in pairs if key=='t')
        if abs(time.time()-int(stamp))>300:return False
        expected=hmac.new(secret.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        return any(key=='v1' and hmac.compare_digest(value,expected) for key,value in pairs)
    except (ValueError,StopIteration):return False


class Plan(BaseModel):
    model_config={'extra':'forbid'}
    plan:Literal['personal','business','firm']


class Checkout(Plan):
    consent:Literal[True]


class PilotControl(BaseModel):
    pilot:bool
    reason:str
    expected_version:int


def router(db,require_user,now):
    r=APIRouter()
    @r.get('/api/billing')
    def status(user:dict=Depends(require_user)):
        with db() as c:
            row=ensure(c,user['id'])
            return {**{k:v for k,v in row.items() if k not in {'customer_id','subscription_id'}},'effective_status':effective(row),'checkout_ready':configured(),'has_subscription':bool(row['subscription_id']),'plans':PLANS,'trial_days':7}

    @r.post('/api/billing/trial')
    def trial(payload:Plan,user:dict=Depends(require_user)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');row=ensure(c,user['id'])
            if row['trial_started'] or row['subscription_id']:raise HTTPException(409,'Trial already used or subscription exists')
            end=(datetime.now(UTC)+timedelta(days=7)).isoformat()
            c.execute("UPDATE subscriptions SET plan=?,status='trial',trial_started=?,trial_end=?,updated_at=?,version=version+1 WHERE user_id=?",(payload.plan,now(),end,now(),user['id']))
            audit(c,user['id'],user['id'],'trial_started',payload.plan)
        return {'trial_end':end}

    @r.post('/api/billing/checkout')
    def checkout(payload:Checkout,user:dict=Depends(require_user)):
        if not configured():raise HTTPException(503,'stripe_operator_setup_required')
        with db() as c:
            c.execute('BEGIN IMMEDIATE');row=ensure(c,user['id'])
            if row['subscription_id'] and effective(row) in {'active','trialing','past_due','unpaid'}:raise HTTPException(409,'Manage existing subscription in portal')
            if effective(row)=='trial':raise HTTPException(409,'Finish the free local trial first; no early charge')
            pending=c.execute('SELECT * FROM billing_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 1',(user['id'],)).fetchone()
            if pending and pending['created_at']>(datetime.now(UTC)-timedelta(hours=24)).isoformat():
                if pending['plan']!=payload.plan:raise HTTPException(409,'Existing checkout pending; retry original plan or wait for expiry')
                identifier=pending['id']
            else:
                identifier=str(uuid.uuid4());c.execute('INSERT INTO billing_orders VALUES(?,?,?,NULL,?)',(identifier,user['id'],payload.plan,now()))
        price=stripe('/v1/prices/'+os.environ['STRIPE_PRICE_'+payload.plan.upper()])
        recurring=price.get('recurring') or {}
        if price.get('unit_amount')!=PLANS[payload.plan] or price.get('currency')!='eur' or recurring.get('interval')!='month' or recurring.get('interval_count',1)!=1 or price.get('tax_behavior')!='inclusive':raise HTTPException(503,'Configured price does not match advertised monthly final price')
        base=os.environ['PUBLIC_APP_URL'].rstrip('/')
        values={'mode':'subscription','line_items[0][price]':os.environ['STRIPE_PRICE_'+payload.plan.upper()],'line_items[0][quantity]':'1','client_reference_id':user['id'],'success_url':base+'/?billing=return','cancel_url':base+'/?billing=cancel','subscription_data[metadata][user_id]':user['id'],'subscription_data[metadata][order_id]':identifier}
        values['customer' if row['customer_id'] else 'customer_email']=row['customer_id'] or user['email']
        result=stripe('/v1/checkout/sessions',values,identifier)
        if urlsplit(result.get('url','')).hostname!='checkout.stripe.com':raise HTTPException(503,'Invalid checkout response')
        with db() as c:
            c.execute('UPDATE billing_orders SET session_id=? WHERE id=?',(result['id'],identifier));audit(c,user['id'],user['id'],'checkout_created',identifier)
        return {'url':result['url']}

    @r.post('/api/billing/portal')
    def portal(user:dict=Depends(require_user)):
        if not configured():raise HTTPException(503,'stripe_operator_setup_required')
        with db() as c:row=ensure(c,user['id'])
        if not row['customer_id']:raise HTTPException(409,'No billing customer')
        result=stripe('/v1/billing_portal/sessions',{'customer':row['customer_id'],'return_url':os.environ['PUBLIC_APP_URL']})
        if urlsplit(result.get('url','')).hostname!='billing.stripe.com':raise HTTPException(503,'Invalid portal response')
        return {'url':result['url']}

    @r.post('/api/billing/webhook')
    async def webhook(request:Request):
        secret=os.getenv('STRIPE_WEBHOOK_SECRET')
        if not secret:raise HTTPException(503,'stripe_operator_setup_required')
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>1024*1024:raise HTTPException(413,'Webhook exceeds size limit')
            chunks.append(chunk)
        body=b''.join(chunks)
        if not signature(body,request.headers.get('stripe-signature',''),secret):raise HTTPException(400,'Invalid signature')
        try:event=json.loads(body);identifier=event['id'];kind=event['type']
        except (ValueError,KeyError,TypeError):raise HTTPException(400,'Invalid event') from None
        with db() as c:
            if c.execute('SELECT 1 FROM billing_events WHERE id=?',(identifier,)).fetchone():return {'received':True}
        if kind.startswith('customer.subscription.'):
            # Read authoritative current state, so delayed/out-of-order notifications cannot restore stale entitlement.
            obj=event['data']['object'];sub=stripe('/v1/subscriptions/'+obj['id'])
            user_id=sub.get('metadata',{}).get('user_id');order_id=sub.get('metadata',{}).get('order_id')
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                if c.execute('SELECT 1 FROM billing_events WHERE id=?',(identifier,)).fetchone():return {'received':True}
                order=c.execute('SELECT * FROM billing_orders WHERE id=? AND user_id=?',(order_id,user_id)).fetchone()
                if not order:raise HTTPException(400,'Unknown subscription order')
                row=ensure(c,user_id);items=sub.get('items',{}).get('data',[])
                if len(items)!=1 or items[0].get('quantity')!=1 or items[0]['price']['id']!=os.getenv('STRIPE_PRICE_'+order['plan'].upper()):raise HTTPException(400,'Unexpected subscription price')
                if row['customer_id'] and row['customer_id']!=sub['customer']:raise HTTPException(400,'Customer mismatch')
                if row['subscription_id'] and row['subscription_id']!=sub['id'] and effective(row)=='active':raise HTTPException(409,'Another subscription is active')
                end=items[0].get('current_period_end') or sub.get('current_period_end')
                end=datetime.fromtimestamp(end,UTC).isoformat() if end else None
                state=sub['status']
                if state=='trialing':state='active' # provider-confirmed trial, not inferred from checkout return
                if state=='active' and not end:raise HTTPException(400,'Missing subscription period')
                c.execute('UPDATE subscriptions SET plan=?,status=?,customer_id=?,subscription_id=?,period_end=?,cancel_at_period_end=?,updated_at=?,version=version+1 WHERE user_id=?',(order['plan'],state,sub['customer'],sub['id'],end,bool(sub.get('cancel_at_period_end')),now(),user_id))
                c.execute('INSERT INTO billing_events VALUES(?,?,?)',(identifier,kind,now()))
            return {'received':True}
        with db() as c:c.execute('INSERT OR IGNORE INTO billing_events VALUES(?,?,?)',(identifier,kind,now()))
        return {'received':True}

    @r.get('/api/admin/billing')
    def admin_billing(user:dict=Depends(require_user)):
        if not user.get('is_admin'):raise HTTPException(403,'administrator_required')
        with db() as c:
            for row in c.execute('SELECT id FROM users').fetchall():ensure(c,row['id'])
            return {'checkout_ready':configured(),'subscriptions':[{**dict(row),'effective_status':effective(dict(row))} for row in c.execute('SELECT s.*,u.email FROM subscriptions s JOIN users u ON u.id=s.user_id ORDER BY s.updated_at DESC')]}

    @r.put('/api/admin/billing/{identifier}')
    def pilot(identifier:str,payload:PilotControl,user:dict=Depends(require_user)):
        if not user.get('is_admin'):raise HTTPException(403,'administrator_required')
        if len(payload.reason.strip())<10:raise HTTPException(422,'Reason required')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM users WHERE id=?',(identifier,)).fetchone():raise HTTPException(404,'User not found')
            row=ensure(c,identifier)
            if row['version']!=payload.expected_version or row['subscription_id']:raise HTTPException(409,'Subscription changed or provider-managed')
            c.execute('UPDATE subscriptions SET status=?,updated_at=?,version=version+1 WHERE user_id=?',('pilot' if payload.pilot else 'expired',now(),identifier))
            audit(c,user['id'],identifier,'pilot_access_changed',payload.reason.strip())
        return {'saved':True}
    return r
