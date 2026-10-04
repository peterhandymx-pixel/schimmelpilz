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
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from .auth import COOKIE_NAME, RegisterInput, LoginInput, public_user, password_hash, verify_password, set_session, token_hash, check_login_limit, failed_logins

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".zip"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Virtuelle Rechtsassistenz Schimmelpilz", version="0.3.0", lifespan=lifespan)
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

    @field_validator("client_name", "client_email", "client_address", "opponent_name", "opponent_address", "opponent_reference", "objective", "court", "court_reference", "deadline_note", mode="before")
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


class DraftUpdate(BaseModel):
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
            CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
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


def row_case(row: sqlite3.Row, connection: sqlite3.Connection) -> dict:
    documents = connection.execute(
        "SELECT id, original_name, content_type, size_bytes, created_at FROM documents WHERE case_id = ? ORDER BY created_at",
        (row["id"],),
    ).fetchall()
    drafts = connection.execute(
        "SELECT id, language, recipient, body, kind, created_at FROM drafts WHERE case_id = ? ORDER BY created_at DESC",
        (row["id"],),
    ).fetchall()
    return {
        **dict(row),
        "details": json.loads(row["details"]),
        "documents": [dict(item) for item in documents],
        "drafts": [dict(item) for item in drafts],
    }


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
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return row_case(row, connection)


@app.get("/api/cases/{case_id}")
def read_case(case_id: str, user: dict = Depends(require_user)) -> dict:
    return get_case(case_id, user["id"])


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
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"id": document_id, "case_id": case_id, "original_name": original, "content_type": file.content_type, "size_bytes": len(content), "created_at": created}


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
    with db() as connection:
        connection.execute("INSERT INTO drafts(id, case_id, language, recipient, body, created_at, kind) VALUES (?, ?, ?, ?, ?, ?, ?)", (draft_id, case_id, payload.language, payload.recipient.strip(), body, created, payload.kind))
    return {"id": draft_id, "case_id": case_id, "language": payload.language, "recipient": payload.recipient, "kind": payload.kind, "body": body, "created_at": created, "disclaimer": "Draft only; have a qualified lawyer review it before sending."}


@app.put("/api/cases/{case_id}/drafts/{draft_id}")
def update_draft(case_id: str, draft_id: str, payload: DraftUpdate, user: dict = Depends(require_user)) -> dict:
    get_case(case_id, user["id"])
    with db() as connection:
        result = connection.execute("UPDATE drafts SET body = ?, recipient = COALESCE(?, recipient), kind = COALESCE(?, kind), language = COALESCE(?, language) WHERE case_id = ? AND id = ?", (payload.body, payload.recipient, payload.kind, payload.language, case_id, draft_id))
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="Draft not found")
        return dict(connection.execute("SELECT id, case_id, language, recipient, body, kind, created_at FROM drafts WHERE id = ?", (draft_id,)).fetchone())
