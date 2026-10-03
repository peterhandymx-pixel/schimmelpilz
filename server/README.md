# Schimmelpilz MVP API

This is the first local API for the single-server setup. It stores the SQLite database at `DATA_DIR/app.db` and uploaded files under `DATA_DIR/uploads`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r server/requirements.txt
python -m uvicorn server.app:app --reload --port 8000
```

Endpoints:

- `GET /api/health`
- `POST /api/cases` with `{ "title", "description", "language" }`
- `GET /api/cases/{id}`
- `POST /api/cases/{id}/documents` as multipart field `file`
- `POST /api/cases/{id}/drafts` with `{ "language", "recipient" }`

The API intentionally has no user authentication yet. Do not expose it publicly until sessions, case permissions, CSRF protection and encrypted backups are implemented.
