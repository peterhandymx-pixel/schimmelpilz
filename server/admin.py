"""Operator back office: overview, user management, billing actions, tools and audit log.

Every route requires an active operator (administrator with two-factor sign-in, and on the ADMIN_EMAILS allowlist when it
is set). Every change needs a reason and is written to the operator audit log.
"""
import csv
import io
import os
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from . import billing, mailer
from .account import RESET_HOURS, app_url
from .auth import token_hash
from .control import audit, require_operator
from .deletion import delete_account_data, remove_files


class Reason(BaseModel):
    model_config = {'extra': 'forbid'}
    reason: str = Field(min_length=10, max_length=500)

    @field_validator('reason')
    @classmethod
    def stripped(cls, value):
        value = value.strip()
        if len(value) < 10:
            raise ValueError('Reason required')
        return value


class ProfileEdit(Reason):
    full_name: str = Field(min_length=3, max_length=160)
    organisation: str = Field(default='', max_length=160)
    email: str = Field(max_length=254)
    phone: str = Field(default='', max_length=60)
    audience: Literal['consumer', 'business', 'law_firm']
    expected_version: int = Field(ge=0)

    @field_validator('email')
    @classmethod
    def email_value(cls, value):
        value = value.strip().lower()
        if '@' not in value or any(c.isspace() for c in value):
            raise ValueError('Invalid email')
        return value


class TrialExtension(Reason):
    days: int = Field(ge=1, le=90)
    expected_version: int


class PlanChange(Reason):
    plan: Literal['personal', 'business', 'firm']
    expected_version: int


class FreeMonths(Reason):
    plan: Literal['personal', 'business', 'firm']
    months: int = Field(ge=1, le=12)
    expected_version: int


class TestMail(BaseModel):
    to: str = Field(max_length=254)


def router(db, require_user, now, upload_dir, data_dir, system_status):
    r = APIRouter()

    def operator(user):
        require_operator(user)
        return user

    def target_user(c, identifier):
        row = c.execute('SELECT * FROM users WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, 'User not found')
        return row

    def subscription_view(row):
        data = dict(row)
        return {**{k: v for k, v in data.items() if k not in {'customer_id', 'subscription_id'}},
                'effective_status': billing.effective(data), 'renewal_due': billing.renewal_due(data)}

    def recalculate(c, identifier):
        # Paid access ends with the latest payment that has not been reversed; without one the trial decides.
        latest = c.execute('SELECT plan,period_end FROM billing_payments WHERE user_id=? AND reversed_at IS NULL ORDER BY period_end DESC LIMIT 1', (identifier,)).fetchone()
        row = billing.ensure(c, identifier)
        if latest:
            c.execute("UPDATE subscriptions SET plan=?,status='active',period_end=?,updated_at=?,version=version+1 WHERE user_id=?", (latest['plan'], latest['period_end'], now(), identifier))
        else:
            trial_live = row['trial_end'] and datetime.fromisoformat(row['trial_end']) > datetime.now(UTC)
            c.execute('UPDATE subscriptions SET status=?,period_end=NULL,updated_at=?,version=version+1 WHERE user_id=?', ('trial' if trial_live else 'expired', now(), identifier))

    # ---------- overview ----------
    @r.get('/api/admin/overview')
    def overview(user: dict = Depends(require_user)):
        operator(user)
        today = datetime.now(UTC)
        with db() as c:
            for row in c.execute('SELECT id FROM users').fetchall():
                billing.ensure(c, row['id'])
            subs = [dict(row) for row in c.execute('SELECT s.*,u.email,u.full_name FROM subscriptions s JOIN users u ON u.id=s.user_id')]
            states = {}
            for item in subs:
                state = billing.effective(item)
                states[state] = states.get(state, 0) + 1
            soon = (today + timedelta(days=7)).isoformat()
            ending = [{'user_id': item['user_id'], 'email': item['email'], 'full_name': item['full_name'], 'status': billing.effective(item),
                       'ends': item['period_end'] if billing.effective(item) == 'active' else item['trial_end']}
                      for item in subs if billing.effective(item) in billing.ACCESS and ((billing.effective(item) == 'active' and item['period_end'] and item['period_end'] <= soon) or (billing.effective(item) == 'trial' and item['trial_end'] and item['trial_end'] <= soon))]
            months = {}
            for row in c.execute("SELECT substr(paid_on,1,7) AS month,provider,SUM(amount_minor) AS total,COUNT(*) AS n FROM billing_payments WHERE reversed_at IS NULL AND paid_on>=? GROUP BY month,provider", ((today - timedelta(days=366)).date().isoformat(),)):
                entry = months.setdefault(row['month'], {'month': row['month'], 'paid': 0, 'test': 0, 'count': 0})
                entry['test' if row['provider'] == 'demo' else 'paid'] += row['total']
                entry['count'] += row['n']
            signups = c.execute('SELECT COUNT(*) FROM users WHERE created_at>=?', ((today - timedelta(days=30)).isoformat(),)).fetchone()[0]
            counts = {table: c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('users', 'cases', 'documents', 'drafts', 'contacts')}
            counts['sessions'] = c.execute('SELECT COUNT(*) FROM sessions WHERE expires_at>?', (today.isoformat(),)).fetchone()[0]
            payments = [dict(row) for row in c.execute('SELECT p.*,u.full_name FROM billing_payments p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.created_at DESC LIMIT 8')]
        storage = sum(path.stat().st_size for path in upload_dir().glob('*') if path.is_file()) if upload_dir().exists() else 0
        return {'counts': counts, 'subscriptions': states, 'signups_30d': signups, 'ending_soon': sorted(ending, key=lambda item: item['ends'] or ''),
                'revenue': sorted(months.values(), key=lambda item: item['month']), 'recent_payments': payments, 'currency': billing.currency(),
                'storage_bytes': storage, 'payment_mode': 'demo' if billing.demo_mode() else 'clip'}

    # ---------- users ----------
    @r.get('/api/admin/users/{identifier}')
    def user_detail(identifier: str, user: dict = Depends(require_user)):
        operator(user)
        with db() as c:
            row = target_user(c, identifier)
            sub = billing.ensure(c, identifier)
            count = lambda sql: c.execute(sql, (identifier,)).fetchone()[0]
            return {
                'user': {k: row[k] for k in ('id', 'email', 'full_name', 'organisation', 'audience', 'street', 'postal_code', 'city', 'country', 'phone', 'created_at', 'is_admin', 'disabled', 'control_version', 'email_verified_at', 'mfa_enabled_at', 'password_changed_at')},
                'subscription': subscription_view(sub),
                'payments': [dict(p) for p in c.execute('SELECT * FROM billing_payments WHERE user_id=? ORDER BY created_at DESC', (identifier,))],
                'counts': {'cases': count('SELECT COUNT(*) FROM cases WHERE user_id=?'),
                           'documents': count('SELECT COUNT(*) FROM documents WHERE case_id IN (SELECT id FROM cases WHERE user_id=?)'),
                           'drafts': count('SELECT COUNT(*) FROM drafts WHERE case_id IN (SELECT id FROM cases WHERE user_id=?)'),
                           'contacts': count('SELECT COUNT(*) FROM contacts WHERE user_id=?'),
                           'sessions': c.execute('SELECT COUNT(*) FROM sessions WHERE user_id=? AND expires_at>?', (identifier, datetime.now(UTC).isoformat())).fetchone()[0]},
                'team': {'members': [dict(m) for m in c.execute('SELECT u.email,m.role,m.enabled FROM team_members m JOIN users u ON u.id=m.user_id WHERE m.owner_id=?', (identifier,))],
                         'member_of': [dict(m) for m in c.execute('SELECT u.email,m.role,m.enabled FROM team_members m JOIN users u ON u.id=m.owner_id WHERE m.user_id=?', (identifier,))]},
                'audit': [dict(a) for a in c.execute('SELECT a.action,a.target,a.created_at,u.email AS actor_email FROM operator_audit a LEFT JOIN users u ON u.id=a.actor_id WHERE a.target LIKE ? OR a.workspace_id=? ORDER BY a.created_at DESC LIMIT 30', ('%' + identifier + '%', identifier))],
            }

    @r.put('/api/admin/users/{identifier}/profile')
    def edit_profile(identifier: str, payload: ProfileEdit, user: dict = Depends(require_user)):
        operator(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = target_user(c, identifier)
            if row['control_version'] != payload.expected_version:
                raise HTTPException(409, 'User changed')
            if payload.email != row['email'] and c.execute('SELECT 1 FROM users WHERE email=?', (payload.email,)).fetchone():
                raise HTTPException(409, 'email_taken')
            verified = row['email_verified_at'] if payload.email == row['email'] else None
            c.execute('UPDATE users SET full_name=?,organisation=?,email=?,phone=?,audience=?,email_verified_at=?,control_version=control_version+1 WHERE id=?',
                      (payload.full_name.strip(), payload.organisation.strip(), payload.email, payload.phone.strip(), payload.audience, verified, identifier))
            changes = [name for name in ('full_name', 'organisation', 'email', 'phone', 'audience') if str(getattr(payload, name)).strip() != str(row[name])]
            audit(c, user['id'], identifier, 'admin_profile_edit', f'{identifier} · {", ".join(changes) or "-"} · {payload.reason}')
        return {'saved': True}

    @r.post('/api/admin/users/{identifier}/verify-email')
    def verify_email(identifier: str, payload: Reason, user: dict = Depends(require_user)):
        operator(user)
        with db() as c:
            target_user(c, identifier)
            c.execute('UPDATE users SET email_verified_at=COALESCE(email_verified_at,?),control_version=control_version+1 WHERE id=?', (now(), identifier))
            audit(c, user['id'], identifier, 'admin_email_verified', f'{identifier} · {payload.reason}')
        return {'saved': True}

    @r.post('/api/admin/users/{identifier}/password-reset')
    def password_reset(identifier: str, payload: Reason, request: Request, user: dict = Depends(require_user)):
        # A one-hour, single-use link. It is mailed when mail is set up; the operator always gets it to pass on securely.
        operator(user)
        token = secrets.token_urlsafe(32)
        with db() as c:
            row = target_user(c, identifier)
            c.execute('INSERT INTO password_resets VALUES(?,?,?,NULL,?)', (token_hash(token), identifier, (datetime.now(UTC) + timedelta(hours=RESET_HOURS)).isoformat(), now()))
            audit(c, user['id'], identifier, 'admin_password_reset', f'{identifier} · {payload.reason}')
        link = f'{app_url(request) or ""}/?reset={quote(token)}'
        mailed = False
        if mailer.configured():
            try:
                mailer.send(row['email'], 'Schimmelpilz: Passwort zurücksetzen',
                            f'Guten Tag {row["full_name"]},\n\nder Support hat für Ihr Konto einen Link zum Zurücksetzen des Passworts erstellt:\n{link}\n\n'
                            f'Der Link ist {RESET_HOURS} Stunde gültig und nur einmal verwendbar.\n')
                mailed = True
            except mailer.MailUnavailable:
                pass
        return {'link': link, 'mailed': mailed, 'expires_hours': RESET_HOURS}

    @r.post('/api/admin/users/{identifier}/reset-mfa')
    def reset_mfa(identifier: str, payload: Reason, user: dict = Depends(require_user)):
        operator(user)
        if identifier == user['id']:
            raise HTTPException(409, 'Cannot reset your own second factor here')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            target_user(c, identifier)
            c.execute('UPDATE users SET mfa_secret=NULL,mfa_pending_secret=NULL,mfa_enabled_at=NULL,mfa_last_step=NULL,control_version=control_version+1 WHERE id=?', (identifier,))
            c.execute('DELETE FROM mfa_recovery_codes WHERE user_id=?', (identifier,))
            c.execute('DELETE FROM sessions WHERE user_id=?', (identifier,))
            audit(c, user['id'], identifier, 'admin_mfa_reset', f'{identifier} · {payload.reason}')
        return {'saved': True}

    @r.delete('/api/admin/users/{identifier}', status_code=204)
    def delete_user(identifier: str, confirm: str, reason: str = Query(min_length=10, max_length=500), user: dict = Depends(require_user)):
        operator(user)
        if identifier == user['id']:
            raise HTTPException(409, 'Delete your own account under Kanzlei / Profil')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = target_user(c, identifier)
            if confirm.strip().lower() != row['email']:
                raise HTTPException(422, 'confirmation_mismatch')
            if row['is_admin'] and not c.execute('SELECT 1 FROM users WHERE is_admin=1 AND disabled=0 AND id<>? LIMIT 1', (identifier,)).fetchone():
                raise HTTPException(409, 'last_administrator')
            uploads, letterheads = delete_account_data(c, identifier)
            # Payments stay for bookkeeping; the audit entry keeps the address the account had.
            audit(c, user['id'], None, 'admin_user_deleted', f'{row["email"]} · {reason.strip()}')
        remove_files(upload_dir(), uploads)
        remove_files(data_dir() / 'letterheads', letterheads)
        return Response(status_code=204)

    # ---------- billing ----------
    @r.post('/api/admin/billing/{identifier}/extend-trial')
    def extend_trial(identifier: str, payload: TrialExtension, user: dict = Depends(require_user)):
        operator(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            target_user(c, identifier)
            row = billing.ensure(c, identifier)
            if row['version'] != payload.expected_version:
                raise HTTPException(409, 'Subscription changed')
            base = max(datetime.now(UTC), datetime.fromisoformat(row['trial_end'])) if row['trial_end'] else datetime.now(UTC)
            end = base + timedelta(days=payload.days)
            status = row['status'] if billing.effective(dict(row)) == 'active' else 'trial'
            c.execute('UPDATE subscriptions SET status=?,trial_started=COALESCE(trial_started,?),trial_end=?,updated_at=?,version=version+1 WHERE user_id=?', (status, now(), end.isoformat(), now(), identifier))
            audit(c, user['id'], identifier, 'admin_trial_extended', f'{identifier} · +{payload.days} · {payload.reason}')
        return {'trial_end': end.isoformat()}

    @r.put('/api/admin/billing/{identifier}/plan')
    def change_plan(identifier: str, payload: PlanChange, user: dict = Depends(require_user)):
        operator(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            target_user(c, identifier)
            row = billing.ensure(c, identifier)
            if row['version'] != payload.expected_version:
                raise HTTPException(409, 'Subscription changed')
            c.execute('UPDATE subscriptions SET plan=?,updated_at=?,version=version+1 WHERE user_id=?', (payload.plan, now(), identifier))
            audit(c, user['id'], identifier, 'admin_plan_changed', f'{identifier} · {row["plan"]} → {payload.plan} · {payload.reason}')
        return {'saved': True}

    @r.post('/api/admin/billing/{identifier}/free-months', status_code=201)
    def free_months(identifier: str, payload: FreeMonths, user: dict = Depends(require_user)):
        # Goodwill or compensation: booked like a payment of 0 so the period chain and the history stay complete.
        operator(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            target = target_user(c, identifier)
            row = billing.ensure(c, identifier)
            if row['version'] != payload.expected_version:
                raise HTTPException(409, 'Subscription changed')
            start = billing.paid_from(row)
            end = billing.add_months(start, payload.months)
            reference = 'FREI-' + uuid.uuid4().hex[:10].upper()
            c.execute("UPDATE subscriptions SET plan=?,status='active',period_end=?,cancel_at_period_end=0,updated_at=?,version=version+1 WHERE user_id=?", (payload.plan, end.isoformat(), now(), identifier))
            c.execute("INSERT INTO billing_payments(id,user_id,email,plan,months,amount_minor,currency,provider,reference,paid_on,period_start,period_end,note,recorded_by,created_at) VALUES(?,?,?,?,?,0,?,'manual',?,?,?,?,?,?,?)",
                      (str(uuid.uuid4()), identifier, target['email'], payload.plan, payload.months, billing.currency(), reference, datetime.now(UTC).date().isoformat(), start.isoformat(), end.isoformat(), payload.reason, user['id'], now()))
            audit(c, user['id'], identifier, 'admin_free_months', f'{identifier} · {payload.months} · {reference} · {payload.reason}')
        return {'period_end': end.isoformat(), 'reference': reference}

    @r.post('/api/admin/payments/{payment_id}/reverse')
    def reverse_payment(payment_id: str, payload: Reason, user: dict = Depends(require_user)):
        # Only the latest booking of an account can be reversed, so the remaining periods stay a continuous chain.
        operator(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            payment = c.execute('SELECT * FROM billing_payments WHERE id=?', (payment_id,)).fetchone()
            if not payment:
                raise HTTPException(404, 'Payment not found')
            if payment['reversed_at']:
                raise HTTPException(409, 'already_reversed')
            latest = c.execute('SELECT id FROM billing_payments WHERE user_id=? AND reversed_at IS NULL ORDER BY period_end DESC LIMIT 1', (payment['user_id'],)).fetchone()
            if latest['id'] != payment_id:
                raise HTTPException(409, 'only_latest_payment')
            c.execute('UPDATE billing_payments SET reversed_at=?,reversed_reason=? WHERE id=?', (now(), payload.reason, payment_id))
            if c.execute('SELECT 1 FROM users WHERE id=?', (payment['user_id'],)).fetchone():
                recalculate(c, payment['user_id'])
            audit(c, user['id'], payment['user_id'], 'admin_payment_reversed', f'{payment["user_id"]} · {payment["reference"]} · {payload.reason}')
        return {'saved': True}

    @r.get('/api/admin/payments.csv')
    def payments_csv(user: dict = Depends(require_user)):
        operator(user)
        out = io.StringIO()
        writer = csv.writer(out, delimiter=';')
        writer.writerow(['Zahlungsdatum', 'E-Mail', 'Tarif', 'Monate', 'Betrag', 'Währung', 'Art', 'Referenz', 'Zeitraum von', 'Zeitraum bis', 'Storniert am', 'Notiz'])
        kinds = {'clip': 'Clip', 'demo': 'Testzahlung', 'manual': 'Gutschrift'}
        plans = {'personal': 'Privat', 'business': 'Business', 'firm': 'Kanzlei'}
        with db() as c:
            for p in c.execute('SELECT * FROM billing_payments ORDER BY paid_on DESC,created_at DESC'):
                writer.writerow([p['paid_on'], p['email'], plans.get(p['plan'], p['plan']), p['months'], f'{p["amount_minor"] / 100:.2f}'.replace('.', ','), p['currency'], kinds.get(p['provider'], p['provider']),
                                 p['reference'], p['period_start'][:10], p['period_end'][:10], (p['reversed_at'] or '')[:10], p['note']])
        return Response('﻿' + out.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="Schimmelpilz-Zahlungen.csv"', 'Cache-Control': 'no-store'})

    # ---------- tools ----------
    def outbox_files():
        folder = mailer.outbox()
        if not folder or not folder.exists():
            return []
        return sorted(folder.glob('*.eml'), key=lambda path: path.stat().st_mtime, reverse=True)

    @r.get('/api/admin/tools')
    def tools(user: dict = Depends(require_user)):
        operator(user)
        from email import policy
        from email.parser import BytesParser
        mails = []
        for path in outbox_files()[:30]:
            with path.open('rb') as stream:
                head = BytesParser(policy=policy.default).parse(stream, headersonly=True)
            mails.append({'id': path.stem, 'to': head['To'], 'subject': head['Subject'], 'date': datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()})
        disk = __import__('shutil').disk_usage(data_dir())
        return {**system_status(),
                'mail': {'smtp': bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM')), 'outbox': bool(mailer.outbox()), 'messages': mails},
                'payment_mode': 'demo' if billing.demo_mode() else 'clip', 'links_ready': billing.links_ready(), 'plans': billing.plans(), 'currency': billing.currency(),
                'admin_allowlist': bool(os.getenv('ADMIN_EMAILS', '').strip()),
                'disk': {'free': disk.free, 'total': disk.total}}

    @r.get('/api/admin/tools/mail/{message_id}')
    def outbox_message(message_id: str, user: dict = Depends(require_user)):
        operator(user)
        try:
            uuid.UUID(message_id)
        except ValueError:
            raise HTTPException(404, 'Not found') from None
        match = [path for path in outbox_files() if path.stem == message_id]
        if not match:
            raise HTTPException(404, 'Not found')
        return FileResponse(match[0], media_type='message/rfc822', filename=match[0].name, headers={'Cache-Control': 'no-store'})

    @r.post('/api/admin/tools/test-mail')
    def test_mail(payload: TestMail, user: dict = Depends(require_user)):
        operator(user)
        try:
            mailer.send(payload.to.strip(), 'Schimmelpilz: Testnachricht', 'Diese Testnachricht bestätigt, dass der E-Mail-Versand eingerichtet ist.\n')
        except mailer.MailUnavailable:
            raise HTTPException(503, 'mail_not_configured') from None
        with db() as c:
            audit(c, user['id'], None, 'admin_test_mail', payload.to.strip())
        return {'sent': True, 'outbox': bool(mailer.outbox())}

    # ---------- audit ----------
    @r.get('/api/admin/audit')
    def audit_log(q: str = '', action: str = '', before: str = '', limit: int = Query(default=100, ge=1, le=500), user: dict = Depends(require_user)):
        operator(user)
        sql = 'SELECT a.*,u.email AS actor_email FROM operator_audit a LEFT JOIN users u ON u.id=a.actor_id WHERE 1=1'
        args = []
        if q:
            sql += ' AND (a.target LIKE ? OR u.email LIKE ? OR a.action LIKE ? OR a.workspace_id=?)'
            args += ['%' + q + '%'] * 3 + [q]
        if action:
            sql += ' AND a.action=?'
            args.append(action)
        if before:
            sql += ' AND a.created_at<?'
            args.append(before)
        sql += ' ORDER BY a.created_at DESC LIMIT ?'
        args.append(limit)
        with db() as c:
            rows = [dict(row) for row in c.execute(sql, args)]
            actions = [row[0] for row in c.execute('SELECT DISTINCT action FROM operator_audit ORDER BY action')]
        return {'entries': rows, 'actions': actions}

    return r
