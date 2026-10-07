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
- `POST /api/auth/register` with email, password (12+ characters), audience, name and contact address. Business/law-firm accounts also require an organisation; optional `profile` stores legal form, role, representative, registry court/number, VAT ID and industry or responsible lawyer, bar association, admission country and practice areas. These are self-declared details, not verified professional status or shared-staff permissions.
- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
- `GET /api/auth/letterheads`, `POST /api/auth/letterheads` (multipart `file`, PDF/DOC/DOCX, maximum 10 MB).
- `GET /api/auth/letterheads/{id}/pdf`, `POST /api/auth/letterheads/{id}/preview` with margin settings, and `PUT /api/auth/letterheads/{id}/activate` with the same settings and `confirmed: true`.
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
- `POST /api/cases/{id}/drafts` with `{ "language", "recipient", "kind", "body", "research_run_id" }`. Kinds: `letter`, `claim`, `application`, `objection`, `response`. Only a basic letter can omit `body`.
- `PUT /api/cases/{id}/drafts/{draft_id}` with `{ "body", "recipient", "kind", "language", "expected_version" }` stores the edited text and metadata. Optional `use_current_letterhead: true` adopts the currently active briefpaper version; otherwise the saved version is retained.
- `POST /api/cases/{id}/drafts/preview-pdf` with `body`, optional `draft_id` and `use_current_letterhead` exports current editor text without saving it. `GET /api/cases/{id}/drafts/{draft_id}/pdf` exports the saved version.

All case, document and draft routes require a signed-in account. Every write request, including login/register/logout, must include `X-Schimmelpilz-Request: 1`. The frontend includes the header and session cookie automatically.

## Persistent local storage

SQLite is included with Python; no separate database installation is needed. The API opens and initialises the existing database on startup without deleting records. It uses transactions for case references and draft writes.

In the default Shadow PC setup, data lives under `C:\Users\Shadow\Downloads\ai\data`:

- `app.db`: accounts, password hashes, hashed session tokens, case particulars, references, document metadata, exact draft text, tasks, activity and research runs with model/token/status metadata.
- `uploads/`: document contents under generated filenames, outside the public web folder.
- `letterheads/`: private original uploads and normalized PDF templates. SQLite stores ownership, dimensions, SHA-256, margins, confirmation and the version used by each draft.
- `app.db-wal` and `app.db-shm`, when present, are SQLite working files.

After a browser reload, the frontend fetches saved cases from the API. The saved-case selector restores the last chosen case. Browser storage holds only that case ID and the interface language, not the document contents or draft text. Clearing browser storage does not delete server records. Data also survives an API restart, provided the data directory is retained. This does not protect against disk loss or a Shadow PC reset.

Set `DATA_DIR` before starting the API to choose another directory. Docker uses `/data` in the persistent `app_data` volume. The repository ignores runtime data; GitHub receives source code only.

## Storage verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r server/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s server/tests -v
```

The tests use temporary storage, leaving real cases untouched. They check persistence, edited text, account isolation, migration of legacy data, references, uploaded-byte downloads and validation.

## Registration and letter paper

The bilingual registration form separates consumer, company and law-firm fields. Companies and firms receive an optional second onboarding step for blank letter paper; existing accounts can configure it under their profile. Upload a template without an old letter body or recipient. Accept one or two equal-size portrait pages: page one is used first, and the last template page repeats on continuation pages. PDF templates must be unencrypted, without annotations, form fields, rotation or cropped pages.

PDF drawing content is reused at its original size and position; draft text is added inside a user-selected writing frame. Top, bottom, left and right margins apply to every page. Activation requires a sample preview and an explicit layout confirmation in the UI. Confirmed versions are immutable. New drafts snapshot the active version and margins; older drafts keep their version until the user opts to adopt the current briefhead when saving. Plain-text downloads cannot contain a graphic letterhead. PDF output is available; editable DOCX output, automatic signature and dispatch are not implemented.

Word templates are converted locally using LibreOffice with a separate temporary profile, macros disabled and a 60-second timeout. Font substitution and line breaks can change during conversion, so the converted PDF must be checked before confirmation. Original uploads are retained privately. This is not a process sandbox for untrusted Office files; production operators must add converter isolation and maintain its security updates.

Install LibreOffice Writer on the server or set `SOFFICE_PATH` to its executable. Native Shadow development detects the official extracted runtime at `data/libreoffice/program/soffice.exe`; this ignored runtime is not uploaded to GitHub. Docker installs LibreOffice Writer and fonts. No converter means Word upload returns 503; PDF templates continue to work. PDF.js renders preview pages in the browser using bundled worker/font assets; licences are under `docs/licenses/`.

## Accounts and migration

Passwords use salted scrypt hashes. Opaque sessions expire after seven days, are stored as hashes, and use HttpOnly/SameSite=Strict cookies. Failed sign-ins are limited per client address. Docker Compose sets `COOKIE_SECURE=true` for HTTPS behind Caddy; native localhost development uses HTTP cookies.

The first registered account takes ownership of local prototype cases created before accounts existed. Later accounts start with separate files. On an existing installation, register the owner's account locally before opening registration to the public. Startup preserves legacy case, document and draft IDs and adds the new fields. References are unique per account, not shared passwords.

The current workflow supports consumers, businesses and law firms. It does not yet include shared firm memberships, invitation administration, email verification, password recovery, MFA or backup scheduling. Public German federal sources can be imported and searched locally. Substantive legal approval, fee/jurisdiction calculation and electronic filing remain planned. Local AI answers and editable drafts are not reviewed legal opinions.

## Local research AI

Run official Ollama bound to `127.0.0.1:11434` with cloud features disabled (`OLLAMA_NO_CLOUD=1`), then pull `qwen2.5:7b`. Configure the API through `OLLAMA_BASE_URL` and `OLLAMA_MODEL` if needed. Docker uses the private `ollama` service and persistent model volume; run `docker compose exec ollama ollama pull qwen2.5:7b` once. Do not publish the model port.

The API supplies selected account-owned particulars, workflow instructions, bounded completed conversation, reviewed document passages and selected or locally found legal passages to the actual Ollama chat endpoint. Only public provider XML is fetched externally; questions and case documents stay on this server. Output is plain text with linked citation IDs and is clearly labelled unverified. A generation is recorded before inference; failures remain visible without a fabricated answer. Requests time out after 180 seconds and a single-worker process lock prevents simultaneous inference. A request left pending after a server crash can be asked again with a new ID. API tests use a mock model; the native preview is additionally tested against the installed runtime with synthetic cases.

## Public legal source catalogue

`LEGAL_DATA_DIR` defaults to `data/legal-sources`, independently of account `DATA_DIR`; Docker sets it to `/data/legal-sources` in the persistent volume. It contains public XML-derived text and a SQLite FTS5 index, never private case content. Private attachments/review notes and per-answer copies live in the account database. Runtime files remain excluded from Git.

The adapter imports BGB, EGBGB, ZPO, GVG, HGB, GmbHG, InsO, KSchG, BUrlG, ArbGG, FamFG, VwGO, SGG, StGB, StPO, VwVfG, RVG, GKG, FamGKG, GG, SGB I, II and X. These are provider-consolidated current texts, not official promulgations or proof of historical applicability. It imports the published RII decision metadata index and initially eight latest decisions per supported federal court. Topic search covers downloaded texts; reference/court/date search covers the published metadata. Other decisions are downloaded on demand. This is not exhaustive federal/state/EU/Mexican case law. No proprietary database or general web-search integration is provided.

In Recherche, **Katalog aktualisieren** starts a background refresh. A fresh deployment starts with an empty catalogue until refreshed. Alternatively run `python -m server.legal_catalogue` from the repository root (or `docker compose exec api python -m server.legal_catalogue`). Imports replace each collection transactionally; failed imports preserve its last usable version. Progress and failed collections are persisted. There is no scheduled refresh. Inspect collection and passage timestamps before relying on them.

Authenticated routes:

- `GET /api/legal/status`: counts, coverage, collection dates and refresh progress.
- `POST /api/legal/refresh`: start refresh (202); only allowlisted public provider URLs are followed, including redirects.
- `GET /api/legal/search?q=...&kind=all|law|decision`: local search, 2–200 characters, at most 15 results.
- `GET /api/legal/source?key=...`: load/validate the original full snapshot by indexed identifier; unknown source 404, failed retrieval 503.
- `GET/POST /api/cases/{id}/legal-sources`: list or attach an immutable snapshot (`{"key": "..."}`); case ownership required, at most 250 attachments.
- `PUT /api/cases/{id}/legal-sources/{source_id}/review`: `status` pending/checked/excluded and `note`; checked requires a note of at least 10 characters. This records the user's review, not independent approval. Excluded sources cannot enter new answers.
- Research POST adds `legal_source_ids` (at most eight owned attachments) and `use_legal_catalogue` (default false for API compatibility, enabled by default in the DE interface). Other jurisdictions reject German legal context. Reusing a generation ID with a changed source selection returns 409.

The model receives at most eight legal passages, two per source, 1,800 characters each and 9,000 combined. Statute locations are labelled paragraph *blocks*, rather than inferred subsection numbers; decision paragraph numbers come from XML. Excerpts may omit footnotes, tables, other provisions or reasoning. Every run stores exact passages, snapshot/excerpt SHA-256, retrieval date, metadata and review state. The snapshot hash covers parsed content, not the original ZIP bytes. Later refreshes/review changes do not rewrite history. Unknown or missing [L#] identifiers are flagged; identifier matching does not check semantic support, adverse authority or applicable versions. Draft adoption appends this ledger to the text, including warning markers; existing PDF export preserves it. The draft remains editable and requires legal review.

Extraction is limited to 80 physical PDF pages or DOCX body sections, 12,000 characters per unit and 120,000 characters total. DOCX headers, footnotes and page layout are not extracted. The chat receives up to 12 reviewed excerpts, each at most 2,400 characters and 8,000 characters combined, ranked by question terms. This is partial document context, not a full file analysis. Each research run stores the exact excerpt, filename, page/section, text-review timestamp and full reviewed-unit SHA-256. Later corrections do not change historical runs; revoking review prevents using that text in a new request. Existing chat history remains part of the bounded conversation. Original uploads stay private and unchanged. Draft adoption retains the document provenance ledger.

From the repository root, `./start-local.ps1` starts/reuses the native local model, API (8001) and frontend (4173). It uses the existing `.venv`, installed frontend dependencies and portable Ollama, and does not download models or reset data. The separate preview can be started with `-ApiPort 8002 -WebPort 4174 -DataDirectory data/desk-preview`. Runtime logs are in the selected data directory. This launcher is not a Windows login task or production process supervisor.

## Versioned draft review

See [review workflow and boundaries](../docs/draft-review.md). Draft creation optionally accepts a completed same-case `research_run_id`; only server-saved provenance is trusted. Legacy snapshots are backfilled additively without inventing source context or older history.

- `GET /api/cases/{id}/drafts/{draft_id}/review`: current draft, checklist/text blocks, original supplied passages, hard blocks, versions and review events.
- `GET /api/cases/{id}/drafts/{draft_id}/versions/{version}`: read-only content snapshot and hash.
- `POST /api/cases/{id}/drafts/{draft_id}/review`: `action` (`begin`, `check`, `approve`, `reopen`), required `expected_version` and `expected_review_revision`. Check includes `check_id`, `checked`, `note` (10+ characters when checked); approve requires `confirmed: true`, `note` (20+ characters), no blockers and all checklist/text blocks reviewed. Conflicts/unresolved checks return 409; invalid notes/confirmation return 422.

Every successful review write increments the review revision. Actual draft edits increment the content version, clear current approval and preserve immutable versions/earlier approval evidence. Unchanged saves do not increment/reset. Saved PDF exports include `X-Draft-Version`, `X-Draft-Review-Status` and version/status filenames, not a signature or legal approval stamp. These remain account-holder reviews; no role-based independent reviewer has been added.
