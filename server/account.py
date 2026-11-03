"""Self-service account management: profile, email, password, recovery, verification, two-factor login, deletion."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import time
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import quote, urlsplit

import segno
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from . import mailer
from .auth import COOKIE_NAME, OrganisationProfile, password_hash, verify_password, set_session, token_hash, public_user
from .deletion import delete_account_data, remove_files

RESET_HOURS = 1
VERIFY_HOURS = 48
TOTP_STEP = 30
ISSUER = 'Schimmelpilz'
mail_requests: dict[str, list[float]] = {}


def migrate(connection):
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(users)')}
    for name, definition in (('email_verified_at', 'TEXT'), ('mfa_secret', 'TEXT'), ('mfa_pending_secret', 'TEXT'),
                             ('mfa_enabled_at', 'TEXT'), ('mfa_last_step', 'INTEGER NOT NULL DEFAULT 0'), ('password_changed_at', 'TEXT')):
        if name not in columns:
            connection.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS password_resets(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at TEXT NOT NULL,used_at TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS email_verifications(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,email TEXT NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mfa_recovery_codes(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,code_hash TEXT NOT NULL,used_at TEXT,PRIMARY KEY(user_id,code_hash));
    ''')


# ---------- TOTP (RFC 6238, SHA-1, 6 digits, 30 s) ----------

def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def totp(secret, step):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    return f'{(struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}'


def matching_step(secret, code, last_step=0, now=None):
    """Accept one step of clock drift either way; never accept a step already used (replay)."""
    code = ''.join(ch for ch in (code or '') if ch.isdigit())
    if len(code) != 6:
        return None
    current = int((now if now is not None else time.time()) // TOTP_STEP)
    for step in (current - 1, current, current + 1):
        if step > last_step and hmac.compare_digest(totp(secret, step), code):
            return step
    return None


def recovery_hash(code):
    return hashlib.sha256(code.replace('-', '').strip().lower().encode()).hexdigest()


def check_second_factor(connection, user, code):
    """True when code is a fresh TOTP or an unused recovery code. Consumes what it accepts."""
    if not user['mfa_enabled_at']:
        return True
    if not code:
        return False
    step = matching_step(user['mfa_secret'], code, user['mfa_last_step'])
    if step:
        connection.execute('UPDATE users SET mfa_last_step=? WHERE id=?', (step, user['id']))
        return True
    used = connection.execute('UPDATE mfa_recovery_codes SET used_at=? WHERE user_id=? AND code_hash=? AND used_at IS NULL',
                              (datetime.now(UTC).isoformat(), user['id'], recovery_hash(code)))
    return bool(used.rowcount)


# ---------- helpers ----------

def now():
    return datetime.now(UTC).isoformat()


def app_url(request):
    configured = os.getenv('PUBLIC_APP_URL', '').strip().rstrip('/')
    if configured:
        return configured
    # Local development only: trust the browser's own origin when it is a loopback address.
    # Browsers omit Origin on same-site GET requests, so fall back to the Referer's origin.
    for header in ('origin', 'referer'):
        parts = urlsplit(request.headers.get(header) or '')
        if parts.scheme in {'http', 'https'} and parts.hostname in {'localhost', '127.0.0.1'}:
            return f'{parts.scheme}://{parts.netloc}'
    return None


def mail_ready(request):
    return mailer.configured() and bool(app_url(request))


def mail_limit(key, limit=5, window=3600):
    cutoff = time.time() - window
    for name in list(mail_requests):
        mail_requests[name] = [stamp for stamp in mail_requests[name] if stamp > cutoff]
        if not mail_requests[name]:
            del mail_requests[name]
    if len(mail_requests.get(key, [])) >= limit:
        return False
    mail_requests.setdefault(key, []).append(time.time())
    return True


def client_key(request):
    return request.client.host if request.client else 'local'


def full_user(connection, user_id):
    row = connection.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not row:
        raise HTTPException(401, 'Session expired')
    return row


def require_password(row, password):
    if not verify_password(password or '', row['salt'], row['password_hash']):
        raise HTTPException(403, 'password_incorrect')


def send_verification(connection, request, row):
    token = secrets.token_urlsafe(32)
    connection.execute('INSERT INTO email_verifications VALUES(?,?,?,?,NULL,?)', (token_hash(token), row['id'], row['email'],
                       (datetime.now(UTC) + timedelta(hours=VERIFY_HOURS)).isoformat(), now()))
    link = f'{app_url(request)}/?verify={quote(token)}'
    mailer.send(row['email'], 'Schimmelpilz: E-Mail-Adresse bestätigen / confirm your email',
                f'Guten Tag {row["full_name"]},\n\nbitte bestätigen Sie Ihre E-Mail-Adresse für Schimmelpilz:\n{link}\n\n'
                f'Der Link ist {VERIFY_HOURS} Stunden gültig. Falls Sie kein Konto angelegt haben, ignorieren Sie diese Nachricht.\n\n'
                f'Please confirm your email address for Schimmelpilz using the link above. It expires in {VERIFY_HOURS} hours.\n')


# ---------- inputs ----------

class ProfileUpdate(BaseModel):
    model_config = {'extra': 'forbid'}
    full_name: str = Field(min_length=3, max_length=160)
    organisation: str = Field(default='', max_length=160)
    street: str = Field(min_length=3, max_length=200)
    postal_code: str = Field(min_length=2, max_length=20)
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    phone: str = Field(default='', max_length=60)
    profile: OrganisationProfile = Field(default_factory=OrganisationProfile)

    @field_validator('full_name', 'organisation', 'street', 'postal_code', 'city', 'country', 'phone', mode='before')
    @classmethod
    def strip_input(cls, value):
        return value.strip() if isinstance(value, str) else value


class EmailChange(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email', mode='before')
    @classmethod
    def clean_email(cls, value):
        value = value.strip().lower() if isinstance(value, str) else value
        if not isinstance(value, str) or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
            raise ValueError('A valid email is required')
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class AccountDeletion(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: Literal['LÖSCHEN', 'DELETE']
    mfa_code: str | None = Field(default=None, max_length=20)


class ResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    password: str = Field(min_length=12, max_length=128)


class TokenInput(BaseModel):
    token: str = Field(min_length=20, max_length=128)


class PasswordInput(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class CodeInput(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class MfaDisable(PasswordInput):
    code: str = Field(min_length=6, max_length=20)


def router(db, require_user, upload_dir, data_dir):
    routes = APIRouter()

    @routes.get('/api/auth/capabilities')
    def capabilities(request: Request):
        return {'mail': mail_ready(request)}

    @routes.put('/api/auth/profile')
    def update_profile(payload: ProfileUpdate, user: dict = Depends(require_user)):
        if user['audience'] != 'consumer' and not payload.organisation:
            raise HTTPException(422, 'organisation_required')
        with db() as connection:
            connection.execute('UPDATE users SET full_name=?,organisation=?,street=?,postal_code=?,city=?,country=?,phone=?,profile=? WHERE id=?',
                               (payload.full_name, payload.organisation, payload.street, payload.postal_code, payload.city, payload.country,
                                payload.phone, json.dumps(payload.profile.model_dump(), ensure_ascii=False), user['id']))
            return public_user(full_user(connection, user['id']))

    @routes.put('/api/auth/email')
    def change_email(payload: EmailChange, request: Request, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = full_user(connection, user['id'])
            require_password(row, payload.password)
            if payload.email == row['email']:
                return public_user(row)
            if connection.execute('SELECT 1 FROM users WHERE email=?', (payload.email,)).fetchone():
                raise HTTPException(409, 'Email already registered')
            connection.execute('UPDATE users SET email=?,email_verified_at=NULL WHERE id=?', (payload.email, row['id']))
            connection.execute('UPDATE email_verifications SET used_at=? WHERE user_id=? AND used_at IS NULL', (now(), row['id']))
            row = full_user(connection, row['id'])
            if mail_ready(request):
                try:
                    send_verification(connection, request, row)
                except mailer.MailUnavailable:
                    pass  # The address change stands; the user can request another confirmation.
            return public_user(row)

    @routes.put('/api/auth/password')
    def change_password(payload: PasswordChange, request: Request, response: Response, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = full_user(connection, user['id'])
            require_password(row, payload.current_password)
            if payload.new_password == payload.current_password:
                raise HTTPException(422, 'password_unchanged')
            salt = secrets.token_hex(16)
            connection.execute('UPDATE users SET password_hash=?,salt=?,password_changed_at=? WHERE id=?', (password_hash(payload.new_password, salt), salt, now(), row['id']))
            # Every other device is signed out; this browser receives a fresh session.
            connection.execute('DELETE FROM sessions WHERE user_id=?', (row['id'],))
            connection.execute('UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL', (now(), row['id']))
            set_session(connection, row['id'], request, response)
        return {'changed': True, 'other_sessions_revoked': True}

    @routes.post('/api/auth/account/delete', status_code=204)
    def delete_account(payload: AccountDeletion, request: Request, response: Response, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = full_user(connection, user['id'])
            require_password(row, payload.password)
            if not check_second_factor(connection, row, payload.mfa_code):
                raise HTTPException(403, 'mfa_code_required')
            if row['is_admin'] and not connection.execute('SELECT 1 FROM users WHERE is_admin=1 AND disabled=0 AND id<>? LIMIT 1', (row['id'],)).fetchone():
                raise HTTPException(409, 'last_administrator')
            uploads, letterheads = delete_account_data(connection, row['id'])
        remove_files(upload_dir(), uploads)
        remove_files(data_dir() / 'letterheads', letterheads)
        response.delete_cookie('schimmelpilz_workspace', path='/')
        response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='strict')

    @routes.post('/api/auth/password-reset/request', status_code=202)
    def request_reset(payload: ResetRequest, request: Request):
        email = payload.email.strip().lower()
        # Same answer whether or not the address exists; limits bound mail flooding.
        if not mail_ready(request) or not mail_limit('ip:' + client_key(request), 10) or not mail_limit('reset:' + email, 3):
            return {'accepted': True}
        with db() as connection:
            row = connection.execute('SELECT * FROM users WHERE email=? AND disabled=0', (email,)).fetchone()
            if row:
                token = secrets.token_urlsafe(32)
                connection.execute('INSERT INTO password_resets VALUES(?,?,?,NULL,?)', (token_hash(token), row['id'], (datetime.now(UTC) + timedelta(hours=RESET_HOURS)).isoformat(), now()))
                try:
                    mailer.send(row['email'], 'Schimmelpilz: Passwort zurücksetzen / reset your password',
                                f'Guten Tag {row["full_name"]},\n\nüber folgenden Link können Sie ein neues Passwort festlegen:\n'
                                f'{app_url(request)}/?reset={quote(token)}\n\nDer Link ist {RESET_HOURS} Stunde gültig und nur einmal verwendbar. '
                                'Haben Sie das nicht angefordert, ignorieren Sie diese Nachricht; Ihr Passwort bleibt unverändert.\n\n'
                                'Use the link above to choose a new password. It expires in one hour and works once. '
                                'If you did not request this, ignore this message.\n')
                except mailer.MailUnavailable:
                    pass
        return {'accepted': True}

    @routes.post('/api/auth/password-reset/confirm')
    def confirm_reset(payload: ResetConfirm):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            entry = connection.execute('SELECT * FROM password_resets WHERE token_hash=? AND used_at IS NULL AND expires_at>?', (token_hash(payload.token), now())).fetchone()
            if not entry:
                raise HTTPException(400, 'reset_link_invalid_or_expired')
            salt = secrets.token_hex(16)
            connection.execute('UPDATE users SET password_hash=?,salt=?,password_changed_at=? WHERE id=?', (password_hash(payload.password, salt), salt, now(), entry['user_id']))
            connection.execute('UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL', (now(), entry['user_id']))
            connection.execute('DELETE FROM sessions WHERE user_id=?', (entry['user_id'],))
            # Receiving the reset mail proves control of the address.
            connection.execute('UPDATE users SET email_verified_at=COALESCE(email_verified_at,?) WHERE id=?', (now(), entry['user_id']))
        return {'changed': True}

    @routes.post('/api/auth/verify-email/send', status_code=202)
    def resend_verification(request: Request, user: dict = Depends(require_user)):
        if not mail_ready(request):
            raise HTTPException(503, 'mail_not_configured')
        if not mail_limit('verify:' + user['id'], 3):
            raise HTTPException(429, 'Too many requests')
        with db() as connection:
            row = full_user(connection, user['id'])
            if row['email_verified_at']:
                return {'already_verified': True}
            try:
                send_verification(connection, request, row)
            except mailer.MailUnavailable:
                raise HTTPException(503, 'mail_delivery_failed') from None
        return {'sent': True}

    @routes.post('/api/auth/verify-email/confirm')
    def confirm_verification(payload: TokenInput):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            entry = connection.execute('SELECT * FROM email_verifications WHERE token_hash=? AND used_at IS NULL AND expires_at>?', (token_hash(payload.token), now())).fetchone()
            row = connection.execute('SELECT * FROM users WHERE id=?', (entry['user_id'],)).fetchone() if entry else None
            # A link for an address that was changed afterwards no longer verifies anything.
            if not entry or not row or row['email'] != entry['email']:
                raise HTTPException(400, 'verification_link_invalid_or_expired')
            connection.execute('UPDATE email_verifications SET used_at=? WHERE token_hash=?', (now(), entry['token_hash']))
            connection.execute('UPDATE users SET email_verified_at=? WHERE id=?', (now(), row['id']))
        return {'verified': True}

    @routes.post('/api/auth/mfa/setup')
    def mfa_setup(payload: PasswordInput, user: dict = Depends(require_user)):
        with db() as connection:
            row = full_user(connection, user['id'])
            require_password(row, payload.password)
            if row['mfa_enabled_at']:
                raise HTTPException(409, 'mfa_already_enabled')
            secret = new_secret()
            connection.execute('UPDATE users SET mfa_pending_secret=? WHERE id=?', (secret, row['id']))
        label = quote(f'{ISSUER}:{row["email"]}')
        uri = f'otpauth://totp/{label}?secret={secret}&issuer={ISSUER}&algorithm=SHA1&digits=6&period={TOTP_STEP}'
        # The QR code lets a phone authenticator app scan the setup instead of typing the key.
        return {'secret': secret, 'otpauth_uri': uri, 'qr_svg': segno.make(uri, error='m').svg_data_uri(scale=5, border=2)}

    @routes.post('/api/auth/mfa/enable')
    def mfa_enable(payload: CodeInput, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = full_user(connection, user['id'])
            if row['mfa_enabled_at'] or not row['mfa_pending_secret']:
                raise HTTPException(409, 'mfa_setup_required')
            step = matching_step(row['mfa_pending_secret'], payload.code)
            if not step:
                raise HTTPException(422, 'mfa_code_invalid')
            codes = ['-'.join(secrets.token_hex(2) for _ in range(3)) for _ in range(8)]
            connection.execute('DELETE FROM mfa_recovery_codes WHERE user_id=?', (row['id'],))
            connection.executemany('INSERT INTO mfa_recovery_codes VALUES(?,?,NULL)', [(row['id'], recovery_hash(code)) for code in codes])
            connection.execute('UPDATE users SET mfa_secret=mfa_pending_secret,mfa_pending_secret=NULL,mfa_enabled_at=?,mfa_last_step=? WHERE id=?', (now(), step, row['id']))
        return {'enabled': True, 'recovery_codes': codes}

    @routes.post('/api/auth/mfa/disable')
    def mfa_disable(payload: MfaDisable, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = full_user(connection, user['id'])
            require_password(row, payload.password)
            if not row['mfa_enabled_at']:
                raise HTTPException(409, 'mfa_not_enabled')
            if row['is_admin'] and os.getenv('ADMIN_MFA_REQUIRED', 'true').lower() != 'false':
                raise HTTPException(409, 'administrators_must_keep_mfa')
            if not check_second_factor(connection, row, payload.code):
                raise HTTPException(422, 'mfa_code_invalid')
            connection.execute('UPDATE users SET mfa_secret=NULL,mfa_pending_secret=NULL,mfa_enabled_at=NULL,mfa_last_step=0 WHERE id=?', (row['id'],))
            connection.execute('DELETE FROM mfa_recovery_codes WHERE user_id=?', (row['id'],))
        return {'enabled': False}

    return routes
