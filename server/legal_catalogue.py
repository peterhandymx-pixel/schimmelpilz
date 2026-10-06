"""Official public XML adapters and local search. No private query leaves this server."""
import hashlib
import io
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zipfile import ZipFile
from xml.etree import ElementTree as ET

LEGAL_DIR = Path(os.getenv('LEGAL_DATA_DIR', Path(__file__).resolve().parents[1] / 'data/legal-sources'))
GII = 'https://www.gesetze-im-internet.de'
RII = 'https://www.rechtsprechung-im-internet.de'
LAWS = {'bgb':'BGB','bgbeg':'EGBGB','zpo':'ZPO','gvg':'GVG','hgb':'HGB','gmbhg':'GmbHG','inso':'InsO','kschg':'KSchG','burlg':'BUrlG','arbgg':'ArbGG','famfg':'FamFG','vwgo':'VwGO','sgg':'SGG','stgb':'StGB','stpo':'StPO','vwvfg':'VwVfG','rvg':'RVG','gkg_2004':'GKG','famgkg':'FamGKG','gg':'GG','sgb_1':'SGB I','sgb_2':'SGB II','sgb_10':'SGB X'}
SYNC_LOCK = threading.Lock()
FETCH_LOCK = threading.Lock()
PROGRESS_LOCK = threading.Lock()
INIT_LOCK = threading.Lock()
INITIALIZED = set()
PROGRESS = {'running':False, 'completed':0, 'total':0, 'current':'', 'errors':[]}


def timestamp():
    return datetime.now(UTC).isoformat()


def safe_url(url):
    parts = urlsplit(url)
    if parts.scheme not in {'http','https'} or parts.username or parts.password or parts.port or parts.query or parts.fragment:
        raise ValueError('unsupported_source_url')
    if parts.hostname == 'www.gesetze-im-internet.de':
        allowed = parts.path == '/gii-toc.xml' or bool(re.fullmatch(r'/[a-z0-9_-]+/xml\.zip', parts.path))
    elif parts.hostname == 'www.rechtsprechung-im-internet.de':
        allowed = parts.path == '/rii-toc.xml' or bool(re.fullmatch(r'/jportal/docs/bsjrs/jb-[A-Z0-9]+\.zip', parts.path))
    else:
        allowed = False
    if not allowed:
        raise ValueError('unsupported_source_url')
    return urlunsplit(('https', parts.hostname, parts.path, '', ''))


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return super().redirect_request(request, fp, code, msg, headers, safe_url(newurl))


def fetch_public(url, limit=8 * 1024 * 1024):
    request = Request(safe_url(url), headers={'User-Agent':'Schimmelpilz/0.5 (official XML catalogue)', 'Accept':'application/xml, application/zip'})
    with build_opener(OfficialRedirect()).open(request, timeout=25) as response:
        safe_url(response.geturl())
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('source_too_large')
    return data


def xml_root(data):
    if len(data) > 40 * 1024 * 1024 or re.search(br'<!ENTITY', data, re.I):
        raise ValueError('unsafe_xml')
    # ElementTree does not load external DTDs. Never enable an external entity resolver.
    return ET.fromstring(data)


def unzip_xml(data):
    with ZipFile(io.BytesIO(data)) as archive:
        files = [item for item in archive.infolist() if item.filename.lower().endswith('.xml')]
        if len(files) != 1 or files[0].file_size > 12 * 1024 * 1024 or files[0].flag_bits & 1:
            raise ValueError('unsupported_archive')
        return archive.read(files[0])


def words(element):
    return re.sub(r'\s+', ' ', ' '.join(element.itertext())).strip() if element is not None else ''


def field(root, name):
    return words(root.find(name))


def date_value(value):
    if re.fullmatch(r'\d{8}', value):
        return f'{value[:4]}-{value[4:6]}-{value[6:]}'
    return value


def parse_law(data, path):
    root = xml_root(data)
    if root.tag != 'dokumente' or path not in LAWS:
        raise ValueError('unsupported_statute')
    first = root.find('norm/metadaten')
    if first is None:
        raise ValueError('missing_metadata')
    abbreviation = field(first, 'jurabk') or LAWS[path]
    version = '; '.join(words(item) for item in first.findall('standangabe/standkommentar'))
    full_title = field(first, 'langue')
    rows = []
    for norm in root.findall('norm'):
        meta = norm.find('metadaten')
        if meta is None:
            continue
        label = field(meta, 'enbez')
        content = norm.find('textdaten/text/Content')
        text = words(content)
        if not label or not text or len(text) > 150000:
            continue
        paragraphs = [{'pinpoint':label + (f' · Absatzblock {i+1}' if len(list(content)) > 1 else ''), 'text':words(item)} for i,item in enumerate(list(content)) if words(item)]
        if not paragraphs:
            paragraphs = [{'pinpoint':label, 'text':text}]
        match = re.fullmatch(r'§\s*(\d+[a-z]*)', label)
        article = re.fullmatch(r'Art\s+(\d+[a-z]*)', label)
        page = '__' + match[1] + '.html' if match else 'art_' + article[1] + '.html' if article else 'index.html'
        rows.append({'key':'law:' + path + ':' + norm.get('doknr',''), 'kind':'law', 'title':f'{label} {abbreviation} · {field(meta,"titel")}', 'url':f'{GII}/{path}/{page}', 'download_url':f'{GII}/{path}/xml.zip', 'metadata':{'law':abbreviation,'law_path':path,'full_title':full_title,'version_note':version,'build_date':root.get('builddate',''),'publication_date':field(first,'ausfertigung-datum'),'jurisdiction':'DE','version_scope':'current_consolidated_not_historical'}, 'text':text, 'units':paragraphs})
    if not rows:
        raise ValueError('empty_statute')
    return rows


def parse_decision_index(data):
    root = xml_root(data)
    if root.tag != 'items':
        raise ValueError('invalid_index')
    rows = []
    for item in root.findall('item'):
        link = safe_url(field(item,'link'))
        match = re.fullmatch(r'/jportal/docs/bsjrs/jb-([A-Z0-9]+)\.zip', urlsplit(link).path)
        if not match:
            raise ValueError('invalid_decision_link')
        identifier = match[1]
        court, date, reference = field(item,'gericht'), date_value(field(item,'entsch-datum')), field(item,'aktenzeichen')
        rows.append({'key':'decision:' + identifier, 'kind':'decision','title':f'{court} · {date} · {reference}', 'url':f'{RII}/jportal/?quelle=jlink&docid={identifier}&psml=bsjrsprod.psml&max=true','download_url':link, 'metadata':{'court':court,'decision_date':date,'reference':reference,'identifier':identifier,'provider_modified':field(item,'modified'),'jurisdiction':'DE'}})
    if not rows:
        raise ValueError('empty_index')
    return rows


def parse_decision(data, expected):
    root = xml_root(data)
    identifier = field(root,'doknr')
    if root.tag != 'dokument' or identifier != expected['metadata']['identifier']:
        raise ValueError('decision_identity_mismatch')
    if field(root,'aktenzeichen') != expected['metadata']['reference'] or date_value(field(root,'entsch-datum')) != expected['metadata']['decision_date']:
        raise ValueError('decision_metadata_mismatch')
    court = field(root,'gertyp')
    if not expected['metadata']['court'].startswith(court) or not court:
        raise ValueError('decision_court_mismatch')
    units = []
    for section in ['titelzeile','leitsatz','tenor','tatbestand','entscheidungsgruende','gruende','abweichende_meinung','sonstiger_titel']:
        node = root.find(section)
        if node is None:
            continue
        for item in node.findall('.//dl'):
            text = words(item.find('dd'))
            if text:
                number = words(item.find('dt'))
                units.append({'pinpoint':f'Rn. {number}' if number else section, 'text':text})
        if not node.findall('.//dl') and words(node):
            units.append({'pinpoint':section, 'text':words(node)})
    text = '\n'.join(item['text'] for item in units)
    if not units or len(text) > 400000:
        raise ValueError('unsupported_decision_content')
    return {**expected,'metadata':{**expected['metadata'],'decision_type':field(root,'doktyp'),'ecli':field(root,'ecli'),'title_line':field(root,'titelzeile')},'text':text,'units':units}


@contextmanager
def database():
    LEGAL_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(LEGAL_DIR / 'catalogue.db', timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA journal_mode=WAL')
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_catalogue():
    path = (LEGAL_DIR / 'catalogue.db').resolve()
    with INIT_LOCK:
        if path in INITIALIZED and path.exists():
            return
        with database() as db:
            db.executescript('''
        CREATE TABLE IF NOT EXISTS entries(key TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,download_url TEXT NOT NULL,metadata TEXT NOT NULL,text TEXT NOT NULL DEFAULT '',units TEXT NOT NULL DEFAULT '[]',fetched_at TEXT,sha256 TEXT,listed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS collections(key TEXT PRIMARY KEY,updated_at TEXT NOT NULL,error TEXT);
        CREATE TABLE IF NOT EXISTS catalogue_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE VIRTUAL TABLE IF NOT EXISTS entry_search USING fts5(key UNINDEXED,title,text,tokenize='unicode61 remove_diacritics 2');
        ''')
            version = db.execute("SELECT value FROM catalogue_state WHERE key='fts_rowid_version'").fetchone()
            if not version or version['value'] != '1':
                # Direct rowid deletes avoid scanning the entire index for every update.
                db.executescript('''
                BEGIN IMMEDIATE;
                DROP TRIGGER IF EXISTS entry_insert;
                DROP TRIGGER IF EXISTS entry_update;
                DROP TRIGGER IF EXISTS entry_delete;
                DELETE FROM entry_search;
                INSERT INTO entry_search(rowid,key,title,text) SELECT rowid,key,title,text FROM entries;
                CREATE TRIGGER entry_insert AFTER INSERT ON entries BEGIN INSERT INTO entry_search(rowid,key,title,text) VALUES(new.rowid,new.key,new.title,new.text); END;
                CREATE TRIGGER entry_update AFTER UPDATE ON entries BEGIN DELETE FROM entry_search WHERE rowid=old.rowid; INSERT INTO entry_search(rowid,key,title,text) VALUES(new.rowid,new.key,new.title,new.text); END;
                CREATE TRIGGER entry_delete AFTER DELETE ON entries BEGIN DELETE FROM entry_search WHERE rowid=old.rowid; END;
                INSERT OR REPLACE INTO catalogue_state(key,value) VALUES('fts_rowid_version','1');
                COMMIT;
                ''')
        INITIALIZED.add(path)


def store_rows(rows, collection=None):
    fetched = timestamp()
    with database() as db:
        # Acquire the write reservation before SELECT, avoiding a failed WAL read-to-write upgrade.
        db.execute('BEGIN IMMEDIATE')
        if collection:
            db.execute('CREATE TEMP TABLE incoming_keys(key TEXT PRIMARY KEY)')
            db.executemany('INSERT INTO incoming_keys(key) VALUES(?)',[(row['key'],) for row in rows])
            if collection.startswith('law:'):
                db.execute('DELETE FROM entries WHERE key LIKE ? AND key NOT IN (SELECT key FROM incoming_keys)',(collection+':%',))
            elif collection == 'decision-index':
                db.execute("DELETE FROM entries WHERE kind='decision' AND key NOT IN (SELECT key FROM incoming_keys)")
        for row in rows:
            ready = 'text' in row
            text = row.get('text','')
            snapshot_hash = hashlib.sha256(json.dumps({key:row.get(key) for key in ('title','url','metadata','text','units')}, ensure_ascii=False,sort_keys=True).encode()).hexdigest() if ready else None
            old = db.execute('SELECT * FROM entries WHERE key=?',(row['key'],)).fetchone()
            if old and not ready:
                # A changed index record invalidates an old full text; do not mislabel it as refreshed.
                previous = json.loads(old['metadata'])
                if previous.get('provider_modified') == row['metadata'].get('provider_modified'):
                    continue
            db.execute('INSERT INTO entries(key,kind,title,url,download_url,metadata,text,units,fetched_at,sha256,listed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET kind=excluded.kind,title=excluded.title,url=excluded.url,download_url=excluded.download_url,metadata=excluded.metadata,text=excluded.text,units=excluded.units,fetched_at=excluded.fetched_at,sha256=excluded.sha256,listed_at=excluded.listed_at',(row['key'],row['kind'],row['title'],row['url'],row['download_url'],json.dumps(row['metadata'],ensure_ascii=False),text,json.dumps(row.get('units',[]),ensure_ascii=False),fetched if ready else None,snapshot_hash,fetched))
        if collection:
            db.execute('INSERT OR REPLACE INTO collections(key,updated_at,error) VALUES(?,?,NULL)',(collection,fetched))


def entry(row):
    result = dict(row)
    result['metadata'], result['units'] = json.loads(result['metadata']), json.loads(result['units'])
    result['provider'] = 'Gesetze im Internet' if result['kind'] == 'law' else 'Rechtsprechung im Internet'
    result['origin_status'] = 'official_xml_retrieved' if result['fetched_at'] else 'index_only'
    result['snapshot_id'] = str(uuid.uuid5(uuid.NAMESPACE_URL,result['key'] + ':' + (result['sha256'] or 'index')))
    return result


def source(key, refresh=False):
    init_catalogue()
    with database() as db:
        row = db.execute('SELECT * FROM entries WHERE key=?',(key,)).fetchone()
    if not row:
        raise LookupError('source_not_in_catalogue')
    result = entry(row)
    if result['kind'] == 'decision' and (refresh or not result['fetched_at']):
        with FETCH_LOCK:
            data = unzip_xml(fetch_public(result['download_url']))
            parsed = parse_decision(data,result)
            store_rows([parsed])
        with database() as db:
            result = entry(db.execute('SELECT * FROM entries WHERE key=?',(key,)).fetchone())
    return result


def search(query, kind='all', limit=15):
    init_catalogue()
    tokens = re.findall(r'[^\W_]+',query.lower(),re.UNICODE)[:20]
    if not tokens:
        return []
    quoted = ['"' + word + '"' for word in tokens]
    results = []
    with database() as db:
        for operation in [' AND ',' OR ']:
            rows = db.execute('SELECT e.* FROM entry_search s JOIN entries e ON e.key=s.key WHERE entry_search MATCH ? AND (?="all" OR e.kind=?) ORDER BY bm25(entry_search,0,4,1) LIMIT ?', (operation.join(quoted),kind,kind,limit)).fetchall()
            results = [entry(row) for row in rows]
            if results:
                break
    # Prefer an exact provision/reference when numeric legal identifiers occur in the query.
    normalized = re.sub(r'\W+','',query.lower())
    results.sort(key=lambda item: 0 if re.sub(r'\W+','',item['title'].split(' · ')[0].lower()) in normalized else 1)
    return results


def catalogue_status():
    init_catalogue()
    with database() as db:
        counts = {row['kind']:row['count'] for row in db.execute('SELECT kind,COUNT(*) count FROM entries GROUP BY kind')}
        downloaded = db.execute("SELECT COUNT(*) FROM entries WHERE kind='decision' AND fetched_at IS NOT NULL").fetchone()[0]
        updates = [dict(row) for row in db.execute('SELECT * FROM collections ORDER BY key')]
        saved_progress = db.execute("SELECT value FROM catalogue_state WHERE key='last_refresh'").fetchone()
    with PROGRESS_LOCK:
        progress = {**PROGRESS,'errors':list(PROGRESS['errors'])}
        if not progress['running'] and saved_progress:
            progress = json.loads(saved_progress['value'])
    return {'counts':counts,'downloaded_decisions':downloaded,'collections':updates,'progress':progress,'laws':list(LAWS.values()),'jurisdictions':['DE'],'privacy':'local_search_public_downloads_only'}


def sync_catalogue(decisions_per_court=8):
    if not SYNC_LOCK.acquire(blocking=False):
        return False
    init_catalogue()
    with PROGRESS_LOCK:
        PROGRESS.update(running=True,completed=0,total=len(LAWS)+1,current='',errors=[])
    def task(name, work):
        with PROGRESS_LOCK:
            PROGRESS['current'] = name
        try:
            work()
        except Exception:
            with PROGRESS_LOCK:
                PROGRESS['errors'].append(name)
        finally:
            with PROGRESS_LOCK:
                PROGRESS['completed'] += 1
    try:
        for path in LAWS:
            task(LAWS[path],lambda path=path: store_rows(parse_law(unzip_xml(fetch_public(f'{GII}/{path}/xml.zip')),path),'law:'+path))
        task('RII decision index',lambda: store_rows(parse_decision_index(fetch_public(RII + '/rii-toc.xml',40*1024*1024)),'decision-index'))
        with database() as db:
            candidates = [entry(row) for row in db.execute("SELECT * FROM entries WHERE kind='decision' ORDER BY json_extract(metadata,'$.decision_date') DESC")]
        picked, courts = [], {}
        for item in candidates:
            court = item['metadata']['court'].split(' ')[0]
            if court not in {'BGH','BAG','BFH','BVerwG','BSG','BVerfG','BPatG'}:
                continue
            if courts.get(court,0) < decisions_per_court:
                picked.append(item); courts[court] = courts.get(court,0)+1
        with PROGRESS_LOCK:
            PROGRESS['total'] += len(picked)
        for item in picked:
            task(item['title'],lambda key=item['key']: source(key))
    finally:
        with PROGRESS_LOCK:
            PROGRESS['running'] = False
            PROGRESS['current'] = ''
            report = {**PROGRESS,'finished_at':timestamp()}
        try:
            with database() as db:
                db.execute("INSERT OR REPLACE INTO catalogue_state(key,value) VALUES('last_refresh',?)",(json.dumps(report,ensure_ascii=False),))
        finally:
            SYNC_LOCK.release()
    return True


def start_sync():
    if SYNC_LOCK.locked():
        return False
    threading.Thread(target=sync_catalogue, daemon=True, name='official-catalogue-refresh').start()
    return True


if __name__ == '__main__':
    sync_catalogue()
    print(json.dumps(catalogue_status(),ensure_ascii=False))
