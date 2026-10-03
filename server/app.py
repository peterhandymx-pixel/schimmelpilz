"""Small single-server API for the Schimmelpilz MVP.

Runtime data is written to DATA_DIR (outside the public landing-page build).
This is a prototype boundary: it has no login or production legal workflow yet.
"""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".zip"}

app = FastAPI(title="Virtuelle Rechtsassistenz Schimmelpilz", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    language: str = Field(default="de", pattern="^(de|en)$")


class DraftCreate(BaseModel):
    language: str = Field(default="de", pattern="^(de|en)$")
    recipient: str = Field(default="Vermietung", max_length=160)


def now() -> str:
    return datetime.now(UTC).isoformat()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                reference TEXT NOT NULL UNIQUE,
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
            INSERT OR IGNORE INTO counters(name, value) VALUES ('case_reference', 0);
            """
        )


@app.on_event("startup")
def startup() -> None:
    init_db()


def row_case(row: sqlite3.Row, connection: sqlite3.Connection) -> dict:
    documents = connection.execute(
        "SELECT id, original_name, content_type, size_bytes, created_at FROM documents WHERE case_id = ? ORDER BY created_at",
        (row["id"],),
    ).fetchall()
    drafts = connection.execute(
        "SELECT id, language, recipient, body, created_at FROM drafts WHERE case_id = ? ORDER BY created_at DESC",
        (row["id"],),
    ).fetchall()
    return {
        **dict(row),
        "documents": [dict(item) for item in documents],
        "drafts": [dict(item) for item in drafts],
    }


def get_case(case_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Case not found")
        return row_case(row, connection)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "schimmelpilz-api", "version": app.version}


@app.get("/api/cases")
def list_cases() -> list[dict]:
    with db() as connection:
        return [row_case(row, connection) for row in connection.execute("SELECT * FROM cases ORDER BY created_at DESC")]


@app.post("/api/cases", status_code=201)
def create_case(payload: CaseCreate) -> dict:
    case_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        counter = connection.execute("UPDATE counters SET value = value + 1 WHERE name = 'case_reference' RETURNING value").fetchone()[0]
        reference = f"SCH-{datetime.now().year}-{counter:06d}"
        connection.execute(
            "INSERT INTO cases(id, reference, title, description, language, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, reference, payload.title.strip(), payload.description.strip(), payload.language, now()),
        )
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return row_case(row, connection)


@app.get("/api/cases/{case_id}")
def read_case(case_id: str) -> dict:
    return get_case(case_id)


@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_document(case_id: str, file: UploadFile = File(...)) -> dict:
    get_case(case_id)
    original = Path(file.filename or "document").name
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported document type")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB limit")
    document_id = str(uuid.uuid4())
    stored_name = f"{document_id}{extension}"
    target = UPLOAD_DIR / stored_name
    target.write_bytes(content)
    created = now()
    with db() as connection:
        connection.execute(
            "INSERT INTO documents(id, case_id, original_name, stored_name, content_type, size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (document_id, case_id, original, stored_name, file.content_type, len(content), created),
        )
    return {"id": document_id, "case_id": case_id, "original_name": original, "size_bytes": len(content), "created_at": created}


@app.post("/api/cases/{case_id}/drafts", status_code=201)
def create_draft(case_id: str, payload: DraftCreate) -> dict:
    case = get_case(case_id)
    german = payload.language == "de"
    body = (
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
        connection.execute("INSERT INTO drafts(id, case_id, language, recipient, body, created_at) VALUES (?, ?, ?, ?, ?, ?)", (draft_id, case_id, payload.language, payload.recipient.strip(), body, created))
    return {"id": draft_id, "case_id": case_id, "language": payload.language, "recipient": payload.recipient, "body": body, "created_at": created, "disclaimer": "Draft only; have a qualified lawyer review it before sending."}

