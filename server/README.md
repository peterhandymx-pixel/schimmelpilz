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
- `PUT /api/cases/{id}` edits title, description, language and details; internal reference is immutable.
- `POST /api/cases/{id}/tasks`, `PUT /api/cases/{id}/tasks/{task_id}` persist manual tasks (title, note, optional due date, priority, completion). Case responses include tasks and activity.
- `GET /api/research/status` checks local model availability.
- `GET /api/cases/{id}/research` returns the account-owned conversation.
- `POST /api/cases/{id}/research` with UUID `request_id`, `question` (3–4000 characters), `language`, `workflow` (`intake`, `research`, `jurisdiction`, `costs`, `drafting`, `deadlines`) and optional `document_ids` (up to 8 account-owned files from this case). Selected files need reviewed text or return 422. Responses contain the exact supplied document excerpts and their provenance. Completed requests are idempotent; conflicting reuse returns 409. Busy returns 429; unavailable model 503; timeout 504.
- `POST /api/cases/{id}/documents` as multipart field `file`
- `GET /api/cases/{id}/documents/{document_id}/download`
- `GET /api/cases/{id}/documents/{document_id}/text` returns original extracted units, corrected text and review status.
- `POST /api/cases/{id}/documents/{document_id}/extract` extracts PDF text layers or DOCX body paragraphs/tables in a local, time-limited worker. Repeated extraction preserves corrections. Scans require OCR; images and legacy DOC are unsupported. Encrypted/invalid files retain their original upload.
- `PUT /api/cases/{id}/documents/{document_id}/text/{unit_no}` with `text` and `reviewed` saves a corrected page/section. Review checks transcription, not factual truth or legal validity. Empty text cannot be marked reviewed.
- `POST /api/cases/{id}/drafts` with `{ "language", "recipient", "kind", "body" }`. Kinds: `letter`, `claim`, `application`, `objection`, `response`. Only a basic letter can omit `body`.
- `PUT /api/cases/{id}/drafts/{draft_id}` with `{ "body", "recipient", "kind", "language" }` stores the edited text and metadata.

All case, document and draft routes require a signed-in account. Every write request, including login/register/logout, must include `X-Schimmelpilz-Request: 1`. The frontend includes the header and session cookie automatically.

## Persistent local storage

SQLite is included with Python; no separate database installation is needed. The API opens and initialises the existing database on startup without deleting records. It uses transactions for case references and draft writes.

In the default Shadow PC setup, data lives under `C:\Users\Shadow\Downloads\ai\data`:

- `app.db`: accounts, password hashes, hashed session tokens, case particulars, references, document metadata, exact draft text, tasks, activity and research runs with model/token/status metadata.
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

The current workflow supports consumers, businesses and law firms. It does not yet include shared firm memberships, invitation administration, email verification, password recovery, MFA or backup scheduling. Automatic source ingestion/verification, fee/jurisdiction calculation and electronic filing remain planned. Local AI answers and editable drafts are not reviewed legal opinions.

## Local research AI

Run official Ollama bound to `127.0.0.1:11434` with cloud features disabled (`OLLAMA_NO_CLOUD=1`), then pull `qwen2.5:7b`. Configure the API through `OLLAMA_BASE_URL` and `OLLAMA_MODEL` if needed. Docker uses the private `ollama` service and persistent model volume; run `docker compose exec ollama ollama pull qwen2.5:7b` once. Do not publish the model port.

The API supplies selected account-owned particulars, project-specific workflow instructions, bounded completed conversation and explicitly selected reviewed document passages to the actual Ollama chat endpoint. It does not fetch external legal sources. Output is plain text and clearly labelled unverified. A generation is recorded before inference; failures remain visible without a fabricated answer. Requests time out after 180 seconds and a single-worker process lock prevents simultaneous inference. A request left pending after a server crash can be asked again with a new ID. API test cases use a mock model; the native preview is additionally tested against the installed runtime with synthetic cases.

Extraction is limited to 80 physical PDF pages or DOCX body sections, 12,000 characters per unit and 120,000 characters total. DOCX headers, footnotes and page layout are not extracted. The chat receives up to 12 reviewed excerpts, each at most 2,400 characters and 8,000 characters combined, ranked by question terms. This is partial document context, not a full file analysis. Each research run stores the exact excerpt, filename, page/section, text-review timestamp and full reviewed-unit SHA-256. Later corrections do not change historical runs; revoking review prevents using that text in a new request. Existing chat history remains part of the bounded conversation. Original uploads stay private and unchanged. Draft adoption retains the document provenance ledger.

From the repository root, `./start-local.ps1` starts/reuses the native local model, API (8001) and frontend (4173). It uses the existing `.venv`, installed frontend dependencies and portable Ollama, and does not download models or reset data. The separate preview can be started with `-ApiPort 8002 -WebPort 4174 -DataDirectory data/desk-preview`. Runtime logs are in the selected data directory. This launcher is not a Windows login task or production process supervisor.
