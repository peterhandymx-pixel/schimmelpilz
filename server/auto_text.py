"""Automatic text reading for every new case document: text layer first, then OCR for photos and scanned PDF pages.

Runs right after the upload or inbox assignment has been answered (a FastAPI background task), one step at a time under
the shared extraction lock. The result is unreviewed machine text, exactly what the manual "read text" and OCR buttons
produce: research still uses only text a person has checked against the original.
"""
from fastapi import HTTPException

from . import document_ocr
from .ocr_routes import OcrInput, perform

# A PDF page with less text than this has no usable text layer (scan, photo, only a page number).
SCANNED_BELOW = 25
# Bounds the CPU time one upload can take; longer scans keep the manual OCR button for the remaining pages.
MAX_OCR_PAGES = 24
PAGES_PER_RUN = 4
OCR_SUFFIXES = {'.pdf', '.png', '.jpg', '.jpeg'}


def migrate(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS document_auto_text(
        document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
        status TEXT NOT NULL, error_code TEXT, ocr_pages INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)''')
    # Work cut off by a restart is not resumed silently; the manual buttons stay available for it.
    connection.execute("UPDATE document_auto_text SET status='interrupted' WHERE status IN ('queued','running')")


def mark(db, now, document_id, status, error_code=None, ocr_pages=0):
    with db() as connection:
        if connection.execute('SELECT 1 FROM documents WHERE id=?', (document_id,)).fetchone():
            connection.execute('''INSERT INTO document_auto_text(document_id,status,error_code,ocr_pages,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(document_id) DO UPDATE SET status=excluded.status,error_code=excluded.error_code,ocr_pages=excluded.ocr_pages,updated_at=excluded.updated_at''',
                (document_id, status, error_code, ocr_pages, now()))


def ocr_targets(suffix, pages, total):
    """Pages that need OCR: the single image, or PDF pages whose text layer is (almost) empty and unreviewed."""
    if suffix in {'.png', '.jpg', '.jpeg'}:
        return [1]
    if suffix != '.pdf':
        return []
    known = {row['unit_no']: row for row in pages}
    targets = []
    for unit_no in range(1, total + 1):
        row = known.get(unit_no)
        if row is None or (row['reviewed_at'] is None and row['reviewed_text'] is None and len((row['original_text'] or '').strip()) < SCANNED_BELOW):
            targets.append(unit_no)
    return targets[:MAX_OCR_PAGES]


def runs(targets):
    """Consecutive page ranges of at most PAGES_PER_RUN pages: [1,2,3,7] -> [(1,3),(7,1)]."""
    result = []
    for page in targets:
        if result and result[-1][0] + result[-1][1] == page and result[-1][1] < PAGES_PER_RUN:
            result[-1] = (result[-1][0], result[-1][1] + 1)
        else:
            result.append((page, 1))
    return result


def pdf_pages(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    return 0 if reader.is_encrypted else min(len(reader.pages), 80)


class AutoText:
    def __init__(self, db, now, record_activity, upload_dir, root, lock, extract_stored):
        self.db, self.now, self.record_activity, self.upload_dir, self.root = db, now, record_activity, upload_dir, root
        self.lock, self.extract_stored = lock, extract_stored

    def queue(self, background_tasks, case_id, document_id, user_id):
        mark(self.db, self.now, document_id, 'queued')
        background_tasks.add_task(self.process, case_id, document_id, user_id)

    def process(self, case_id, document_id, user_id):
        try:
            with self.db() as connection:
                document = connection.execute('SELECT * FROM documents WHERE id=? AND case_id=?', (document_id, case_id)).fetchone()
            if not document:
                return
            mark(self.db, self.now, document_id, 'running')
            suffix = (self.upload_dir() / document['stored_name']).suffix.lower()
            if suffix in {'.pdf', '.docx'}:
                with self.lock:
                    self.extract_stored(case_id, document)
            if suffix not in OCR_SUFFIXES:
                return self.finish(document_id, 0)
            with self.db() as connection:
                pages = connection.execute('SELECT unit_no,original_text,reviewed_text,reviewed_at FROM document_pages WHERE document_id=?', (document_id,)).fetchall()
            total = pdf_pages(self.upload_dir() / document['stored_name']) if suffix == '.pdf' else 1
            targets = ocr_targets(suffix, pages, total)
            if not targets:
                return self.finish(document_id, 0)
            if not document_ocr.available():
                return mark(self.db, self.now, document_id, 'ocr_unavailable', 'ocr_unavailable')
            done = 0
            for start, count in runs(targets):
                with self.lock:
                    metadata = perform(self.db, self.now, self.record_activity, self.upload_dir, self.root, case_id, document, user_id,
                                       OcrInput(start_page=start, count=count, language='deu+eng'), replace_below=SCANNED_BELOW)
                done += metadata['written_units']
            self.finish(document_id, done)
        except HTTPException as error:
            mark(self.db, self.now, document_id, 'failed', str(error.detail))
        except Exception:
            mark(self.db, self.now, document_id, 'failed', 'auto_text_failed')

    def finish(self, document_id, ocr_pages):
        with self.db() as connection:
            has_text = connection.execute("SELECT 1 FROM document_pages WHERE document_id=? AND trim(original_text)!=''", (document_id,)).fetchone()
        mark(self.db, self.now, document_id, 'done' if has_text else 'no_text', None, ocr_pages)
