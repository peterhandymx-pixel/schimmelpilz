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
    ''')


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

    return routes
