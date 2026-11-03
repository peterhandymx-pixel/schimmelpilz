"""Manual import of email attachments from the account owner's own IMAP mailbox into the Posteingang.

- Each owner configures one mailbox. The password is encrypted with a key stored in DATA_DIR (not in the database).
  Backups exclude keys, so after a restore the mailbox password must be entered again.
- Fetching is an explicit action. Messages are read with BODY.PEEK (they stay unread) and are never deleted or moved.
- Only attachments with permitted file types and sizes become inbox entries; assignment to a case stays manual.
- Hosts that resolve to private, loopback or link-local addresses are refused unless MAILBOX_ALLOW_PRIVATE_HOSTS=true,
  so the server cannot be used to probe its own network.
"""
import email
import hashlib
import imaplib
import ipaddress
import os
import socket
import ssl
import uuid
from datetime import UTC, datetime
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

MAX_MESSAGES = 25
MAX_MESSAGE_BYTES = 30 * 1024 * 1024
TIMEOUT = 20


def migrate(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS mailbox_settings(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,host TEXT NOT NULL,port INTEGER NOT NULL,
            security TEXT NOT NULL,username TEXT NOT NULL,password_encrypted TEXT NOT NULL,folder TEXT NOT NULL,last_fetch_at TEXT,last_result TEXT,version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS mailbox_messages(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,message_key TEXT NOT NULL,imported_at TEXT NOT NULL,attachments INTEGER NOT NULL,PRIMARY KEY(user_id,message_key));
    ''')


def cipher(data_dir):
    path = Path(data_dir) / 'mailbox.key'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('xb') as stream:
                os.chmod(path, 0o600)
                stream.write(Fernet.generate_key())
        except FileExistsError:
            pass
    return Fernet(path.read_bytes().strip())


def check_host(host, port):
    if os.getenv('MAILBOX_ALLOW_PRIVATE_HOSTS', '').lower() == 'true':
        return
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except OSError:
        raise HTTPException(422, 'mailbox_host_not_found') from None
    for address in addresses:
        ip = ipaddress.ip_address(address.split('%')[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise HTTPException(422, 'mailbox_host_not_public')


def connect(settings, password):
    check_host(settings['host'], settings['port'])
    context = ssl.create_default_context()
    try:
        if settings['security'] == 'ssl':
            client = imaplib.IMAP4_SSL(settings['host'], settings['port'], ssl_context=context, timeout=TIMEOUT)
        else:
            client = imaplib.IMAP4(settings['host'], settings['port'], timeout=TIMEOUT)
            client.starttls(ssl_context=context)
        client.login(settings['username'], password)
    except imaplib.IMAP4.error:
        raise HTTPException(422, 'mailbox_login_failed') from None
    except (OSError, ssl.SSLError):
        raise HTTPException(503, 'mailbox_unreachable') from None
    return client


def clean_header(value, limit):
    text = ' '.join(str(value or '').split())
    return ''.join(c for c in text if ord(c) >= 32 and ord(c) != 127)[:limit]


def clean_filename(name):
    name = Path((name or '').replace('\\', '/')).name
    return ''.join(c for c in name if ord(c) >= 32 and ord(c) != 127 and c not in '<>:"|?*')


class MailboxInput(BaseModel):
    model_config = {'extra': 'forbid'}
    host: str = Field(min_length=3, max_length=253, pattern=r'^[A-Za-z0-9.-]+$')
    port: Literal[993, 143] = 993
    security: Literal['ssl', 'starttls'] = 'ssl'
    username: str = Field(min_length=1, max_length=254)
    password: str | None = Field(default=None, max_length=512)
    folder: str = Field(default='INBOX', min_length=1, max_length=100, pattern=r'^[^"\r\n\\]+$')

    @field_validator('username', mode='before')
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


def router(db, require_user, now, upload_dir, data_dir, max_bytes, allowed_extensions):
    routes = APIRouter()

    def owner_only(user):
        if user.get('workspace_role', 'owner') != 'owner':
            raise HTTPException(403, 'workspace_owner_required_for_mailbox')

    def public(row):
        if not row:
            return {'configured': False}
        return {'configured': True, **{key: row[key] for key in ('host', 'port', 'security', 'username', 'folder', 'last_fetch_at', 'last_result', 'version')}}

    @routes.get('/api/inbox/mailbox')
    def read_settings(user: dict = Depends(require_user)):
        owner_only(user)
        with db() as connection:
            return public(connection.execute('SELECT * FROM mailbox_settings WHERE user_id=?', (user['id'],)).fetchone())

    @routes.put('/api/inbox/mailbox')
    def save_settings(payload: MailboxInput, user: dict = Depends(require_user)):
        owner_only(user)
        check_host(payload.host, payload.port)
        with db() as connection:
            existing = connection.execute('SELECT * FROM mailbox_settings WHERE user_id=?', (user['id'],)).fetchone()
            if payload.password:
                encrypted = cipher(data_dir()).encrypt(payload.password.encode()).decode()
            elif existing:
                encrypted = existing['password_encrypted']
            else:
                raise HTTPException(422, 'mailbox_password_required')
            connection.execute('''INSERT INTO mailbox_settings(user_id,host,port,security,username,password_encrypted,folder) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET host=excluded.host,port=excluded.port,security=excluded.security,username=excluded.username,
                password_encrypted=excluded.password_encrypted,folder=excluded.folder,version=mailbox_settings.version+1''',
                               (user['id'], payload.host.lower(), payload.port, payload.security, payload.username, encrypted, payload.folder))
            return public(connection.execute('SELECT * FROM mailbox_settings WHERE user_id=?', (user['id'],)).fetchone())

    @routes.delete('/api/inbox/mailbox', status_code=204)
    def remove_settings(user: dict = Depends(require_user)):
        owner_only(user)
        with db() as connection:
            connection.execute('DELETE FROM mailbox_settings WHERE user_id=?', (user['id'],))

    @routes.post('/api/inbox/mailbox/fetch')
    def fetch(user: dict = Depends(require_user)):
        owner_only(user)
        with db() as connection:
            settings = connection.execute('SELECT * FROM mailbox_settings WHERE user_id=?', (user['id'],)).fetchone()
        if not settings:
            raise HTTPException(409, 'mailbox_not_configured')
        try:
            password = cipher(data_dir()).decrypt(settings['password_encrypted'].encode()).decode()
        except InvalidToken:
            raise HTTPException(409, 'mailbox_password_unreadable_enter_again') from None
        client = connect(settings, password)
        imported, skipped, written = [], 0, []
        try:
            status, _ = client.select(f'"{settings["folder"]}"', readonly=True)
            if status != 'OK':
                raise HTTPException(422, 'mailbox_folder_not_found')
            status, data = client.uid('SEARCH', None, 'UNSEEN')
            uids = (data[0] or b'').split()[-MAX_MESSAGES:] if status == 'OK' else []
            for uid in uids:
                status, size_data = client.uid('FETCH', uid, '(RFC822.SIZE)')
                size_text = (size_data[0] or b'').decode(errors='ignore') if status == 'OK' and size_data and isinstance(size_data[0], bytes) else ''
                size = int(size_text.split('RFC822.SIZE')[1].strip(' )').split()[0]) if 'RFC822.SIZE' in size_text else 0
                if size > MAX_MESSAGE_BYTES:
                    skipped += 1
                    continue
                status, parts = client.uid('FETCH', uid, '(BODY.PEEK[])')
                raw = next((part[1] for part in parts if isinstance(part, tuple)), None) if status == 'OK' else None
                if not raw:
                    continue
                message = email.message_from_bytes(raw, policy=policy.default)
                key = hashlib.sha256((clean_header(message['Message-ID'], 500) or hashlib.sha256(raw).hexdigest()).encode()).hexdigest()
                with db() as connection:
                    if connection.execute('SELECT 1 FROM mailbox_messages WHERE user_id=? AND message_key=?', (user['id'], key)).fetchone():
                        continue
                try:
                    received = parsedate_to_datetime(message['Date']).date().isoformat()
                except (TypeError, ValueError, IndexError):
                    received = datetime.now(UTC).date().isoformat()
                name, address = parseaddr(str(message['From'] or ''))
                sender = clean_header(f'{name} <{address}>' if name and address else address or name, 160)
                subject = clean_header(message['Subject'], 160)
                count = 0
                for attachment in message.iter_attachments():
                    original = clean_filename(attachment.get_filename())
                    extension = Path(original).suffix.lower()
                    if extension not in allowed_extensions:
                        continue
                    content = attachment.get_payload(decode=True) or b''
                    if not content or len(content) > max_bytes:
                        continue
                    if len(original) > 240:
                        original = original[:240 - len(extension)] + extension
                    identifier = str(uuid.uuid4())
                    target = upload_dir() / (identifier + extension)
                    target.write_bytes(content)
                    written.append(target)
                    with db() as connection:
                        connection.execute('''INSERT INTO inbox_documents(id,user_id,original_name,stored_name,content_type,size_bytes,sha256,subject,sender,received_on,note,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (identifier, user['id'], original, target.name, attachment.get_content_type(), len(content),
                                                                 hashlib.sha256(content).hexdigest(), subject, sender, received, 'Aus E-Mail-Postfach importiert', now()))
                    imported.append({'id': identifier, 'name': original, 'subject': subject, 'sender': sender})
                    count += 1
                with db() as connection:
                    connection.execute('INSERT OR IGNORE INTO mailbox_messages VALUES(?,?,?,?)', (user['id'], key, now(), count))
                if not count:
                    skipped += 1
        except HTTPException:
            raise
        except (imaplib.IMAP4.error, OSError, ssl.SSLError):
            raise HTTPException(503, 'mailbox_unreachable') from None
        finally:
            try:
                client.logout()
            except Exception:
                pass
        result = f'{len(imported)} imported, {skipped} skipped'
        with db() as connection:
            connection.execute('UPDATE mailbox_settings SET last_fetch_at=?,last_result=? WHERE user_id=?', (now(), result, user['id']))
        return {'imported': imported, 'skipped_messages': skipped}

    return routes
