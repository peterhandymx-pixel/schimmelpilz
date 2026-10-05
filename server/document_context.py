"""Select explicit, reviewed document excerpts; persist their exact provenance."""
import hashlib
import re


def select_sources(connection, case_id, document_ids, question):
    if not document_ids:
        return []
    terms = set(re.findall(r"\w{4,}", question.lower()))
    candidates = []
    for document_id in document_ids:
        rows = connection.execute("""SELECT d.id, d.original_name, p.unit_no, p.reviewed_text, p.reviewed_at, e.unit_kind
            FROM documents d JOIN document_pages p ON p.document_id=d.id
            JOIN document_extractions e ON e.document_id=d.id
            WHERE d.case_id=? AND d.id=? AND p.reviewed_at IS NOT NULL
            ORDER BY p.unit_no""", (case_id, document_id)).fetchall()
        for row in rows:
            text = row["reviewed_text"] or ""
            if text.strip():
                score = sum(text.lower().count(term) for term in terms)
                candidates.append((score, dict(row)))
    candidates.sort(key=lambda pair: (-pair[0], document_ids.index(pair[1]["id"]), pair[1]["unit_no"]))
    remaining, sources = 8000, []
    for _, row in candidates[:12]:
        text = row["reviewed_text"][:min(2400, remaining)]
        if not text:
            break
        sources.append({"document_id": row["id"], "filename": row["original_name"], "unit_no": row["unit_no"], "unit_kind": row["unit_kind"], "text": text, "reviewed_at": row["reviewed_at"], "text_sha256": hashlib.sha256(row["reviewed_text"].encode("utf-8")).hexdigest(), "excerpt_truncated": len(text) < len(row["reviewed_text"])})
        remaining -= len(text)
    return sources
