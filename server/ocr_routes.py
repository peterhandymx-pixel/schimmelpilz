"""Explicit account-owned OCR without overwriting reviewed or entered text."""
import json
import subprocess
import sys
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from . import document_ocr


class OcrInput(BaseModel):
    model_config={'extra':'forbid'}
    start_page:int=Field(default=1,ge=1,le=80)
    count:int=Field(default=1,ge=1,le=12)
    language:Literal['deu','eng','deu+eng']='deu+eng'

    @model_validator(mode='after')
    def bounds(self):
        if self.start_page+self.count-1>80:raise ValueError('Range exceeds supported pages')
        return self


def migrate(connection):
    columns={row['name'] for row in connection.execute('PRAGMA table_info(document_pages)')}
    for name,definition in [('origin',"TEXT NOT NULL DEFAULT 'text'"),('ocr_confidence','REAL'),('ocr_run_id','TEXT')]:
        if name not in columns:connection.execute(f'ALTER TABLE document_pages ADD COLUMN {name} {definition}')
    connection.execute('''CREATE TABLE IF NOT EXISTS document_ocr_runs(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),user_id TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,parameters TEXT NOT NULL,metadata TEXT NOT NULL)''')


def perform(db,now,record_activity,upload_dir,root,case_id,document,user_id,payload,replace_below=0):
    """Runs OCR for the requested pages (caller holds the extraction lock) and stores unreviewed machine text.

    Reviewed or manually entered text is never replaced; existing machine text only when it is shorter than
    replace_below characters (a scanned PDF's empty or near-empty text layer). Returns the run metadata."""
    document_id=document['id']
    path=upload_dir()/document['stored_name']
    if not path.resolve().is_relative_to(upload_dir().resolve()) or path.is_symlink() or not path.is_file():raise HTTPException(404,'Stored file unavailable')
    if path.suffix.lower() not in {'.pdf','.png','.jpg','.jpeg'}:raise HTTPException(415,'OCR supports PDF, PNG and JPG')
    if path.suffix.lower()!='.pdf' and (payload.start_page!=1 or payload.count!=1):raise HTTPException(422,'Images contain one location')
    if not document_ocr.available():raise HTTPException(503,'ocr_unavailable')
    try:
        worker=subprocess.run([sys.executable,'-m','server.document_ocr',str(path.resolve()),payload.model_dump_json()],cwd=root,capture_output=True,timeout=115,check=True,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        result=json.loads(worker.stdout)
    except (subprocess.SubprocessError,ValueError,OSError):raise HTTPException(503,'ocr_failed') from None
    if result.get('error_code'):
        code=result['error_code'];raise HTTPException(503 if code in {'ocr_unavailable','ocr_model_mismatch','ocr_failed'} else 422,code)
    run_id=str(uuid.uuid4());written=0;skipped=[]
    with db() as connection:
        connection.execute('BEGIN IMMEDIATE')
        if not connection.execute('SELECT 1 FROM documents WHERE id=? AND case_id=?',(document_id,case_id)).fetchone():raise HTTPException(404,'Document not found')
        for unit in result['units']:
            old=connection.execute('SELECT * FROM document_pages WHERE document_id=? AND unit_no=?',(document_id,unit['unit_no'])).fetchone()
            # Existing reviewed/manual/nonempty original text is never replaced.
            if old and (old['reviewed_text'] is not None or old['reviewed_at'] or len(old['original_text'].strip())>=max(1,replace_below)):
                skipped.append(unit['unit_no']);continue
            if old:
                connection.execute('UPDATE document_pages SET original_text=?,origin=?,ocr_confidence=?,ocr_run_id=? WHERE document_id=? AND unit_no=?',(unit['text'],'ocr',unit['confidence'],run_id,document_id,unit['unit_no']))
            else:
                connection.execute('INSERT INTO document_pages(document_id,unit_no,original_text,origin,ocr_confidence,ocr_run_id) VALUES(?,?,?,?,?,?)',(document_id,unit['unit_no'],unit['text'],'ocr',unit['confidence'],run_id))
            written+=1
        any_text=connection.execute("SELECT 1 FROM document_pages WHERE document_id=? AND trim(original_text)!=''",(document_id,)).fetchone()
        state='ready' if any_text else 'no_text'
        previous=connection.execute('SELECT * FROM document_extractions WHERE document_id=?',(document_id,)).fetchone()
        limited=bool(result['truncated'] or (previous and previous['truncated']))
        if previous:
            connection.execute('UPDATE document_extractions SET status=?,error_code=NULL,unit_kind=?,truncated=? WHERE document_id=?',(state,result['unit_kind'],limited,document_id))
        else:
            connection.execute('INSERT INTO document_extractions VALUES(?,?,?,?,?,?)',(document_id,state,None,result['unit_kind'],limited,now()))
        metadata={key:value for key,value in result.items() if key!='units'}|{'written_units':written,'skipped_units':skipped}
        connection.execute('INSERT INTO document_ocr_runs VALUES(?,?,?,?,?,?)',(run_id,document_id,user_id,now(),payload.model_dump_json(),json.dumps(metadata)))
        record_activity(connection,case_id,'document_ocr',document['original_name'])
    return metadata


def router(db,require_user,now,record_activity,get_case,get_document,document_text,upload_dir,lock,root):
    routes=APIRouter()
    @routes.get('/api/cases/{case_id}/documents/{document_id}/ocr/status')
    def status(case_id:str,document_id:str,user:dict=Depends(require_user)):
        get_case(case_id,user['id'])
        with db() as connection:get_document(connection,case_id,document_id)
        return {'available':document_ocr.available(),'engine':'tesseract.js-7.0.0','languages':['deu','eng','deu+eng'],'max_pages_per_run':12,'max_page':80,'max_pixels':document_ocr.MAX_PIXELS}
    @routes.post('/api/cases/{case_id}/documents/{document_id}/ocr')
    def recognize(case_id:str,document_id:str,payload:OcrInput,user:dict=Depends(require_user)):
        get_case(case_id,user['id'])
        with db() as connection:document=get_document(connection,case_id,document_id)
        path=upload_dir()/document['stored_name']
        if not path.resolve().is_relative_to(upload_dir().resolve()) or path.is_symlink() or not path.is_file():raise HTTPException(404,'Stored file unavailable')
        if path.suffix.lower() not in {'.pdf','.png','.jpg','.jpeg'}:raise HTTPException(415,'OCR supports PDF, PNG and JPG')
        if path.suffix.lower()!='.pdf' and (payload.start_page!=1 or payload.count!=1):raise HTTPException(422,'Images contain one location')
        if not document_ocr.available():raise HTTPException(503,'ocr_unavailable')
        if not lock.acquire(blocking=False):raise HTTPException(429,'extraction_busy')
        try:
            metadata=perform(db,now,record_activity,upload_dir,root,case_id,document,user['id'],payload)
        finally:lock.release()
        with db() as connection:return document_text(connection,document_id)|{'ocr':metadata}
    return routes
