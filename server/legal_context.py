"""Case-owned legal snapshots, bounded passages and deterministic citation-ID checks."""
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime


def attach_snapshot(connection, case_id, snapshot):
    existing = connection.execute('SELECT id FROM case_legal_sources WHERE case_id=? AND snapshot_id=?',(case_id,snapshot['snapshot_id'])).fetchone()
    if existing:
        return existing['id']
    count = connection.execute('SELECT COUNT(*) FROM case_legal_sources WHERE case_id=?',(case_id,)).fetchone()[0]
    if count >= 250:
        raise ValueError('source_limit')
    identifier = str(uuid.uuid4())
    connection.execute('INSERT INTO case_legal_sources(id,case_id,snapshot_id,snapshot,review_status,review_note,created_at) VALUES(?,?,?,?,?,?,?)',(identifier,case_id,snapshot['snapshot_id'],json.dumps(snapshot,ensure_ascii=False),'pending','',datetime.now(UTC).isoformat()))
    return identifier


def legal_row(row):
    return {**dict(row),'snapshot':json.loads(row['snapshot'])}


def supplied_legal_passages(rows, question):
    terms = set(re.findall(r'[^\W_]{3,}',question.lower()))
    result, remaining = [], 9000
    for row in rows:
        if row['review_status'] == 'excluded':
            raise ValueError('source_excluded')
        snapshot = json.loads(row['snapshot'])
        ranked = sorted(enumerate(snapshot['units']),key=lambda item:(-sum(term in item[1]['text'].lower() for term in terms),item[0]))
        # At most two locations per source, eight locations and 9,000 characters total.
        for index, unit in sorted(ranked[:2]):
            if len(result) >= 8 or remaining < 200:
                break
            length = min(1800,remaining)
            excerpt = unit['text'][:length]
            result.append({'citation_id':f'L{len(result)+1}','case_source_id':row['id'],'snapshot_id':snapshot['snapshot_id'],'kind':snapshot['kind'],'title':snapshot['title'],'url':snapshot['url'],'provider':snapshot['provider'],'metadata':snapshot['metadata'],'pinpoint':unit['pinpoint'],'text':excerpt,'excerpt_truncated':len(unit['text'])>len(excerpt),'fetched_at':snapshot['fetched_at'],'source_sha256':snapshot['sha256'],'excerpt_sha256':hashlib.sha256(excerpt.encode()).hexdigest(),'origin_status':snapshot['origin_status'],'review_status':row['review_status'],'review_note':row['review_note'],'reviewed_at':row['reviewed_at']})
            remaining -= len(excerpt)
    return result


def citation_audit(answer, sources):
    available = {item['citation_id'] for item in sources}
    mentioned = set(re.findall(r'\[(L\d+)\]',answer))
    return {'matched':sorted(mentioned & available),'unknown':sorted(mentioned-available),'missing_citations':bool(sources) and not bool(mentioned & available),'legal_review_required':True,'scope':'identifier_check_only'}
