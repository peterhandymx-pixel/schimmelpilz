"""Private incoming files, explicitly assigned once to an owned case."""
import hashlib
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError, field_validator


class Metadata(BaseModel):
    model_config = {'extra': 'forbid'}
    subject: str = Field(default='', max_length=160)
    sender: str = Field(default='', max_length=160)
    received_on: date
    note: str = Field(default='', max_length=2000)

    @field_validator('subject', 'sender', 'note', mode='before')
    @classmethod
    def strip_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if any((ord(c) < 32 and c not in '\n\r\t') or ord(c) == 127 for c in value):
                raise ValueError('Control characters are not allowed')
        return value


class MetadataUpdate(Metadata):
    expected_version: int = Field(ge=1)


class Assignment(BaseModel):
    model_config = {'extra': 'forbid'}
    case_id: uuid.UUID
    expected_version: int = Field(ge=1)


class Correction(Assignment):
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator('reason')
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if len(value) < 10 or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
            raise ValueError('A meaningful correction reason is required')
        return value


def migrate(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS inbox_documents (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            original_name TEXT NOT NULL, stored_name TEXT NOT NULL,
            content_type TEXT, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
            subject TEXT NOT NULL, sender TEXT NOT NULL, received_on TEXT NOT NULL,
            note TEXT NOT NULL, created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
            case_id TEXT REFERENCES cases(id), document_id TEXT REFERENCES documents(id),
            assigned_at TEXT
        );
        CREATE INDEX IF NOT EXISTS inbox_owner ON inbox_documents(user_id);
        CREATE TABLE IF NOT EXISTS inbox_corrections (
            id TEXT PRIMARY KEY, inbox_id TEXT NOT NULL REFERENCES inbox_documents(id),
            from_case_id TEXT NOT NULL REFERENCES cases(id), case_id TEXT NOT NULL REFERENCES cases(id),
            old_document_id TEXT NOT NULL REFERENCES documents(id), document_id TEXT NOT NULL REFERENCES documents(id),
            reason TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL
        );
    ''')
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(documents)')}
    for name in ['inbox_reassigned_at', 'inbox_correction_note']:
        if name not in columns:
            connection.execute(f'ALTER TABLE documents ADD COLUMN {name} TEXT')


def router(db, require_user, now, record_activity, upload_directory, max_bytes, allowed_extensions):
    routes = APIRouter()

    def owned(connection, identifier, user_id):
        row = connection.execute('SELECT * FROM inbox_documents WHERE id=? AND user_id=?', (identifier,user_id)).fetchone()
        if not row:
            raise HTTPException(404,'Inbox document not found')
        return row

    def public(connection, row):
        result = {key:row[key] for key in row.keys() if key not in {'user_id','stored_name'}}
        case = connection.execute('SELECT reference,title FROM cases WHERE id=? AND user_id=?', (row['case_id'],row['user_id'])).fetchone()
        result['case_reference'] = case['reference'] if case else None
        result['case_title'] = case['title'] if case else None
        extraction = connection.execute('SELECT status FROM document_extractions WHERE document_id=?',(row['document_id'],)).fetchone()
        result['extraction_status'] = extraction['status'] if extraction else None
        result['reviewed_units'] = connection.execute('SELECT COUNT(*) FROM document_pages WHERE document_id=? AND reviewed_at IS NOT NULL',(row['document_id'],)).fetchone()[0]
        result['corrections'] = [dict(item) for item in connection.execute('''
            SELECT h.version,h.reason,h.created_at,a.reference AS from_reference,b.reference AS to_reference
            FROM inbox_corrections h JOIN cases a ON a.id=h.from_case_id JOIN cases b ON b.id=h.case_id
            WHERE h.inbox_id=? ORDER BY h.version DESC''',(row['id'],))]
        return result

    @routes.get('/api/inbox')
    def list_inbox(user: dict = Depends(require_user)):
        with db() as connection:
            rows = connection.execute('SELECT * FROM inbox_documents WHERE user_id=? ORDER BY created_at DESC,id', (user['id'],)).fetchall()
            return [public(connection,row) for row in rows]

    @routes.post('/api/inbox',status_code=201)
    async def upload_incoming(file: UploadFile = File(...), received_on: str = Form(...), subject: str = Form(''), sender: str = Form(''), note: str = Form(''), user: dict = Depends(require_user)):
        try:
            try:
                metadata = Metadata(subject=subject,sender=sender,received_on=received_on,note=note)
            except ValidationError:
                raise HTTPException(422,'Invalid incoming document metadata') from None
            original = Path((file.filename or 'document').replace('\\','/')).name
            original = ''.join(c for c in original if ord(c) >= 32 and ord(c) != 127)
            extension = Path(original).suffix.lower()
            if extension not in allowed_extensions:
                raise HTTPException(415,'Unsupported document type')
            if len(original) > 240:
                original = original[:240-len(extension)] + extension
            content = await file.read(max_bytes+1)
            if not content:
                raise HTTPException(422,'Document is empty')
            if len(content)>max_bytes:
                raise HTTPException(413,'Document exceeds the 10 MB limit')
        finally:
            await file.close()
        identifier = str(uuid.uuid4())
        stored = identifier + extension
        target = upload_directory()/stored
        target.write_bytes(content)
        try:
            with db() as connection:
                connection.execute('''INSERT INTO inbox_documents(id,user_id,original_name,stored_name,content_type,size_bytes,sha256,subject,sender,received_on,note,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(identifier,user['id'],original,stored,file.content_type,len(content),hashlib.sha256(content).hexdigest(),metadata.subject,metadata.sender,metadata.received_on.isoformat(),metadata.note,now()))
                return public(connection,owned(connection,identifier,user['id']))
        except Exception:
            target.unlink(missing_ok=True)
            raise

    @routes.get('/api/inbox/{identifier}/download')
    def download(identifier: str, user: dict = Depends(require_user)):
        with db() as connection:
            row = owned(connection,identifier,user['id'])
        target = upload_directory()/row['stored_name']
        if not target.is_file():
            raise HTTPException(404,'Stored file not found')
        return FileResponse(target,filename=row['original_name'],media_type='application/octet-stream',headers={'X-Content-Type-Options':'nosniff'})

    @routes.put('/api/inbox/{identifier}')
    def update_metadata(identifier: str, payload: MetadataUpdate, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = owned(connection,identifier,user['id'])
            if row['case_id'] or row['version'] != payload.expected_version:
                raise HTTPException(409,'Entry already assigned or changed')
            connection.execute('UPDATE inbox_documents SET subject=?,sender=?,received_on=?,note=?,version=version+1 WHERE id=?',(payload.subject,payload.sender,payload.received_on.isoformat(),payload.note,identifier))
            return public(connection,owned(connection,identifier,user['id']))

    @routes.post('/api/inbox/{identifier}/assign')
    def assign(identifier: str, payload: Assignment, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = owned(connection,identifier,user['id'])
            case_id = str(payload.case_id)
            if not connection.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?',(case_id,user['id'])).fetchone():
                raise HTTPException(404,'Case not found')
            if row['case_id'] or row['version'] != payload.expected_version:
                raise HTTPException(409,'Entry already assigned or changed')
            target = upload_directory()/row['stored_name']
            if not target.is_file():
                raise HTTPException(404,'Stored file not found')
            connection.execute('''INSERT INTO documents(id,case_id,original_name,stored_name,content_type,size_bytes,created_at)
                VALUES(?,?,?,?,?,?,?)''',(identifier,case_id,row['original_name'],row['stored_name'],row['content_type'],row['size_bytes'],row['created_at']))
            connection.execute('UPDATE inbox_documents SET case_id=?,document_id=?,assigned_at=?,version=version+1 WHERE id=?',(case_id,identifier,now(),identifier))
            record_activity(connection,case_id,'inbox_assigned',row['original_name'])
            return public(connection,owned(connection,identifier,user['id']))

    @routes.post('/api/inbox/{identifier}/correct')
    def correct(identifier: str, payload: Correction, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = owned(connection,identifier,user['id'])
            case_id = str(payload.case_id)
            if not connection.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?',(case_id,user['id'])).fetchone():
                raise HTTPException(404,'Case not found')
            if not row['case_id'] or row['version'] != payload.expected_version or row['case_id'] == case_id:
                raise HTTPException(409,'Assignment changed, unassigned, or same target')
            root=upload_directory().resolve();target=root/row['stored_name']
            if not target.resolve().is_relative_to(root) or target.is_symlink() or not target.is_file():
                raise HTTPException(404,'Stored original unavailable')
            if target.stat().st_size != row['size_bytes'] or hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
                raise HTTPException(409,'Stored original changed')
            old=connection.execute('SELECT id FROM documents WHERE id=? AND case_id=?',(row['document_id'],row['case_id'])).fetchone()
            if not old:
                raise HTTPException(409,'Previous case document unavailable')
            # Retain immutable references to old originals/text/research; create a fresh unreviewed association.
            document_id=str(uuid.uuid4());timestamp=now()
            connection.execute('''INSERT INTO documents(id,case_id,original_name,stored_name,content_type,size_bytes,created_at)
                VALUES(?,?,?,?,?,?,?)''',(document_id,case_id,row['original_name'],row['stored_name'],row['content_type'],row['size_bytes'],timestamp))
            connection.execute('UPDATE documents SET inbox_reassigned_at=?,inbox_correction_note=? WHERE id=?',(timestamp,payload.reason,row['document_id']))
            connection.execute('INSERT INTO inbox_corrections VALUES(?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),identifier,row['case_id'],case_id,row['document_id'],document_id,payload.reason,row['version']+1,timestamp))
            connection.execute('UPDATE inbox_documents SET case_id=?,document_id=?,assigned_at=?,version=version+1 WHERE id=?',(case_id,document_id,timestamp,identifier))
            for affected in [row['case_id'],case_id]:
                record_activity(connection,affected,'inbox_corrected',row['original_name']+' · '+payload.reason)
            return public(connection,owned(connection,identifier,user['id']))

    return routes
