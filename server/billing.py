"""Seven-day trial from registration, then prepaid monthly access paid through reusable Clip payment links; nothing converts silently.

Clip's reusable links have no API callback that identifies the account, so the operator records each payment seen in the
Clip dashboard. A recorded payment extends paid access by whole calendar months; nothing renews or charges automatically.
"""
import calendar
import os
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .control import audit, require_operator

PLAN_IDS=('personal','business','firm')
DEFAULT_PRICES={'personal':'9.90','business':'29.90','firm':'49.90'}
ACCESS={'trial','active'}
TRIAL_DAYS=7
RENEWAL_NOTICE_DAYS=7
AUDIENCE_PLAN="CASE audience WHEN 'business' THEN 'business' WHEN 'law_firm' THEN 'firm' ELSE 'personal' END"


def migrate(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS subscriptions(user_id TEXT PRIMARY KEY REFERENCES users(id),plan TEXT NOT NULL DEFAULT 'personal',status TEXT NOT NULL DEFAULT 'pilot',trial_started TEXT,trial_end TEXT,customer_id TEXT,subscription_id TEXT,period_end TEXT,cancel_at_period_end INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS billing_orders(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),plan TEXT NOT NULL,session_id TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS billing_events(id TEXT PRIMARY KEY,event_type TEXT NOT NULL,received_at TEXT NOT NULL);
        -- Payment evidence is kept after account deletion (bookkeeping retention), hence no foreign key and an email snapshot.
        CREATE TABLE IF NOT EXISTS billing_payments(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,email TEXT NOT NULL,plan TEXT NOT NULL,months INTEGER NOT NULL,amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,provider TEXT NOT NULL,reference TEXT NOT NULL,paid_on TEXT NOT NULL,period_start TEXT NOT NULL,period_end TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',recorded_by TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(provider,reference));
    ''')
    if 'completed_at' not in {r[1] for r in c.execute('PRAGMA table_info(billing_orders)')}:
        c.execute('ALTER TABLE billing_orders ADD COLUMN completed_at TEXT')
    # The pilot phase is over: accounts still on free pilot access get the same seven-day trial as new accounts, counted from now.
    start=datetime.now(UTC)
    c.execute(f"UPDATE subscriptions SET plan=(SELECT {AUDIENCE_PLAN} FROM users WHERE users.id=subscriptions.user_id),status='trial',trial_started=?,trial_end=?,updated_at=?,version=version+1 WHERE status='pilot'",
              (start.isoformat(),(start+timedelta(days=TRIAL_DAYS)).isoformat(),start.isoformat()))


def ensure(c,user_id):
    # The trial starts with the account: the first time an account is seen it gets TRIAL_DAYS of full access.
    start=datetime.now(UTC)
    c.execute(f"INSERT OR IGNORE INTO subscriptions(user_id,plan,status,trial_started,trial_end,updated_at) SELECT id,{AUDIENCE_PLAN},'trial',?,?,? FROM users WHERE id=?",
              (start.isoformat(),(start+timedelta(days=TRIAL_DAYS)).isoformat(),start.isoformat(),user_id))
    return dict(c.execute('SELECT * FROM subscriptions WHERE user_id=?',(user_id,)).fetchone())


def effective(row):
    if row['status']=='trial' and row['trial_end'] and datetime.fromisoformat(row['trial_end'])<=datetime.now(UTC):return 'expired'
    if row['status']=='active' and row['period_end'] and datetime.fromisoformat(row['period_end'])<=datetime.now(UTC):return 'expired'
    return row['status']


def enforce(c,user,request):
    if user.get('is_admin'):return
    # Reading, exporting and deleting own data stay available after a trial or paid period ends.
    if request.method in {'GET','HEAD','DELETE'} or request.url.path.startswith(('/api/auth/','/api/team','/api/admin','/api/billing')):return
    row=ensure(c,user['id'])
    if effective(row) not in ACCESS:raise HTTPException(402,'subscription_required_read_export_remains_available')


def currency():
    value=os.getenv('PRICE_CURRENCY','EUR').strip().upper()
    return value if re.fullmatch(r'[A-Z]{3}',value) else 'EUR'


def plans():
    """Monthly final prices in minor units (cents/centavos), from PRICE_PERSONAL/_BUSINESS/_FIRM such as 199.00."""
    result={}
    for plan in PLAN_IDS:
        try:value=Decimal(os.getenv('PRICE_'+plan.upper(),'').strip() or DEFAULT_PRICES[plan])
        except InvalidOperation:value=Decimal(DEFAULT_PRICES[plan])
        if not value.is_finite() or value<=0 or value!=value.quantize(Decimal('0.01')):value=Decimal(DEFAULT_PRICES[plan])
        result[plan]=int(value*100)
    return result


def payment_link(plan):
    # Operator-made reusable Clip link for this plan's monthly amount; only HTTPS links are handed to browsers.
    value=os.getenv('CLIP_LINK_'+plan.upper(),'').strip()
    parts=urlsplit(value)
    return value if parts.scheme=='https' and parts.hostname else None


def demo_mode():
    # PAYMENT_MODE=demo: purchases are simulated in the app; no provider, no card data, nothing is charged.
    return os.getenv('PAYMENT_MODE','').strip().lower()=='demo'


def links_ready():
    return {plan:demo_mode() or bool(payment_link(plan)) for plan in PLAN_IDS}


def add_months(moment,months):
    month=moment.month-1+months
    year=moment.year+month//12;month=month%12+1
    return moment.replace(year=year,month=month,day=min(moment.day,calendar.monthrange(year,month)[1]))


def paid_from(row):
    """Paid time starts after any running paid period or trial, so paying early never shortens access."""
    start=datetime.now(UTC)
    for status,column in (('active','period_end'),('trial','trial_end')):
        if row['status']==status and row[column] and datetime.fromisoformat(row[column])>start:start=datetime.fromisoformat(row[column])
    return start


def renewal_due(row):
    if effective(row)!='active' or not row['period_end']:return False
    return datetime.fromisoformat(row['period_end'])-datetime.now(UTC)<=timedelta(days=RENEWAL_NOTICE_DAYS)


def minor_amount(text):
    try:value=Decimal(text.strip().replace(',','.'))
    except InvalidOperation:raise HTTPException(422,'invalid_amount') from None
    if not value.is_finite() or value<=0 or value!=value.quantize(Decimal('0.01')):raise HTTPException(422,'invalid_amount')
    return int(value*100)


class Plan(BaseModel):
    model_config={'extra':'forbid'}
    plan:Literal['personal','business','firm']


class Checkout(Plan):
    consent:Literal[True]


class AccessControl(BaseModel):
    # Only ending access is possible; free access without a time limit no longer exists.
    pilot:Literal[False]=False
    reason:str
    expected_version:int


class PaymentRecord(Plan):
    months:int=Field(ge=1,le=12)
    amount:str=Field(min_length=1,max_length=20)
    reference:str=Field(min_length=3,max_length=100)
    paid_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    note:str=Field(default='',max_length=500)
    expected_version:int


def payment_view(row):
    return {key:row[key] for key in ('id','plan','months','amount_minor','currency','provider','reference','paid_on','period_start','period_end','created_at')}


def router(db,require_user,now):
    r=APIRouter()

    @r.get('/api/public/pricing')
    def public_pricing():
        return {'currency':currency(),'plans':plans(),'trial_days':TRIAL_DAYS}

    @r.get('/api/billing')
    def status(user:dict=Depends(require_user)):
        with db() as c:
            row=ensure(c,user['id'])
            payments=[payment_view(p) for p in c.execute('SELECT * FROM billing_payments WHERE user_id=? ORDER BY created_at DESC LIMIT 24',(user['id'],))]
            pending=c.execute('SELECT plan,created_at FROM billing_orders WHERE user_id=? AND completed_at IS NULL ORDER BY created_at DESC LIMIT 1',(user['id'],)).fetchone()
        ready=links_ready()
        return {**{k:v for k,v in row.items() if k not in {'customer_id','subscription_id'}},'effective_status':effective(row),'checkout_ready':any(ready.values()),'links_ready':ready,
                'plans':plans(),'currency':currency(),'trial_days':TRIAL_DAYS,'payments':payments,'pending_payment':dict(pending) if pending else None,'renewal_due':renewal_due(row),'payment_reference':user['email'],'payment_mode':'demo' if demo_mode() else 'clip'}

    @r.post('/api/billing/trial')
    def trial(payload:Plan,user:dict=Depends(require_user)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');row=ensure(c,user['id'])
            if row['trial_started'] or c.execute('SELECT 1 FROM billing_payments WHERE user_id=? LIMIT 1',(user['id'],)).fetchone():raise HTTPException(409,'Trial already used or paid access exists')
            end=(datetime.now(UTC)+timedelta(days=TRIAL_DAYS)).isoformat()
            c.execute("UPDATE subscriptions SET plan=?,status='trial',trial_started=?,trial_end=?,updated_at=?,version=version+1 WHERE user_id=?",(payload.plan,now(),end,now(),user['id']))
            audit(c,user['id'],user['id'],'trial_started',payload.plan)
        return {'trial_end':end}

    @r.post('/api/billing/checkout')
    def checkout(payload:Checkout,user:dict=Depends(require_user)):
        # Records the payment intent and hands out the plan's Clip link; access changes only when the operator records the payment.
        url=payment_link(payload.plan)
        if not url:raise HTTPException(503,'payment_link_not_configured')
        with db() as c:
            c.execute('BEGIN IMMEDIATE');row=ensure(c,user['id'])
            c.execute('UPDATE billing_orders SET completed_at=? WHERE user_id=? AND completed_at IS NULL AND plan<>?',(now(),user['id'],payload.plan))
            pending=c.execute('SELECT id FROM billing_orders WHERE user_id=? AND plan=? AND completed_at IS NULL',(user['id'],payload.plan)).fetchone()
            identifier=pending['id'] if pending else str(uuid.uuid4())
            if not pending:c.execute('INSERT INTO billing_orders(id,user_id,plan,created_at) VALUES(?,?,?,?)',(identifier,user['id'],payload.plan,now()))
            audit(c,user['id'],user['id'],'payment_link_opened',payload.plan)
        return {'url':url,'reference':user['email']}

    @r.post('/api/billing/demo-payment',status_code=201)
    def demo_payment(payload:Checkout,user:dict=Depends(require_user)):
        # Books one month exactly like a confirmed payment, but marked as a test; only available in test mode.
        if not demo_mode():raise HTTPException(404,'Not found')
        reference='TEST-'+uuid.uuid4().hex[:10].upper()
        with db() as c:
            c.execute('BEGIN IMMEDIATE');row=ensure(c,user['id'])
            start=paid_from(row);end=add_months(start,1)
            c.execute("UPDATE subscriptions SET plan=?,status='active',period_end=?,cancel_at_period_end=0,updated_at=?,version=version+1 WHERE user_id=?",(payload.plan,end.isoformat(),now(),user['id']))
            c.execute("INSERT INTO billing_payments(id,user_id,email,plan,months,amount_minor,currency,provider,reference,paid_on,period_start,period_end,note,recorded_by,created_at) VALUES(?,?,?,?,1,?,?,'demo',?,?,?,?,?,?,?)",
                      (str(uuid.uuid4()),user['id'],user['email'],payload.plan,plans()[payload.plan],currency(),reference,datetime.now(UTC).date().isoformat(),start.isoformat(),end.isoformat(),'Testzahlung, nichts abgebucht',user['id'],now()))
            c.execute('UPDATE billing_orders SET completed_at=? WHERE user_id=? AND completed_at IS NULL',(now(),user['id']))
            audit(c,user['id'],user['id'],'demo_payment',f'{payload.plan} · {reference}')
        return {'period_end':end.isoformat(),'reference':reference}

    @r.get('/api/admin/billing')
    def admin_billing(user:dict=Depends(require_user)):
        require_operator(user)
        with db() as c:
            for row in c.execute('SELECT id FROM users').fetchall():ensure(c,row['id'])
            pending={row['user_id']:dict(row) for row in c.execute('SELECT user_id,plan,MAX(created_at) AS created_at FROM billing_orders WHERE completed_at IS NULL GROUP BY user_id')}
            payments={}
            for row in c.execute('SELECT * FROM billing_payments ORDER BY created_at DESC'):payments.setdefault(row['user_id'],[]).append(payment_view(row))
            subscriptions=[{**{k:v for k,v in dict(row).items() if k not in {'customer_id','subscription_id'}},'effective_status':effective(dict(row)),'renewal_due':renewal_due(dict(row)),
                            'pending_payment':pending.get(row['user_id']),'payments':payments.get(row['user_id'],[])[:5]} for row in c.execute('SELECT s.*,u.email FROM subscriptions s JOIN users u ON u.id=s.user_id ORDER BY s.updated_at DESC')]
        ready=links_ready()
        return {'checkout_ready':any(ready.values()),'links_ready':ready,'plans':plans(),'currency':currency(),'subscriptions':subscriptions}

    @r.post('/api/admin/billing/{identifier}/payments',status_code=201)
    def record_payment(identifier:str,payload:PaymentRecord,user:dict=Depends(require_user)):
        require_operator(user)
        amount=minor_amount(payload.amount)
        if amount!=plans()[payload.plan]*payload.months:raise HTTPException(422,'amount_does_not_match_plan_price')
        try:paid_on=date.fromisoformat(payload.paid_on)
        except ValueError:raise HTTPException(422,'invalid_payment_date') from None
        today=datetime.now(UTC).date()
        if paid_on>today+timedelta(days=1) or paid_on<today-timedelta(days=400):raise HTTPException(422,'invalid_payment_date')
        reference=payload.reference.strip()
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            target=c.execute('SELECT email FROM users WHERE id=?',(identifier,)).fetchone()
            if not target:raise HTTPException(404,'User not found')
            row=ensure(c,identifier)
            if row['version']!=payload.expected_version:raise HTTPException(409,'Subscription changed')
            if c.execute("SELECT 1 FROM billing_payments WHERE provider='clip' AND reference=?",(reference,)).fetchone():raise HTTPException(409,'payment_already_recorded')
            start=paid_from(row);end=add_months(start,payload.months)
            c.execute("UPDATE subscriptions SET plan=?,status='active',period_end=?,cancel_at_period_end=0,updated_at=?,version=version+1 WHERE user_id=?",(payload.plan,end.isoformat(),now(),identifier))
            c.execute("INSERT INTO billing_payments(id,user_id,email,plan,months,amount_minor,currency,provider,reference,paid_on,period_start,period_end,note,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,'clip',?,?,?,?,?,?,?)",
                      (str(uuid.uuid4()),identifier,target['email'],payload.plan,payload.months,amount,currency(),reference,paid_on.isoformat(),start.isoformat(),end.isoformat(),payload.note.strip(),user['id'],now()))
            c.execute('UPDATE billing_orders SET completed_at=? WHERE user_id=? AND completed_at IS NULL',(now(),identifier))
            audit(c,user['id'],identifier,'payment_recorded',f'{payload.plan} · {payload.months} · {reference}')
        return {'period_end':end.isoformat()}

    @r.put('/api/admin/billing/{identifier}')
    def end_access(identifier:str,payload:AccessControl,user:dict=Depends(require_user)):
        require_operator(user)
        if len(payload.reason.strip())<10:raise HTTPException(422,'Reason required')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM users WHERE id=?',(identifier,)).fetchone():raise HTTPException(404,'User not found')
            row=ensure(c,identifier)
            if row['version']!=payload.expected_version:raise HTTPException(409,'Subscription changed')
            c.execute("UPDATE subscriptions SET status='expired',updated_at=?,version=version+1 WHERE user_id=?",(now(),identifier))
            audit(c,user['id'],identifier,'access_ended',payload.reason.strip())
        return {'saved':True}
    return r
