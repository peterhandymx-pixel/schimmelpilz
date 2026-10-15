"""Reversible archive state and private portable case packages."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask


class ArchiveInput(BaseModel):
    model_config={'extra':'forbid'}
    archived: bool
    expected_version: int = Field(ge=0)


def migrate(connection):
    columns={row['name'] for row in connection.execute('PRAGMA table_info(cases)')}
    if 'archived_at' not in columns:
        connection.execute('ALTER TABLE cases ADD COLUMN archived_at TEXT')
    if 'archive_version' not in columns:
        connection.execute('ALTER TABLE cases ADD COLUMN archive_version INTEGER NOT NULL DEFAULT 0')


def router(db,require_user,now,record_activity,row_case,data_dir,upload_dir):
    routes=APIRouter()

    def owned(connection,case_id,user_id):
        row=connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?',(case_id,user_id)).fetchone()
        if not row:
            raise HTTPException(404,'Case not found')
        return row

    @routes.put('/api/cases/{case_id}/archive')
    def archive(case_id:str,payload:ArchiveInput,user:dict=Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            old=owned(connection,case_id,user['id'])
            if old['archive_version'] != payload.expected_version:
                raise HTTPException(409,'Archive state changed')
            if bool(old['archived_at']) != payload.archived:
                connection.execute('UPDATE cases SET archived_at=?,archive_version=archive_version+1 WHERE id=?',(now() if payload.archived else None,case_id))
                record_activity(connection,case_id,'case_archived' if payload.archived else 'case_restored')
            return row_case(owned(connection,case_id,user['id']),connection)

    @routes.get('/api/cases/{case_id}/export.zip')
    def export(case_id:str,user:dict=Depends(require_user)):
        files=[]
        with db() as connection:
            # One SQLite read snapshot captures all structured records consistently.
            connection.execute('BEGIN')
            case=owned(connection,case_id,user['id'])
            records={'format':'schimmelpilz-case-v1','exported_at':now(),'case':row_case(case,connection)}
            def selected(table,column='case_id',values=None):
                ids=values if values is not None else [case_id]
                if not ids:
                    return []
                return [dict(row) for row in connection.execute(f'SELECT * FROM {table} WHERE {column} IN ({",".join("?" for _ in ids)})',ids)]
            for table in ['research_runs','case_legal_sources','cost_reviews','tasks','activities','route_plans','route_plan_versions']:
                records[table]=selected(table)
            documents=selected('documents');drafts=selected('drafts')
            records['documents']=documents;records['drafts']=drafts
            for table in ['document_pages','document_extractions','document_ocr_runs']:
                records[table]=selected(table,'document_id',[doc['id'] for doc in documents])
            for table in ['draft_versions','draft_review_checks','draft_review_events']:
                records[table]=selected(table,'draft_id',[draft['id'] for draft in drafts])
            records['cost_review_versions']=selected('cost_review_versions','review_id',[review['id'] for review in records['cost_reviews']])
            records['contacts']=[dict(row) for row in connection.execute('SELECT c.*,cc.role FROM contacts c JOIN contact_cases cc ON cc.contact_id=c.id WHERE cc.case_id=? AND c.user_id=?',(case_id,user['id']))]
            records['inbox_documents']=selected('inbox_documents')
            heads={draft['letterhead_id'] for draft in drafts if draft['letterhead_id']}
            for version in records['draft_versions']:
                head=json.loads(version['snapshot']).get('letterhead_id')
                if head:
                    heads.add(head)
            records['letterheads']=[row for row in selected('letterheads','id',sorted(heads)) if row['user_id']==user['id']]
            for doc in documents:
                files.append(('documents/'+doc['id']+Path(doc['stored_name']).suffix,upload_dir(),doc['stored_name'],doc['size_bytes']))
            for head in records['letterheads']:
                folder=data_dir()/'letterheads'
                files.extend([('letterheads/'+head['original_stored'],folder,head['original_stored'],None),('letterheads/'+head['pdf_stored'],folder,head['pdf_stored'],None)])
        metadata=json.dumps(records,ensure_ascii=False,indent=2).encode('utf-8')
        limit=200*1024*1024;total=len(metadata)
        if total>limit:
            raise HTTPException(413,'Case export exceeds 200 MB')
        checked=[]
        for name,root,stored,expected_size in files:
            root=Path(root).resolve()
            if not stored or Path(stored).name != stored or any(char in stored for char in '/\\:'):
                raise HTTPException(503,'Unsafe stored file')
            path=root/stored
            if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
                raise HTTPException(503,'Required original missing')
            size=path.stat().st_size
            if expected_size is not None and size!=expected_size:
                raise HTTPException(503,'Original size mismatch')
            total+=size
            if total>limit:
                raise HTTPException(413,'Case export exceeds 200 MB')
            checked.append((name,path,size))
        temporary=TemporaryDirectory(prefix='schimmelpilz-case-export-')
        try:
            output=Path(temporary.name)/'case.zip';manifest=[]
            with ZipFile(output,'w',compression=ZIP_DEFLATED,allowZip64=True) as archive:
                archive.writestr('case.json',metadata)
                manifest.append({'path':'case.json','bytes':len(metadata),'sha256':hashlib.sha256(metadata).hexdigest()})
                for name,path,size in checked:
                    digest=hashlib.sha256()
                    with path.open('rb') as source,archive.open(name,'w') as target:
                        written=0
                        while chunk:=source.read(65536):
                            written+=len(chunk)
                            if written>size:
                                raise HTTPException(503,'Original changed during export')
                            digest.update(chunk);target.write(chunk)
                    if written!=size:
                        raise HTTPException(503,'Original changed during export')
                    manifest.append({'path':name,'bytes':size,'sha256':digest.hexdigest()})
                archive.writestr('manifest.json',json.dumps(manifest,indent=2))
                archive.writestr('README.txt','Private case export. Keep this archive confidential. case.json contains records and historical versions; documents/ contains original files; letterheads/ contains saved template versions. manifest.json records SHA-256 hashes. This is a portable export, not an automatic import or legal approval. No account password or session is included.\n')
            return FileResponse(output,media_type='application/zip',filename='Schimmelpilz-Akte.zip',background=BackgroundTask(temporary.cleanup))
        except Exception:
            temporary.cleanup()
            raise

    return routes
