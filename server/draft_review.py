"""Immutable draft versions and manual, version-bound review. No semantic legal approval."""
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime

CONTENT_FIELDS = ('body','recipient','language','kind','letterhead_id','letterhead_layout','research_run_id','source_context')
LEDGER_HEADINGS = ('RECHTSQUELLEN DIESER ANFRAGE','LEGAL SOURCES FOR THIS REQUEST','ÜBERGEBENE DOKUMENTSTELLEN','SUPPLIED DOCUMENT PASSAGES')
REQUIRED_CHECKS = ('facts','source_versions','adverse_authority','procedure_recipient_signature')


def timestamp():
    return datetime.now(UTC).isoformat()


def content(row):
    return {key:row[key] for key in CONTENT_FIELDS}


def snapshot_version(connection, row, actor=None):
    snapshot = content(row)
    encoded = json.dumps(snapshot,ensure_ascii=False,sort_keys=True)
    connection.execute('INSERT OR IGNORE INTO draft_versions(draft_id,version,snapshot,sha256,created_at,actor_id,actor_name) VALUES(?,?,?,?,?,?,?)',
        (row['id'],row['version'],encoded,hashlib.sha256(encoded.encode()).hexdigest(),row['updated_at'] or row['created_at'],actor['id'] if actor else None,actor['full_name'] if actor else ''))


def migrate(connection):
    columns = {row['name'] for row in connection.execute('PRAGMA table_info(drafts)')}
    for name,declaration in {'version':'INTEGER NOT NULL DEFAULT 1','updated_at':'TEXT','review_status':"TEXT NOT NULL DEFAULT 'draft'",'review_revision':'INTEGER NOT NULL DEFAULT 0','approved_by':'TEXT','approved_name':'TEXT','approved_at':'TEXT','research_run_id':'TEXT','source_context':"TEXT NOT NULL DEFAULT '{}'"}.items():
        if name not in columns:
            connection.execute(f'ALTER TABLE drafts ADD COLUMN {name} {declaration}')
    connection.executescript('''
    CREATE TABLE IF NOT EXISTS draft_versions(draft_id TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,version INTEGER NOT NULL,snapshot TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL,actor_id TEXT,actor_name TEXT NOT NULL,PRIMARY KEY(draft_id,version));
    CREATE TABLE IF NOT EXISTS draft_review_checks(draft_id TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,version INTEGER NOT NULL,check_id TEXT NOT NULL,checked INTEGER NOT NULL,note TEXT NOT NULL,actor_id TEXT NOT NULL,actor_name TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(draft_id,version,check_id));
    CREATE TABLE IF NOT EXISTS draft_review_events(id TEXT PRIMARY KEY,draft_id TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,version INTEGER NOT NULL,action TEXT NOT NULL,actor_id TEXT NOT NULL,actor_name TEXT NOT NULL,created_at TEXT NOT NULL,note TEXT NOT NULL,evidence TEXT NOT NULL);
    ''')
    for row in connection.execute('SELECT d.* FROM drafts d LEFT JOIN draft_versions v ON v.draft_id=d.id AND v.version=d.version WHERE v.draft_id IS NULL').fetchall():
        snapshot_version(connection,row)


def public_draft(row):
    return {**dict(row),'source_context':json.loads(row['source_context'])}


def working_text(body):
    # Editable appendices are not source authority; only saved server context supplies passages.
    offsets = [match.start() for heading in LEDGER_HEADINGS for match in re.finditer(r'^'+re.escape(heading),body,re.M)]
    return body[:min(offsets)] if offsets else body


def analysis(connection, row):
    context = json.loads(row['source_context'])
    sources = context.get('legal_sources',[])
    lookup = {item['citation_id']:item for item in sources}
    text = working_text(row['body'])
    checks = [{'id':key,'kind':'checklist','text':key,'sources':[],'flags':[]} for key in REQUIRED_CHECKS]
    hard = []
    if not row['recipient'].strip():
        hard.append({'kind':'missing_recipient','text':''})
    placeholders = sorted(set(re.findall(r'\[(?!L\d+\])[^\]\n]{1,180}\]',text)))
    hard.extend({'kind':'placeholder','text':value} for value in placeholders)
    unknown = sorted(set(re.findall(r'\[(L\d+)\]',text))-lookup.keys())
    hard.extend({'kind':'unknown_citation','text':value} for value in unknown)
    paragraphs = [part.strip() for part in re.split(r'\n\s*\n',text) if part.strip()]
    # Text blocks require human review; this deliberately does not classify legal truth.
    for index,part in enumerate(paragraphs):
        markers = list(dict.fromkeys(re.findall(r'\[(L\d+)\]',part)))
        mapped = [lookup[marker] for marker in markers if marker in lookup]
        flags = [] if mapped else ['no_linked_passage']
        if any(item['review_status'] != 'checked' for item in mapped):
            flags.append('source_review_open')
        if any(item.get('excerpt_truncated') for item in mapped):
            flags.append('limited_excerpt')
        identifier = f'block:{index}:' + hashlib.sha256(part.encode()).hexdigest()[:16]
        checks.append({'id':identifier,'kind':'block','text':part,'sources':mapped,'flags':flags})
    saved = {item['check_id']:dict(item) for item in connection.execute('SELECT * FROM draft_review_checks WHERE draft_id=? AND version=?',(row['id'],row['version']))}
    for item in checks:
        item['review'] = saved.get(item['id'])
    unresolved = sum(not item['review'] or not item['review']['checked'] for item in checks)
    return {'checks':checks,'hard_blocks':hard,'unresolved':unresolved,'can_approve':row['review_status']=='in_review' and not hard and unresolved==0,'source_context':context,'scope':'manual_review_not_semantic_verification'}


def response(connection, row):
    result = analysis(connection,row)
    result['draft'] = public_draft(row)
    result['versions'] = [dict(item) for item in connection.execute('SELECT version,sha256,created_at,actor_id,actor_name FROM draft_versions WHERE draft_id=? ORDER BY version DESC',(row['id'],))]
    result['events'] = [{**dict(item),'evidence':json.loads(item['evidence'])} for item in connection.execute('SELECT * FROM draft_review_events WHERE draft_id=? ORDER BY created_at DESC,id DESC',(row['id'],))]
    return result


def event(connection, row, actor, action, note='', evidence=None):
    connection.execute('INSERT INTO draft_review_events(id,draft_id,version,action,actor_id,actor_name,created_at,note,evidence) VALUES(?,?,?,?,?,?,?,?,?)',
        (str(uuid.uuid4()),row['id'],row['version'],action,actor['id'],actor['full_name'],timestamp(),note,json.dumps(evidence or {},ensure_ascii=False)))
