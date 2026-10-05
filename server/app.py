"""Small single-server API for the Schimmelpilz MVP.

Runtime data is written to DATA_DIR (outside the public landing-page build).
It uses local accounts and account-owned files; automatic legal workflows remain planned.
"""

from __future__ import annotations

import os
import json
import sqlite3
import uuid
import secrets
import threading
import subprocess
import sys
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response as BinaryResponse
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from .auth import COOKIE_NAME, RegisterInput, LoginInput, public_user, password_hash, verify_password, set_session, token_hash, check_login_limit, failed_logins
from .research import ollama_status, prepare_messages, generate_answer, OLLAMA_MODEL
from .document_context import select_sources
from .letterheads import normalize, compose_pdf, office_path
import hashlib
from tempfile import TemporaryDirectory
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".zip"}
RESEARCH_LOCK = threading.Lock()
EXTRACTION_LOCK = threading.Lock()
LETTERHEAD_LOCK = threading.Lock()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Virtuelle Rechtsassistenz Schimmelpilz", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-Schimmelpilz-Request"],
    allow_credentials=True,
)


@app.middleware("http")
async def guard_cookie_requests(request: Request, call_next):
    # Custom header plus JSON/multipart handling prevents cross-site form writes.
    if request.method in {"POST", "PUT", "DELETE"} and request.headers.get("x-schimmelpilz-request") != "1":
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Missing request header"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class CaseDetails(BaseModel):
    status: Literal["active", "waiting", "closed"] = "active"
    responsible: str = Field(default="", max_length=160)
    audience: Literal["consumer", "business", "law_firm"] = "consumer"
    client_name: str = Field(default="", max_length=160)
    client_role: Literal["claimant", "respondent", "applicant", "other"] = "other"
    client_email: str = Field(default="", max_length=254)
    client_address: str = Field(default="", max_length=500)
    opponent_name: str = Field(default="", max_length=160)
    opponent_address: str = Field(default="", max_length=500)
    opponent_reference: str = Field(default="", max_length=100)
    legal_area: Literal["general", "consumer", "tenancy", "contract", "commercial", "employment", "family", "social", "administrative", "criminal"] = "general"
    jurisdiction: Literal["DE", "EU", "MX", "other"] = "DE"
    stage: Literal["initial", "out_of_court", "court", "appeal", "enforcement"] = "initial"
    objective: str = Field(default="", max_length=2000)
    court: str = Field(default="", max_length=160)
    court_reference: str = Field(default="", max_length=100)
    received_on: date | None = None
    deadline: date | None = None
    deadline_note: str = Field(default="", max_length=300)
    dispute_value: float | None = Field(default=None, ge=0, le=1_000_000_000_000, allow_inf_nan=False)
    currency: Literal["EUR", "MXN", "USD"] = "EUR"
    fee_basis: Literal["unknown", "statutory", "hourly", "agreement"] = "unknown"
    conflict_check: Literal["pending", "checked", "conflict"] = "pending"

    @field_validator("responsible", "client_name", "client_email", "client_address", "opponent_name", "opponent_address", "opponent_reference", "objective", "court", "court_reference", "deadline_note", mode="before")
    @classmethod
    def strip_input(cls, value):
        return value.strip() if isinstance(value, str) else value


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    language: str = Field(default="de", pattern="^(de|en)$")
    reference_mode: Literal["generate", "existing"] = "generate"
    reference: str | None = Field(default=None, min_length=1, max_length=100)
    details: CaseDetails = Field(default_factory=CaseDetails)

    @field_validator("title", "description", "reference", mode="before")
    @classmethod
    def strip_input(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_reference(self):
        if self.reference_mode == "existing" and not self.reference:
            raise ValueError("An existing reference is required")
        if self.reference and any(ord(character) < 32 or ord(character) == 127 for character in self.reference):
            raise ValueError("Control characters are not allowed in references")
        return self


class DraftCreate(BaseModel):
    language: str = Field(default="de", pattern="^(de|en)$")
    recipient: str = Field(default="", max_length=500)
    kind: Literal["letter", "claim", "application", "objection", "response"] = "letter"
    body: str | None = Field(default=None, min_length=1, max_length=50000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_body(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_specialised_body(self):
        if self.kind != "letter" and self.body is None:
            raise ValueError("Specialised drafts require a completed body")
        return self


class CaseUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    language: Literal["de", "en"] = "de"
    details: CaseDetails = Field(default_factory=CaseDetails)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_input(cls, value):
        return value.strip() if isinstance(value, str) else value


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    note: str = Field(default="", max_length=2000)
    due_on: date | None = None
    priority: Literal["normal", "high"] = "normal"

    @field_validator("title", "note", mode="before")
    @classmethod
    def strip_input(cls, value):
        return value.strip() if isinstance(value, str) else value


class TaskUpdate(TaskCreate):
    completed: bool


class ResearchInput(BaseModel):
    request_id: uuid.UUID
    question: str = Field(min_length=3, max_length=4000)
    language: Literal["de", "en"] = "de"
    workflow: Literal["intake", "research", "jurisdiction", "costs", "drafting", "deadlines"] = "research"
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=8)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value):
        return value.strip() if isinstance(value, str) else value


class DocumentTextReview(BaseModel):
    text: str = Field(max_length=12000)
    reviewed: bool

    @model_validator(mode="after")
    def require_review_text(self):
        if self.reviewed and not self.text.strip():
            raise ValueError("Reviewed text must not be empty")
        return self


class LetterheadLayout(BaseModel):
    top_mm: float = Field(default=70, ge=5, le=160)
    bottom_mm: float = Field(default=30, ge=5, le=120)
    left_mm: float = Field(default=25, ge=5, le=100)
    right_mm: float = Field(default=25, ge=5, le=100)
    font_size: float = Field(default=11, ge=8, le=16)


class LetterheadActivation(LetterheadLayout):
    confirmed: bool


class DraftPdfInput(BaseModel):
    body: str = Field(min_length=1, max_length=50000)
    draft_id: uuid.UUID | None = None
    use_current_letterhead: bool = False


class DraftUpdate(BaseModel):
    use_current_letterhead: bool = False
    body: str = Field(min_length=1, max_length=50000)
    recipient: str | None = Field(default=None, max_length=500)
    kind: Literal["letter", "claim", "application", "objection", "response"] | None = None
    language: Literal["de", "en"] | None = None

    @field_validator("body", mode="before")
    @classmethod
    def strip_body(cls, value):
        return value.strip() if isinstance(value, str) else value


def now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                reference TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                recipient TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_extractions (
                document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                status TEXT NOT NULL, error_code TEXT, unit_kind TEXT NOT NULL,
                truncated INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_pages (
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                unit_no INTEGER NOT NULL, original_text TEXT NOT NULL,
                reviewed_text TEXT, reviewed_at TEXT,
                PRIMARY KEY(document_id, unit_no)
            );
            CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                title TEXT NOT NULL, note TEXT NOT NULL, due_on TEXT,
                priority TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS activities (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_runs (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                question TEXT NOT NULL, language TEXT NOT NULL, workflow TEXT NOT NULL,
                answer TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                model TEXT NOT NULL, error_code TEXT, input_tokens INTEGER, output_tokens INTEGER,
                truncated INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, salt TEXT NOT NULL,
                audience TEXT NOT NULL, full_name TEXT NOT NULL, organisation TEXT NOT NULL,
                street TEXT NOT NULL, postal_code TEXT NOT NULL, city TEXT NOT NULL,
                country TEXT NOT NULL, phone TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS letterheads (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                original_name TEXT NOT NULL, original_stored TEXT NOT NULL,
                pdf_stored TEXT NOT NULL, pdf_sha256 TEXT NOT NULL,
                geometry TEXT NOT NULL, layout TEXT NOT NULL DEFAULT '{}',
                confirmed_at TEXT, created_at TEXT NOT NULL
            );
            INSERT OR IGNORE INTO counters(name, value) VALUES ('case_reference', 0);
            """
        )
        # Add intake data to existing installations without changing their records.
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(cases)")}
        if "details" not in columns:
            connection.execute("ALTER TABLE cases ADD COLUMN details TEXT NOT NULL DEFAULT '{}'")
        if "user_id" not in columns:
            connection.execute("ALTER TABLE cases ADD COLUMN user_id TEXT REFERENCES users(id)")
        draft_columns = {row["name"] for row in connection.execute("PRAGMA table_info(drafts)")}
        if "kind" not in draft_columns:
            connection.execute("ALTER TABLE drafts ADD COLUMN kind TEXT NOT NULL DEFAULT 'letter'")
        for column, declaration in (("letterhead_id", "TEXT"), ("letterhead_layout", "TEXT")):
            if column not in draft_columns:
                connection.execute(f"ALTER TABLE drafts ADD COLUMN {column} {declaration}")
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "profile" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN profile TEXT NOT NULL DEFAULT '{}'")
        if "letterhead_id" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN letterhead_id TEXT")
        research_columns = {row["name"] for row in connection.execute("PRAGMA table_info(research_runs)")}
        for column in ("sources", "document_selection"):
            if column not in research_columns:
                connection.execute(f"ALTER TABLE research_runs ADD COLUMN {column} TEXT NOT NULL DEFAULT '[]'")
        connection.commit()
        # Legacy databases made references globally unique. They are now per account.
        if any(index["origin"] == "u" for index in connection.execute("PRAGMA index_list(cases)")):
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE cases_migrated (
                    id TEXT PRIMARY KEY, reference TEXT NOT NULL, title TEXT NOT NULL,
                    description TEXT NOT NULL, language TEXT NOT NULL, created_at TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}', user_id TEXT REFERENCES users(id)
                );
                INSERT INTO cases_migrated SELECT id, reference, title, description, language, created_at, details, user_id FROM cases;
                DROP TABLE cases;
                ALTER TABLE cases_migrated RENAME TO cases;
                COMMIT;
            """)
            connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS case_owner_reference ON cases(user_id, reference COLLATE NOCASE)")


def require_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required")
    with db() as connection:
        user = connection.execute("SELECT users.* FROM users JOIN sessions ON sessions.user_id = users.id WHERE sessions.token_hash = ? AND sessions.expires_at > ?", (token_hash(token), now())).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Session expired")
    return public_user(user)


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterInput, request: Request, response: Response) -> dict:
    user_id, salt = str(uuid.uuid4()), secrets.token_hex(16)
    hashed = password_hash(payload.password, salt)
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM users WHERE email = ?", (payload.email,)).fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")
        first_account = not connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()
        connection.execute("INSERT INTO users(id, email, password_hash, salt, audience, full_name, organisation, street, postal_code, city, country, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, payload.email, hashed, salt, payload.audience, payload.full_name, payload.organisation, payload.street, payload.postal_code, payload.city, payload.country, payload.phone, now()))
        connection.execute("UPDATE users SET profile=? WHERE id=?", (json.dumps(payload.profile.model_dump(), ensure_ascii=False), user_id))
        if first_account:
            # Preserve pre-account local prototype files for its first owner.
            connection.execute("UPDATE cases SET user_id = ? WHERE user_id IS NULL", (user_id,))
        set_session(connection, user_id, request, response)
        return public_user(connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


@app.post("/api/auth/login")
def login(payload: LoginInput, request: Request, response: Response) -> dict:
    key = check_login_limit(request)
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (payload.email.strip().lower(),)).fetchone()
        # Equal-cost comparison also for unknown addresses.
        valid = verify_password(payload.password, user["salt"] if user else "00" * 16, user["password_hash"] if user else "00" * 64)
        if not user or not valid:
            failed_logins.setdefault(key, []).append(datetime.now(UTC))
            raise HTTPException(status_code=401, detail="Email or password incorrect")
        failed_logins.pop(key, None)
        set_session(connection, user["id"], request, response)
        return public_user(user)


@app.get("/api/auth/me")
def current_user(user: dict = Depends(require_user)) -> dict:
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    with db() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(request.cookies.get(COOKIE_NAME, "")),))
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")


def owned_letterhead(connection, letterhead_id, user_id):
    row = connection.execute("SELECT * FROM letterheads WHERE id=? AND user_id=?", (letterhead_id, user_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Letterhead not found")
    return row


def public_letterhead(row):
    return {key: (json.loads(row[key]) if key in {"geometry", "layout"} else row[key]) for key in ("id", "original_name", "pdf_sha256", "geometry", "layout", "confirmed_at", "created_at")}


@app.get("/api/auth/letterheads")
def letterhead_list(user: dict = Depends(require_user)):
    with db() as connection:
        return {"active_id": user["letterhead_id"], "word_conversion_ready": bool(office_path()), "items": [public_letterhead(row) for row in connection.execute("SELECT * FROM letterheads WHERE user_id=? ORDER BY created_at DESC", (user["id"],))]}


@app.post("/api/auth/letterheads", status_code=201)
def upload_letterhead(file: UploadFile = File(...), user: dict = Depends(require_user)):
    original_name = Path((file.filename or "").replace('\\', '/')).name[:200]
    suffix = Path(original_name).suffix.lower()
    if suffix not in {'.pdf', '.doc', '.docx'}:
        raise HTTPException(status_code=415, detail="PDF, DOC or DOCX required")
    if not LETTERHEAD_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="letterhead_busy")
    try:
        with TemporaryDirectory(prefix='letterhead-') as temporary:
            source, output = Path(temporary) / ('source' + suffix), Path(temporary) / 'normalized.pdf'
            count = 0
            with source.open('wb') as stream:
                while chunk := file.file.read(65536):
                    count += len(chunk)
                    if count > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Letterhead exceeds 10 MB")
                    stream.write(chunk)
            if not count:
                raise HTTPException(status_code=422, detail="Empty letterhead")
            try:
                geometry = normalize(source, output)
            except Exception as failure:
                code = str(failure) if str(failure) in {'converter_unavailable', 'one_or_two_pages_required', 'plain_pdf_required', 'portrait_letter_paper_required', 'matching_page_sizes_required'} else 'invalid_letterhead'
                raise HTTPException(status_code=503 if code == 'converter_unavailable' else 422, detail=code) from None
            letterhead_id = str(uuid.uuid4())
            folder = DATA_DIR / 'letterheads'
            folder.mkdir(exist_ok=True, parents=True)
            original_stored, pdf_stored = letterhead_id + suffix, letterhead_id + '-normalized.pdf'
            import shutil
            shutil.copyfile(source, folder / original_stored)
            shutil.copyfile(output, folder / pdf_stored)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            with db() as connection:
                connection.execute("INSERT INTO letterheads(id,user_id,original_name,original_stored,pdf_stored,pdf_sha256,geometry,layout,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (letterhead_id, user['id'], original_name, original_stored, pdf_stored, digest, json.dumps(geometry), json.dumps(LetterheadLayout().model_dump()), now()))
                return public_letterhead(owned_letterhead(connection, letterhead_id, user['id']))
    finally:
        LETTERHEAD_LOCK.release()


@app.get("/api/auth/letterheads/{letterhead_id}/pdf")
def read_letterhead_pdf(letterhead_id: str, user: dict = Depends(require_user)):
    with db() as connection:
        row = owned_letterhead(connection, letterhead_id, user['id'])
        return FileResponse(DATA_DIR / 'letterheads' / row['pdf_stored'], media_type='application/pdf', headers={'Cache-Control': 'no-store'})


def letterhead_pdf_response(body, letterhead_id, layout, user_id):
    template = None
    if letterhead_id:
        with db() as connection:
            row = owned_letterhead(connection, letterhead_id, user_id)
            template = DATA_DIR / 'letterheads' / row['pdf_stored']
    try:
        content = compose_pdf(body, template, layout)
    except ValueError:
        raise HTTPException(status_code=422, detail='body_frame_too_small') from None
    return BinaryResponse(content, media_type='application/pdf', headers={'Cache-Control': 'no-store', 'Content-Disposition': 'inline; filename="Schimmelpilz-Entwurf.pdf"'})


@app.post("/api/auth/letterheads/{letterhead_id}/preview")
def preview_letterhead(letterhead_id: str, payload: LetterheadLayout, user: dict = Depends(require_user)):
    with db() as connection:
        owned_letterhead(connection, letterhead_id, user['id'])
    body = 'BEISPIELENTWURF / SAMPLE DRAFT\n\nEmpfänger / Recipient\nBeispielstraße 1\n10115 Berlin\n\nIhr Zeichen: [Referenz]\nUnser Zeichen: [Aktenzeichen]\n\nSehr geehrte Damen und Herren,\n\nDieser Mustertext zeigt den gewählten Schreibbereich. Prüfen Sie, dass weder Logo noch Fußzeile überdeckt werden.\n\nMit freundlichen Grüßen\n[Name]\n\n' + ('Beispieltext für die Folgeseite. Sample continuation text.\n' * 70)
    return letterhead_pdf_response(body, letterhead_id, payload.model_dump(), user['id'])


@app.put("/api/auth/letterheads/{letterhead_id}/activate")
def activate_letterhead(letterhead_id: str, payload: LetterheadActivation, user: dict = Depends(require_user)):
    if not payload.confirmed:
        raise HTTPException(status_code=422, detail='preview_confirmation_required')
    layout = payload.model_dump(exclude={'confirmed'})
    # Validate the usable frame before making it the default for new drafts.
    letterhead_pdf_response('Layoutprüfung', letterhead_id, layout, user['id'])
    with db() as connection:
        row = owned_letterhead(connection, letterhead_id, user['id'])
        if row['confirmed_at']:
            raise HTTPException(status_code=409, detail='letterhead_version_immutable')
        connection.execute("UPDATE letterheads SET layout=?,confirmed_at=? WHERE id=?", (json.dumps(layout), now(), row['id']))
        connection.execute("UPDATE users SET letterhead_id=? WHERE id=?", (row['id'], user['id']))
        return public_letterhead(owned_letterhead(connection, letterhead_id, user['id']))


def draft_letterhead(user):
    if not user['letterhead_id']:
        return None, None
    with db() as connection:
        row = owned_letterhead(connection, user['letterhead_id'], user['id'])
        return row['id'], row['layout']


@app.post("/api/cases/{case_id}/drafts/preview-pdf")
def preview_draft_pdf(case_id: str, payload: DraftPdfInput, user: dict = Depends(require_user)):
    get_case(case_id, user['id'])
    if payload.draft_id:
        with db() as connection:
            draft = connection.execute('SELECT * FROM drafts WHERE case_id=? AND id=?', (case_id, str(payload.draft_id))).fetchone()
            if not draft:
                raise HTTPException(status_code=404, detail='Draft not found')
            letterhead_id, layout = draft['letterhead_id'], draft['letterhead_layout']
        if payload.use_current_letterhead:
            letterhead_id, layout = draft_letterhead(user)
    else:
        letterhead_id, layout = draft_letterhead(user)
    return letterhead_pdf_response(payload.body, letterhead_id, json.loads(layout) if layout else LetterheadLayout(top_mm=25, bottom_mm=25).model_dump(), user['id'])


@app.get("/api/cases/{case_id}/drafts/{draft_id}/pdf")
def export_draft_pdf(case_id: str, draft_id: str, user: dict = Depends(require_user)):
    get_case(case_id, user['id'])
    with db() as connection:
        row = connection.execute('SELECT * FROM drafts WHERE case_id=? AND id=?', (case_id, draft_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Draft not found')
    return letterhead_pdf_response(row['body'], row['letterhead_id'], json.loads(row['letterhead_layout']) if row['letterhead_layout'] else LetterheadLayout(top_mm=25, bottom_mm=25).model_dump(), user['id'])


def row_case(row: sqlite3.Row, connection: sqlite3.Connection) -> dict:
    documents = connection.execute(
        """SELECT d.id, d.original_name, d.content_type, d.size_bytes, d.created_at,
            e.status AS extraction_status, e.truncated AS extraction_truncated,
            (SELECT COUNT(*) FROM document_pages p WHERE p.document_id=d.id AND p.reviewed_at IS NOT NULL) AS reviewed_units
            FROM documents d LEFT JOIN document_extractions e ON e.document_id=d.id
            WHERE d.case_id = ? ORDER BY d.created_at""",
        (row["id"],),
    ).fetchall()
    drafts = connection.execute(
        "SELECT id, language, recipient, body, kind, created_at, letterhead_id FROM drafts WHERE case_id = ? ORDER BY created_at DESC",
        (row["id"],),
    ).fetchall()
    return {
        **dict(row),
        "details": json.loads(row["details"]),
        "documents": [dict(item) for item in documents],
        "drafts": [dict(item) for item in drafts],
        "tasks": [{**dict(item), "completed": bool(item["completed"])} for item in connection.execute("SELECT * FROM tasks WHERE case_id = ? ORDER BY created_at DESC", (row["id"],))],
        "activities": [dict(item) for item in connection.execute("SELECT * FROM activities WHERE case_id = ? ORDER BY created_at DESC", (row["id"],))],
    }


def record_activity(connection, case_id: str, action: str, detail: str = "") -> dict:
    event = {"id": str(uuid.uuid4()), "case_id": case_id, "action": action, "detail": detail, "created_at": now()}
    connection.execute("INSERT INTO activities(id, case_id, action, detail, created_at) VALUES (:id, :case_id, :action, :detail, :created_at)", event)
    return event


def get_case(case_id: str, user_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT * FROM cases WHERE id = ? AND user_id = ?", (case_id, user_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Case not found")
        return row_case(row, connection)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "schimmelpilz-api", "version": app.version}


@app.get("/api/cases")
def list_cases(user: dict = Depends(require_user)) -> list[dict]:
    with db() as connection:
        return [row_case(row, connection) for row in connection.execute("SELECT * FROM cases WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))]


@app.post("/api/cases", status_code=201)
def create_case(payload: CaseCreate, user: dict = Depends(require_user)) -> dict:
    case_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if payload.reference_mode == "existing":
            reference = payload.reference
            if connection.execute("SELECT 1 FROM cases WHERE reference = ? COLLATE NOCASE AND user_id = ?", (reference, user["id"])).fetchone():
                raise HTTPException(status_code=409, detail="Reference already exists")
        else:
            # Imported references may already occupy a generated number.
            while True:
                counter = connection.execute("UPDATE counters SET value = value + 1 WHERE name = 'case_reference' RETURNING value").fetchone()[0]
                reference = f"SCH-{datetime.now().year}-{counter:06d}"
                if not connection.execute("SELECT 1 FROM cases WHERE reference = ? COLLATE NOCASE AND user_id = ?", (reference, user["id"])).fetchone():
                    break
        connection.execute(
            "INSERT INTO cases(id, reference, title, description, language, created_at, details, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, reference, payload.title, payload.description, payload.language, now(), payload.details.model_dump_json(), user["id"]),
        )
        record_activity(connection, case_id, "case_created")
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return row_case(row, connection)


@app.get("/api/cases/{case_id}")
def read_case(case_id: str, user: dict = Depends(require_user)) -> dict:
    return get_case(case_id, user["id"])


@app.put("/api/cases/{case_id}")
def update_case(case_id: str, payload: CaseUpdate, user: dict = Depends(require_user)) -> dict:
    get_case(case_id, user["id"])
    with db() as connection:
        connection.execute("UPDATE cases SET title = ?, description = ?, language = ?, details = ? WHERE id = ? AND user_id = ?", (payload.title, payload.description, payload.language, payload.details.model_dump_json(), case_id, user["id"]))
        record_activity(connection, case_id, "case_updated")
        return row_case(connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone(), connection)


@app.post("/api/cases/{case_id}/tasks", status_code=201)
def create_task(case_id: str, payload: TaskCreate, user: dict = Depends(require_user)) -> dict:
    get_case(case_id, user["id"])
    with db() as connection:
        connection.execute("INSERT INTO tasks(id, case_id, title, note, due_on, priority, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), case_id, payload.title, payload.note, payload.due_on.isoformat() if payload.due_on else None, payload.priority, now()))
        record_activity(connection, case_id, "task_created", payload.title)
        return row_case(connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone(), connection)


@app.put("/api/cases/{case_id}/tasks/{task_id}")
def update_task(case_id: str, task_id: str, payload: TaskUpdate, user: dict = Depends(require_user)) -> dict:
    get_case(case_id, user["id"])
    with db() as connection:
        task = connection.execute("SELECT * FROM tasks WHERE id = ? AND case_id = ?", (task_id, case_id)).fetchone()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        completed_at = (task["completed_at"] or now()) if payload.completed else None
        connection.execute("UPDATE tasks SET title = ?, note = ?, due_on = ?, priority = ?, completed = ?, completed_at = ? WHERE id = ? AND case_id = ?", (payload.title, payload.note, payload.due_on.isoformat() if payload.due_on else None, payload.priority, payload.completed, completed_at, task_id, case_id))
        action = "task_completed" if payload.completed else "task_reopened" if task["completed"] else "task_updated"
        record_activity(connection, case_id, action, payload.title)
        return row_case(connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone(), connection)


@app.get("/api/research/status")
def research_status(user: dict = Depends(require_user)) -> dict:
    return ollama_status()


@app.get("/api/cases/{case_id}/research")
def research_history(case_id: str, user: dict = Depends(require_user)) -> list[dict]:
    get_case(case_id, user["id"])
    with db() as connection:
        return [research_row(row) for row in connection.execute("SELECT * FROM research_runs WHERE case_id = ? ORDER BY created_at", (case_id,))]


def research_row(row):
    return {**dict(row), "sources": json.loads(row["sources"]), "document_selection": json.loads(row["document_selection"])}


@app.post("/api/cases/{case_id}/research", status_code=201)
def research_chat(case_id: str, payload: ResearchInput, user: dict = Depends(require_user)) -> dict:
    case = get_case(case_id, user["id"])
    run_id = str(payload.request_id)
    document_ids = sorted(set(str(value) for value in payload.document_ids))
    # One local inference at a time protects the single server's memory.
    if not RESEARCH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="ai_busy")
    try:
        with db() as connection:
            existing = connection.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
            if existing:
                if existing["case_id"] != case_id or existing["question"] != payload.question or existing["language"] != payload.language or existing["workflow"] != payload.workflow or json.loads(existing["document_selection"]) != document_ids:
                    raise HTTPException(status_code=409, detail="request_conflict")
                if existing["status"] == "completed":
                    return research_row(existing)
                raise HTTPException(status_code=409, detail="request_already_recorded")
            history = [dict(row) for row in connection.execute("SELECT * FROM research_runs WHERE case_id = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 6", (case_id,))][::-1]
            for document_id in document_ids:
                get_document(connection, case_id, document_id)
                if not connection.execute("SELECT 1 FROM document_pages WHERE document_id=? AND reviewed_at IS NOT NULL LIMIT 1", (document_id,)).fetchone():
                    raise HTTPException(status_code=422, detail="document_not_reviewed")
            sources = select_sources(connection, case_id, document_ids, payload.question)
            connection.execute("INSERT INTO research_runs(id, case_id, question, language, workflow, status, model, created_at, sources, document_selection) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)", (run_id, case_id, payload.question, payload.language, payload.workflow, OLLAMA_MODEL, now(), json.dumps(sources, ensure_ascii=False), json.dumps(document_ids)))
        try:
            result = generate_answer(prepare_messages(case, history, payload.question, payload.language, payload.workflow, sources))
        except (URLError, OSError, TimeoutError, ValueError) as error:
            code = "ai_timeout" if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError) else "ai_unavailable"
            with db() as connection:
                connection.execute("UPDATE research_runs SET status = 'failed', error_code = ?, finished_at = ? WHERE id = ?", (code, now(), run_id))
            raise HTTPException(status_code=504 if code == "ai_timeout" else 503, detail=code) from None
        with db() as connection:
            connection.execute("UPDATE research_runs SET status = 'completed', answer = ?, input_tokens = ?, output_tokens = ?, truncated = ?, finished_at = ? WHERE id = ?", (result["answer"], result["input_tokens"], result["output_tokens"], result["truncated"], now(), run_id))
            record_activity(connection, case_id, "research_answer")
            return research_row(connection.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone())
    finally:
        RESEARCH_LOCK.release()


def get_document(connection, case_id, document_id):
    document = connection.execute("SELECT * FROM documents WHERE id=? AND case_id=?", (document_id, case_id)).fetchone()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def document_text(connection, document_id):
    extraction = connection.execute("SELECT * FROM document_extractions WHERE document_id=?", (document_id,)).fetchone()
    units = [dict(row) for row in connection.execute("SELECT * FROM document_pages WHERE document_id=? ORDER BY unit_no", (document_id,))]
    return {"extraction": dict(extraction) if extraction else None, "units": units}


@app.get("/api/cases/{case_id}/documents/{document_id}/text")
def read_document_text(case_id: str, document_id: str, user: dict = Depends(require_user)):
    get_case(case_id, user["id"])
    with db() as connection:
        get_document(connection, case_id, document_id)
        return document_text(connection, document_id)


@app.post("/api/cases/{case_id}/documents/{document_id}/extract")
def extract_document(case_id: str, document_id: str, user: dict = Depends(require_user)):
    get_case(case_id, user["id"])
    with db() as connection:
        document = get_document(connection, case_id, document_id)
        if connection.execute("SELECT 1 FROM document_extractions WHERE document_id=?", (document_id,)).fetchone():
            return document_text(connection, document_id)
    if not EXTRACTION_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="extraction_busy")
    try:
        target = UPLOAD_DIR / document["stored_name"]
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Stored file not found")
        try:
            worker = subprocess.run([sys.executable, "-m", "server.document_extraction", str(target.resolve())], cwd=ROOT, capture_output=True, timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            result = json.loads(worker.stdout)
        except (subprocess.SubprocessError, ValueError, OSError):
            result = {"status": "failed", "error_code": "extraction_failed", "unit_kind": "page" if target.suffix == ".pdf" else "section", "truncated": False, "units": []}
        with db() as connection:
            # Another request may have completed before the lock was acquired.
            if not connection.execute("SELECT 1 FROM document_extractions WHERE document_id=?", (document_id,)).fetchone():
                connection.execute("INSERT INTO document_extractions(document_id,status,error_code,unit_kind,truncated,created_at) VALUES (?,?,?,?,?,?)", (document_id, result["status"], result["error_code"], result["unit_kind"], result["truncated"], now()))
                connection.executemany("INSERT INTO document_pages(document_id,unit_no,original_text) VALUES (?,?,?)", [(document_id, unit["unit_no"], unit["text"]) for unit in result["units"]])
                record_activity(connection, case_id, "document_extracted", document["original_name"])
            return document_text(connection, document_id)
    finally:
        EXTRACTION_LOCK.release()


@app.put("/api/cases/{case_id}/documents/{document_id}/text/{unit_no}")
def review_document_text(case_id: str, document_id: str, unit_no: int, payload: DocumentTextReview, user: dict = Depends(require_user)):
    get_case(case_id, user["id"])
    with db() as connection:
        document = get_document(connection, case_id, document_id)
        updated = connection.execute("UPDATE document_pages SET reviewed_text=?,reviewed_at=? WHERE document_id=? AND unit_no=?", (payload.text, now() if payload.reviewed else None, document_id, unit_no))
        if not updated.rowcount:
            raise HTTPException(status_code=404, detail="Text unit not found")
        record_activity(connection, case_id, "document_text_reviewed" if payload.reviewed else "document_text_unreviewed", document["original_name"])
        return document_text(connection, document_id)


@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_document(case_id: str, file: UploadFile = File(...), user: dict = Depends(require_user)) -> dict:
    get_case(case_id, user["id"])
    original = Path((file.filename or "document").replace("\\", "/")).name
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        await file.close()
        raise HTTPException(status_code=415, detail="Unsupported document type")
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(status_code=422, detail="Document is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB limit")
    document_id = str(uuid.uuid4())
    stored_name = f"{document_id}{extension}"
    target = UPLOAD_DIR / stored_name
    target.write_bytes(content)
    created = now()
    try:
        with db() as connection:
            connection.execute(
                "INSERT INTO documents(id, case_id, original_name, stored_name, content_type, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (document_id, case_id, original, stored_name, file.content_type, len(content), created),
            )
            activity = record_activity(connection, case_id, "document_uploaded", original)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"id": document_id, "case_id": case_id, "original_name": original, "content_type": file.content_type, "size_bytes": len(content), "created_at": created, "activity": activity}


@app.get("/api/cases/{case_id}/documents/{document_id}/download")
def download_document(case_id: str, document_id: str, user: dict = Depends(require_user)):
    get_case(case_id, user["id"])
    with db() as connection:
        document = connection.execute("SELECT * FROM documents WHERE case_id = ? AND id = ?", (case_id, document_id)).fetchone()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    target = UPLOAD_DIR / document["stored_name"]
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(target, filename=document["original_name"], media_type="application/octet-stream", headers={"X-Content-Type-Options": "nosniff"})


@app.post("/api/cases/{case_id}/drafts", status_code=201)
def create_draft(case_id: str, payload: DraftCreate, user: dict = Depends(require_user)) -> dict:
    case = get_case(case_id, user["id"])
    german = payload.language == "de"
    body = payload.body if payload.body is not None else (
        f"Sehr geehrte Damen und Herren,\n\n"
        f"hiermit nehme ich Bezug auf den Fall {case['reference']} ({case['title']}).\n\n"
        f"{case['description']}\n\n"
        "Bitte lassen Sie mir hierzu zeitnah eine schriftliche Stellungnahme zukommen.\n\n"
        "Mit freundlichen Grüßen"
        if german
        else f"Dear Sir or Madam,\n\nI am writing regarding case {case['reference']} ({case['title']}).\n\n"
        f"{case['description']}\n\nPlease provide a written response at your earliest convenience.\n\nYours sincerely"
    )
    draft_id = str(uuid.uuid4())
    created = now()
    letterhead_id, letterhead_layout = draft_letterhead(user)
    with db() as connection:
        connection.execute("INSERT INTO drafts(id, case_id, language, recipient, body, created_at, kind, letterhead_id, letterhead_layout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (draft_id, case_id, payload.language, payload.recipient.strip(), body, created, payload.kind, letterhead_id, letterhead_layout))
        activity = record_activity(connection, case_id, "draft_created", payload.kind)
    return {"id": draft_id, "case_id": case_id, "language": payload.language, "recipient": payload.recipient, "kind": payload.kind, "body": body, "created_at": created, "letterhead_id": letterhead_id, "activity": activity, "disclaimer": "Draft only; have a qualified lawyer review it before sending."}


@app.put("/api/cases/{case_id}/drafts/{draft_id}")
def update_draft(case_id: str, draft_id: str, payload: DraftUpdate, user: dict = Depends(require_user)) -> dict:
    get_case(case_id, user["id"])
    with db() as connection:
        result = connection.execute("UPDATE drafts SET body = ?, recipient = COALESCE(?, recipient), kind = COALESCE(?, kind), language = COALESCE(?, language) WHERE case_id = ? AND id = ?", (payload.body, payload.recipient, payload.kind, payload.language, case_id, draft_id))
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="Draft not found")
        if payload.use_current_letterhead:
            letterhead_id, layout = draft_letterhead(user)
            connection.execute('UPDATE drafts SET letterhead_id=?,letterhead_layout=? WHERE id=?', (letterhead_id, layout, draft_id))
        activity = record_activity(connection, case_id, "draft_updated", payload.kind or "")
        return {**dict(connection.execute("SELECT id, case_id, language, recipient, body, kind, created_at, letterhead_id FROM drafts WHERE id = ?", (draft_id,)).fetchone()), "activity": activity}
