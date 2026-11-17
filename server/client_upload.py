"""Upload links for clients: the firm creates a link per case, the client opens it without an account and sends files.

The link carries a random token; only its SHA-256 is stored. A link expires, can be revoked and accepts a limited number
of files. Files are checked by extension, size and file signature and land in the inbox (Posteingang) with the case
pre-selected, so the firm looks at them before they become part of the file. The public page shows only the firm name,
the file reference and the firm's message.
"""
import hashlib
import html
import io
import secrets
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

SIGNATURES = {'.pdf': (b'%PDF-',), '.png': (b'\x89PNG\r\n\x1a\n',), '.jpg': (b'\xff\xd8\xff',), '.jpeg': (b'\xff\xd8\xff',),
              '.docx': (b'PK\x03\x04',), '.doc': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',)}
MAX_BYTES = 10 * 1024 * 1024
RATE: dict[str, list[float]] = {}
RATE_LIMIT, RATE_WINDOW = 40, 600


def migrate(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS upload_links(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE, message TEXT NOT NULL DEFAULT '', expires_at TEXT NOT NULL, max_files INTEGER NOT NULL, uploaded INTEGER NOT NULL DEFAULT 0,
        revoked_at TEXT, created_by TEXT, created_at TEXT NOT NULL)''')
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(inbox_documents)')}
    if 'suggested_case_id' not in columns:
        connection.execute('ALTER TABLE inbox_documents ADD COLUMN suggested_case_id TEXT')


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LinkInput(BaseModel):
    model_config = {'extra': 'forbid'}
    days: int = Field(default=14, ge=1, le=60)
    max_files: int = Field(default=20, ge=1, le=50)
    message: str = Field(default='', max_length=1000)


class QrInput(BaseModel):
    model_config = {'extra': 'forbid'}
    text: str = Field(min_length=10, max_length=500)


def limited(address: str) -> bool:
    moment = time.monotonic()
    recent = [stamp for stamp in RATE.get(address, []) if moment - stamp < RATE_WINDOW]
    RATE[address] = recent + [moment]
    return len(recent) >= RATE_LIMIT


def page(firm: str, reference: str, message: str, remaining: int, expires: str, nonce: str) -> str:
    message_html = f'<p class="message">{html.escape(message)}</p>' if message else ''
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Unterlagen senden – {html.escape(firm)}</title>
<style nonce="{nonce}">
:root{{--ink:#1f2d26;--muted:#5d6b60;--accent:#2f5d4d;--line:#d8e0da}}
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:#f4f6f1}}
main{{max-width:620px;margin:0 auto;padding:28px 16px 48px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px;box-shadow:0 2px 10px rgba(30,50,40,.06)}}
h1{{font-size:24px;margin:0 0 4px}}.firm{{color:var(--muted);margin:0 0 16px}}
.message{{background:#eef4ef;border-radius:10px;padding:12px 14px;white-space:pre-wrap;margin:0 0 18px}}
.drop{{border:2px dashed #b9c9bd;border-radius:12px;padding:26px 16px;text-align:center;background:#fafcf9}}
.drop.over{{border-color:var(--accent);background:#eef6f0}}
.buttons{{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px}}
.button{{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 18px;border-radius:10px;border:1px solid var(--accent);background:#fff;color:var(--accent);font:600 15px inherit;cursor:pointer}}
.button.solid{{background:var(--accent);color:#fff}}input[type=file]{{display:none}}
label.field{{display:block;margin-top:16px;font-weight:600;font-size:14px}}
label.field input,label.field textarea{{display:block;width:100%;margin-top:4px;border:1px solid #c8d3cb;border-radius:8px;padding:10px;font:inherit}}
ul{{list-style:none;padding:0;margin:16px 0 0}}li{{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-top:1px solid #edf1ed;font-size:14px}}
li span:last-child{{white-space:nowrap;font-weight:600}}.ok{{color:var(--accent)}}.err{{color:#a33d36}}
.hint{{color:var(--muted);font-size:13px;margin:14px 0 0}}.done{{text-align:center;padding:14px;border-radius:10px;background:#eef6f0;margin-top:16px;font-weight:600}}
</style></head><body><main><div class="card">
<h1>Unterlagen senden</h1><p class="firm">{html.escape(firm)} · Aktenzeichen {html.escape(reference)}</p>{message_html}
<div class="drop" id="drop"><strong>Dateien hierher ziehen</strong><br><span class="hint">oder auswählen – PDF, Fotos (JPG, PNG), Word · bis 10 MB je Datei</span>
<div class="buttons"><button class="button solid" type="button" id="pick">Dateien auswählen</button><button class="button" type="button" id="camera">Foto aufnehmen</button></div>
<input type="file" id="files" multiple accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,image/jpeg,image/png,application/pdf">
<input type="file" id="photo" accept="image/*" capture="environment"></div>
<label class="field">Ihr Name (optional)<input id="name" maxlength="120" autocomplete="name"></label>
<label class="field">Nachricht an die Kanzlei (optional)<textarea id="note" rows="3" maxlength="1000"></textarea></label>
<ul id="list"></ul><div id="done" class="done" hidden>Vielen Dank! Ihre Unterlagen sind bei der Kanzlei angekommen.</div>
<p class="hint">Noch {remaining} Dateien möglich · Link gültig bis {html.escape(expires)}. Die Dateien gehen direkt an die Kanzlei und sind nur dort sichtbar.</p>
</div></main>
<script nonce="{nonce}">
const list=document.getElementById('list'),done=document.getElementById('done');
const send=async file=>{{const row=document.createElement('li');row.innerHTML='<span></span><span>wird gesendet …</span>';row.firstChild.textContent=file.name;list.appendChild(row);
 const body=new FormData();body.append('file',file);body.append('name',document.getElementById('name').value);body.append('note',document.getElementById('note').value);
 try{{const r=await fetch(location.pathname,{{method:'POST',headers:{{'X-Schimmelpilz-Request':'1'}},body}});const j=await r.json().catch(()=>({{}}));
  if(r.ok){{row.lastChild.textContent='angekommen';row.lastChild.className='ok';done.hidden=false;}}else{{row.lastChild.textContent=j.message||'nicht gesendet';row.lastChild.className='err';}}}}
 catch{{row.lastChild.textContent='Verbindung fehlgeschlagen';row.lastChild.className='err';}}}};
const take=async files=>{{for(const file of files)await send(file);}};
for(const [button,input] of [['pick','files'],['camera','photo']]){{document.getElementById(button).onclick=()=>document.getElementById(input).click();
 document.getElementById(input).onchange=event=>{{take([...event.target.files]);event.target.value='';}};}}
const drop=document.getElementById('drop');drop.ondragover=event=>{{event.preventDefault();drop.classList.add('over');}};drop.ondragleave=()=>drop.classList.remove('over');
drop.ondrop=event=>{{event.preventDefault();drop.classList.remove('over');take([...event.dataTransfer.files]);}};
</script></body></html>'''


def closed_page(text: str) -> str:
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">'
            '<title>Link nicht verfügbar</title></head><body style="font:16px/1.5 system-ui,sans-serif;background:#f4f6f1;color:#1f2d26;margin:0">'
            f'<main style="max-width:560px;margin:40px auto;padding:24px;background:#fff;border-radius:14px;border:1px solid #d8e0da"><h1 style="font-size:22px;margin-top:0">Link nicht verfügbar</h1><p>{html.escape(text)}</p></main></body></html>')


def router(db, require_user, now, record_activity, upload_dir):
    routes = APIRouter()

    def owned_case(connection, case_id, user):
        row = connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (case_id, user['id'])).fetchone()
        if not row or (user.get('allowed_cases') is not None and case_id not in user['allowed_cases']):
            raise HTTPException(404, 'Case not found')
        return row

    def public_link(row):
        today = now()
        state = 'revoked' if row['revoked_at'] else 'expired' if row['expires_at'] < today else 'full' if row['uploaded'] >= row['max_files'] else 'active'
        return {key: row[key] for key in ('id', 'message', 'expires_at', 'max_files', 'uploaded', 'revoked_at', 'created_at')} | {'state': state}

    def active(connection, token):
        row = connection.execute('SELECT * FROM upload_links WHERE token_hash=?', (digest(token),)).fetchone() if 16 <= len(token) <= 100 else None
        if not row or row['revoked_at'] or row['expires_at'] < now():
            return None, 'Dieser Link ist abgelaufen oder wurde von der Kanzlei beendet. Bitte fragen Sie dort nach einem neuen Link.'
        if row['uploaded'] >= row['max_files']:
            return None, 'Über diesen Link wurden bereits alle möglichen Dateien gesendet. Bitte fragen Sie die Kanzlei nach einem neuen Link.'
        return row, ''

    @routes.get('/api/cases/{case_id}/upload-links')
    def list_links(case_id: str, user: dict = Depends(require_user)):
        with db() as connection:
            owned_case(connection, case_id, user)
            return [public_link(row) for row in connection.execute('SELECT * FROM upload_links WHERE case_id=? ORDER BY created_at DESC', (case_id,))]

    @routes.post('/api/cases/{case_id}/upload-links', status_code=201)
    def create_link(case_id: str, payload: LinkInput, user: dict = Depends(require_user)):
        token = secrets.token_urlsafe(24)
        with db() as connection:
            case = owned_case(connection, case_id, user)
            expires = (datetime.fromisoformat(now()) + timedelta(days=payload.days)).isoformat()
            identifier = str(uuid.uuid4())
            connection.execute('INSERT INTO upload_links VALUES(?,?,?,?,?,?,?,?,?,?,?)', (identifier, user['id'], case_id, digest(token), payload.message.strip(), expires,
                                                                                     payload.max_files, 0, None, user.get('actor_id', user['id']), now()))
            record_activity(connection, case_id, 'upload_link_created', f'gültig bis {expires[:10]}')
            row = connection.execute('SELECT * FROM upload_links WHERE id=?', (identifier,)).fetchone()
            return public_link(row) | {'token': token, 'path': f'/api/public/upload/{token}', 'reference': case['reference']}

    @routes.delete('/api/cases/{case_id}/upload-links/{link_id}', status_code=204)
    def revoke_link(case_id: str, link_id: str, user: dict = Depends(require_user)):
        with db() as connection:
            owned_case(connection, case_id, user)
            if not connection.execute('UPDATE upload_links SET revoked_at=? WHERE id=? AND case_id=? AND revoked_at IS NULL', (now(), link_id, case_id)).rowcount:
                raise HTTPException(404, 'Not found')
            record_activity(connection, case_id, 'upload_link_revoked', '')
        return Response(status_code=204)

    @routes.post('/api/upload-links/qr')
    def qr(payload: QrInput, user: dict = Depends(require_user)):
        import segno
        output = io.BytesIO()
        segno.make(payload.text, error='m').save(output, kind='svg', scale=6, border=2, dark='#1f2d26')
        return Response(output.getvalue(), media_type='image/svg+xml')

    @routes.get('/api/public/upload/{token}', response_class=HTMLResponse)
    def upload_page(token: str):
        headers = {'X-Robots-Tag': 'noindex', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'}
        with db() as connection:
            row, problem = active(connection, token)
            if not row:
                return HTMLResponse(closed_page(problem), status_code=410, headers=headers)
            case = connection.execute('SELECT reference FROM cases WHERE id=?', (row['case_id'],)).fetchone()
            owner = connection.execute('SELECT organisation, full_name FROM users WHERE id=?', (row['user_id'],)).fetchone()
        nonce = secrets.token_urlsafe(16)
        headers['Content-Security-Policy'] = f"default-src 'none'; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; connect-src 'self'; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        expires = date.fromisoformat(row['expires_at'][:10]).strftime('%d.%m.%Y')
        return HTMLResponse(page(owner['organisation'] or owner['full_name'], case['reference'], row['message'], row['max_files'] - row['uploaded'], expires, nonce), headers=headers)

    @routes.post('/api/public/upload/{token}', status_code=201)
    async def upload(token: str, request: Request, file: UploadFile = File(...), name: str = Form(default=''), note: str = Form(default='')):
        address = request.client.host if request.client else 'unknown'
        if limited(address):
            raise HTTPException(429, detail='too_many')
        original = Path((file.filename or 'Datei').replace('\\', '/')).name[:200] or 'Datei'
        extension = Path(original).suffix.lower()
        try:
            content = await file.read(MAX_BYTES + 1)
        finally:
            await file.close()
        if extension not in SIGNATURES:
            return Response('{"detail":"type","message":"Dateityp nicht erlaubt (PDF, JPG, PNG, Word)"}', status_code=415, media_type='application/json')
        if not content:
            return Response('{"detail":"empty","message":"Datei ist leer"}', status_code=422, media_type='application/json')
        if len(content) > MAX_BYTES:
            return Response('{"detail":"size","message":"Datei ist größer als 10 MB"}', status_code=413, media_type='application/json')
        if not content.startswith(SIGNATURES[extension]):
            return Response('{"detail":"content","message":"Dateiinhalt passt nicht zur Endung"}', status_code=415, media_type='application/json')
        name, note = ' '.join(name.split())[:120], note.strip()[:1000]
        identifier = str(uuid.uuid4())
        target = upload_dir() / f'{identifier}{extension}'
        kinds = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.doc': 'application/msword',
                 '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row, problem = active(connection, token)
            if not row:
                return Response('{"detail":"closed","message":"Link abgelaufen oder ausgeschöpft"}', status_code=410, media_type='application/json')
            case = connection.execute('SELECT reference FROM cases WHERE id=?', (row['case_id'],)).fetchone()
            target.write_bytes(content)
            try:
                connection.execute('''INSERT INTO inbox_documents(id,user_id,original_name,stored_name,content_type,size_bytes,sha256,subject,sender,received_on,note,created_at,suggested_case_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (identifier, row['user_id'], original, target.name, kinds[extension], len(content), hashlib.sha256(content).hexdigest(),
                                                           f'Mandanten-Upload zu {case["reference"]}', f'Upload-Link{": " + name if name else ""}', now()[:10], note, now(), row['case_id']))
                connection.execute('UPDATE upload_links SET uploaded=uploaded+1 WHERE id=?', (row['id'],))
                record_activity(connection, row['case_id'], 'client_upload', original + (f' (von {name})' if name else ''))
                title = 'Mandanten-Upload im Posteingang prüfen und zuordnen'
                today = now()[:10]
                if not connection.execute('SELECT 1 FROM tasks WHERE case_id=? AND title=? AND completed=0', (row['case_id'], title)).fetchone():
                    connection.execute('INSERT INTO tasks(id, case_id, title, note, due_on, priority, created_at, kind, due_time, pre_days) VALUES (?,?,?,?,?,?,?,?,?,?)',
                                       (str(uuid.uuid4()), row['case_id'], title, 'Neue Unterlagen über den Upload-Link.', today, 'high', now(), 'task', None, 0))
            except Exception:
                target.unlink(missing_ok=True)
                raise
        return {'ok': True, 'name': original}

    return routes
