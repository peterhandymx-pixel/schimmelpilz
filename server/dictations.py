"""Office dictation: lawyers record dictations for a case, the typing pool takes and completes them.

Audio is recorded in the browser as plain PCM and uploaded as a mono 16-bit WAV, so insert and
overwrite corrections happen before upload and playback can seek to the exact sample.
Every step (recorded, taken, released, completed, deleted) is written into the case history.
"""
import struct
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

MAX_DICTATION_BYTES = 80 * 1024 * 1024  # about 40 minutes at 16 kHz mono
PRIORITIES = ('normal', 'urgent', 'immediate')
PRIORITY_LABELS = {'normal': 'normal', 'urgent': 'eilig', 'immediate': 'sofort'}
STATUSES = ('open', 'in_progress', 'done')


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS dictations(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        author_id TEXT NOT NULL, author_name TEXT NOT NULL, priority TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
        stored_name TEXT NOT NULL, size_bytes INTEGER NOT NULL, duration_ms INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open', assignee_id TEXT, assignee_name TEXT,
        created_at TEXT NOT NULL, taken_at TEXT, done_at TEXT, done_by_name TEXT, done_note TEXT NOT NULL DEFAULT '',
        version INTEGER NOT NULL DEFAULT 1)''')
    c.execute('CREATE INDEX IF NOT EXISTS dictations_by_workspace ON dictations(user_id, status)')


def wav_duration_ms(content):
    """Duration of a PCM WAV file; rejects anything that is not one."""
    if len(content) < 44 or content[:4] != b'RIFF' or content[8:12] != b'WAVE':
        raise HTTPException(415, 'wav_required')
    position, rate, block, data = 12, None, None, None
    while position + 8 <= len(content):
        chunk, size = content[position:position + 4], struct.unpack('<I', content[position + 4:position + 8])[0]
        if chunk == b'fmt ' and size >= 16:
            audio_format, channels, rate, _, block, bits = struct.unpack('<HHIIHH', content[position + 8:position + 24])
            if audio_format != 1 or channels not in (1, 2) or bits != 16 or not 8000 <= rate <= 48000:
                raise HTTPException(415, 'pcm16_wav_required')
        elif chunk == b'data':
            data = min(size, len(content) - position - 8)
            break
        position += 8 + size + (size & 1)
    if not rate or not block or data is None:
        raise HTTPException(415, 'wav_required')
    duration = round(data / block / rate * 1000)
    if duration < 500:
        raise HTTPException(422, 'dictation_too_short')
    return duration


def minutes(ms):
    seconds = ms // 1000  # same as the player clock
    return f'{seconds // 60}:{seconds % 60:02d} Min.'


class Step(BaseModel):
    model_config = {'extra': 'forbid'}
    expected_version: int = Field(ge=1)


class Completion(Step):
    note: str = Field(default='', max_length=500)


def router(db, require_user, now, record_activity, upload_dir):
    routes = APIRouter()

    def actor(user):
        return user.get('actor_id', user['id']), user['full_name']

    def editable(user):
        if user.get('workspace_role') == 'viewer':
            raise HTTPException(403, 'workspace_read_only')

    def visible(user, case_id):
        allowed = user.get('allowed_cases')
        return allowed is None or case_id in allowed

    def owned(c, user, dictation_id):
        row = c.execute('''SELECT d.*, c.reference, c.title AS case_title FROM dictations d JOIN cases c ON c.id = d.case_id
            WHERE d.id = ? AND d.user_id = ?''', (dictation_id, user['id'])).fetchone()
        if not row or not visible(user, row['case_id']):
            raise HTTPException(404, 'Dictation not found')
        return row

    def public(row):
        item = {key: row[key] for key in row.keys() if key not in ('stored_name', 'user_id')}
        return item

    def changed(row, expected):
        if row['version'] != expected:
            raise HTTPException(409, 'dictation_changed')

    @routes.post('/api/cases/{case_id}/dictations', status_code=201)
    async def record(case_id: str, file: UploadFile = File(...), priority: Literal[PRIORITIES] = Form('normal'), note: str = Form('', max_length=300), user: dict = Depends(require_user)):
        editable(user)
        try:
            content = await file.read(MAX_DICTATION_BYTES + 1)
        finally:
            await file.close()
        if len(content) > MAX_DICTATION_BYTES:
            raise HTTPException(413, 'dictation_too_long')
        duration = wav_duration_ms(content)
        author_id, author_name = actor(user)
        dictation_id = str(uuid.uuid4())
        stored = f'dictation-{dictation_id}.wav'
        folder = Path(upload_dir())
        folder.mkdir(parents=True, exist_ok=True)
        (folder / stored).write_bytes(content)
        try:
            with db() as c:
                if not c.execute('SELECT 1 FROM cases WHERE id = ? AND user_id = ?', (case_id, user['id'])).fetchone() or not visible(user, case_id):
                    raise HTTPException(404, 'Case not found')
                c.execute('''INSERT INTO dictations(id, user_id, case_id, author_id, author_name, priority, note, stored_name, size_bytes, duration_ms, created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (dictation_id, user['id'], case_id, author_id, author_name, priority, note.strip(), stored, len(content), duration, now()))
                record_activity(c, case_id, 'dictation_created', f'{author_name} · {minutes(duration)} · Priorität {PRIORITY_LABELS[priority]}' + (f' · {note.strip()}' if note.strip() else ''))
                return public(owned(c, user, dictation_id))
        except Exception:
            (folder / stored).unlink(missing_ok=True)
            raise

    @routes.get('/api/dictations')
    def pool(status: Literal[STATUSES + ('active', 'all')] = 'active', author_id: str = '', user: dict = Depends(require_user)):
        conditions, values = ['d.user_id = ?'], [user['id']]
        if status == 'active':
            conditions.append("d.status != 'done'")
        elif status != 'all':
            conditions.append('d.status = ?'); values.append(status)
        if author_id:
            conditions.append('d.author_id = ?'); values.append(author_id)
        with db() as c:
            rows = c.execute(f'''SELECT d.*, c.reference, c.title AS case_title FROM dictations d JOIN cases c ON c.id = d.case_id
                WHERE {' AND '.join(conditions)}
                ORDER BY CASE d.status WHEN 'done' THEN 1 ELSE 0 END, CASE d.priority WHEN 'immediate' THEN 0 WHEN 'urgent' THEN 1 ELSE 2 END, d.created_at''', values).fetchall()
            authors = c.execute('SELECT DISTINCT author_id, author_name FROM dictations WHERE user_id = ? ORDER BY author_name', (user['id'],)).fetchall()
        items = [public(row) for row in rows if visible(user, row['case_id'])]
        return {'items': items[:500], 'authors': [dict(row) for row in authors], 'me': actor(user)[0]}

    @routes.get('/api/dictations/{dictation_id}/audio')
    def audio(dictation_id: str, user: dict = Depends(require_user)):
        with db() as c:
            row = owned(c, user, dictation_id)
        root = Path(upload_dir()).resolve()
        target = root / row['stored_name']
        if not target.resolve().is_relative_to(root) or not target.is_file():
            raise HTTPException(404, 'Audio not found')
        return FileResponse(target, media_type='audio/wav', headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})

    @routes.post('/api/dictations/{dictation_id}/take')
    def take(dictation_id: str, payload: Step, user: dict = Depends(require_user)):
        editable(user)
        person, name = actor(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = owned(c, user, dictation_id)
            changed(row, payload.expected_version)
            if row['status'] != 'open':
                raise HTTPException(409, 'dictation_not_open')
            c.execute("UPDATE dictations SET status='in_progress', assignee_id=?, assignee_name=?, taken_at=?, version=version+1 WHERE id=?", (person, name, now(), dictation_id))
            record_activity(c, row['case_id'], 'dictation_taken', f"{name} · Diktat von {row['author_name']}")
            return public(owned(c, user, dictation_id))

    @routes.post('/api/dictations/{dictation_id}/release')
    def release(dictation_id: str, payload: Step, user: dict = Depends(require_user)):
        editable(user)
        person, name = actor(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = owned(c, user, dictation_id)
            changed(row, payload.expected_version)
            if row['status'] != 'in_progress' or (row['assignee_id'] != person and user.get('workspace_role', 'owner') != 'owner'):
                raise HTTPException(409, 'dictation_not_yours')
            c.execute("UPDATE dictations SET status='open', assignee_id=NULL, assignee_name=NULL, taken_at=NULL, version=version+1 WHERE id=?", (dictation_id,))
            record_activity(c, row['case_id'], 'dictation_released', f"{name} · Diktat von {row['author_name']} zurück in den Pool")
            return public(owned(c, user, dictation_id))

    @routes.post('/api/dictations/{dictation_id}/complete')
    def complete(dictation_id: str, payload: Completion, user: dict = Depends(require_user)):
        editable(user)
        person, name = actor(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = owned(c, user, dictation_id)
            changed(row, payload.expected_version)
            if row['status'] == 'done':
                raise HTTPException(409, 'dictation_done')
            if row['status'] == 'in_progress' and row['assignee_id'] != person and user.get('workspace_role', 'owner') != 'owner':
                raise HTTPException(409, 'dictation_not_yours')
            finished = now()
            note = payload.note.strip()
            c.execute('''UPDATE dictations SET status='done', assignee_id=COALESCE(assignee_id, ?), assignee_name=COALESCE(assignee_name, ?),
                taken_at=COALESCE(taken_at, ?), done_at=?, done_by_name=?, done_note=?, version=version+1 WHERE id=?''', (person, name, finished, finished, name, note, dictation_id))
            record_activity(c, row['case_id'], 'dictation_done', f"Diktat von {row['author_name']} ({minutes(row['duration_ms'])}) geschrieben von {name}" + (f' · {note}' if note else ''))
            return public(owned(c, user, dictation_id))

    @routes.delete('/api/dictations/{dictation_id}', status_code=204)
    def remove(dictation_id: str, user: dict = Depends(require_user)):
        editable(user)
        person, name = actor(user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = owned(c, user, dictation_id)
            # Only an untouched dictation can be withdrawn, by its author or the workspace owner.
            if row['status'] != 'open' or (row['author_id'] != person and user.get('workspace_role', 'owner') != 'owner'):
                raise HTTPException(409, 'dictation_in_use')
            c.execute('DELETE FROM dictations WHERE id=?', (dictation_id,))
            record_activity(c, row['case_id'], 'dictation_deleted', f"{name} · {minutes(row['duration_ms'])}")
        (Path(upload_dir()) / row['stored_name']).unlink(missing_ok=True)
        return None

    return routes
