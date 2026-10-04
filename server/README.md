# Schimmelpilz MVP API

This is the first local API for the single-server setup. It stores the SQLite database at `DATA_DIR/app.db` and uploaded files under `DATA_DIR/uploads`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r server/requirements.txt
python -m uvicorn server.app:app --reload --port 8001
```

Endpoints:

- `GET /api/health`
- `GET /api/cases` returns saved cases, documents and drafts.
- `POST /api/auth/register` with email, password (12+ characters), audience, name and contact address. Business/law-firm accounts also require an organisation.
- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
- `POST /api/cases` with `{ "title", "description", "language", "reference_mode", "reference", "details" }`. Use `generate` or `existing`; an existing reference must be unique within the account. Court and opponent references belong in `details`.
- `GET /api/cases/{id}`
- `POST /api/cases/{id}/documents` as multipart field `file`
- `GET /api/cases/{id}/documents/{document_id}/download`
- `POST /api/cases/{id}/drafts` with `{ "language", "recipient", "kind", "body" }`. Kinds: `letter`, `claim`, `application`, `objection`, `response`. Only a basic letter can omit `body`.
- `PUT /api/cases/{id}/drafts/{draft_id}` with `{ "body", "recipient", "kind", "language" }` stores the edited text and metadata.

All case, document and draft routes require a signed-in account. Every write request, including login/register/logout, must include `X-Schimmelpilz-Request: 1`. The frontend includes the header and session cookie automatically.

## Persistent local storage

SQLite is included with Python; no separate database installation is needed. The API opens and initialises the existing database on startup without deleting records. It uses transactions for case references and draft writes.

In the default Shadow PC setup, data lives under `C:\Users\Shadow\Downloads\ai\data`:

- `app.db`: accounts, password hashes, hashed session tokens, case particulars, references, document metadata and the exact saved draft text.
- `uploads/`: document contents under generated filenames, outside the public web folder.
- `app.db-wal` and `app.db-shm`, when present, are SQLite working files.

After a browser reload, the frontend fetches saved cases from the API. The saved-case selector restores the last chosen case. Browser storage holds only that case ID and the interface language, not the document contents or draft text. Clearing browser storage does not delete server records. Data also survives an API restart, provided the data directory is retained. This does not protect against disk loss or a Shadow PC reset.

Set `DATA_DIR` before starting the API to choose another directory. Docker uses `/data` in the persistent `app_data` volume. The repository ignores runtime data; GitHub receives source code only.

## Storage verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r server/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s server/tests -v
```

The tests use temporary storage, leaving real cases untouched. They check persistence, edited text, account isolation, migration of legacy data, references, uploaded-byte downloads and validation.

## Accounts and migration

Passwords use salted scrypt hashes. Opaque sessions expire after seven days, are stored as hashes, and use HttpOnly/SameSite=Strict cookies. Failed sign-ins are limited per client address. Docker Compose sets `COOKIE_SECURE=true` for HTTPS behind Caddy; native localhost development uses HTTP cookies.

The first registered account takes ownership of local prototype cases created before accounts existed. Later accounts start with separate files. On an existing installation, register the owner's account locally before opening registration to the public. Startup preserves legacy case, document and draft IDs and adds the new fields. References are unique per account, not shared passwords.

The current workflow supports consumers, businesses and law firms. It does not yet include shared firm memberships, invitation administration, email verification, password recovery, MFA or backup scheduling. Automatic AI analysis, source ingestion, fee/jurisdiction calculation and electronic filing remain planned. Drafts are editable templates, not automatically reviewed legal opinions.
