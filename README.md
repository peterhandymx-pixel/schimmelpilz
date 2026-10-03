# AI Rechtsanwalt Schimmelpilz

Implementation plan for an English/German legal assistant on one self-managed server.

Status: working prototype. The bilingual landing page and the first single-server API are implemented; authentication, production document processing and legal review workflows still belong to the next milestones.

## One-server architecture

Use one Linux server in the location selected by the owner. Run three services through Docker Compose:

| Service | Responsibility |
| --- | --- |
| Web application | Bilingual interface, login, cases, uploads, chat, document editing and exports |
| Ollama | Run the chosen English/German model locally; disable cloud features |
| Caddy | HTTPS and routing to the web application |

Use a Python/FastAPI application with server-rendered templates and small amounts of JavaScript. Keep the database in SQLite and uploads in private local directories. Run a single application worker initially, with a persistent job queue in SQLite for document extraction and model requests. No separate database server, Redis, hosted vector database or external AI API is needed for the first version.

Only Caddy exposes public web ports. The application and Ollama communicate over an internal Docker network. The browser never calls Ollama directly. Pin dependency and container versions when implementation starts.

All case storage, OCR, AI inference and document generation happen on this server. Optional off-server backups are operator-managed and must be treated as a separate data flow. GitHub holds source code and documentation; runtime data stays outside Git.

## First release

1. One administrator account and invitation-only user accounts; English/German language switch.
2. Case creation with a transactionally allocated internal Aktenzeichen, for example SCH-2026-000001. Store court and other official references separately. Use a database ID for ownership and permissions, rather than treating a reference number as a password.
3. Case overview with parties, jurisdiction, facts, notes, timeline and confirmed deadlines.
4. PDF, DOCX and image uploads with local extraction/OCR. Show the source page and allow correction before extracted information becomes a confirmed case fact.
5. Case chat that retrieves relevant case excerpts and a locally maintained legal source collection. Display source links, document pages and source-check dates. Ask for missing facts and explicitly flag unsupported claims.
6. Editable drafts: factual summaries, correspondence, requests and selected legal document templates. Export DOCX and PDF. Keep drafts, revisions and review status.
7. A reviewer role that can edit and approve documents. Persist who approved which version and when.
8. Owner-only administration for accounts, model configuration, backups, source updates and audit history.

The language setting controls interface and output language. The case jurisdiction controls applicable law. Start with German law and a narrow document set. If mould-related tenancy disputes are the intended speciality, use that as the first legal area.

## Data and access

SQLite tables: users, sessions, cases, case_members, reference_counters, parties, documents, extracted_pages, messages, drafts, draft_versions, reviews, deadlines, jobs, legal_sources and audit_events.

Every case, file, chat and export operation checks case membership. Store uploaded files under generated names outside the public directory, enforce size/type limits, and serve them only through authenticated routes. Uploaded document text is untrusted input, never an instruction to the model.

Store hashed passwords, use secure server-side sessions, CSRF protection, login throttling and administrator MFA. Keep document contents out of routine logs. Keep secrets in server environment configuration. Retention/deletion settings must cover database rows, uploads, exports and backups.

## Server and model selection

The same server must have enough RAM/VRAM for the selected model, context size and concurrent requests. Select a local model with suitable English/German performance and a licence appropriate for the intended use. Benchmark representative documents on the actual hardware before choosing a model or quoting capacity. CPU inference is possible, but latency may be unsuitable for interactive use.

Set OLLAMA_NO_CLOUD=1, select a local model, and do not publish Ollama's port. Queue requests and start with one model request at a time. A model download needs internet access; ordinary local inference should not send case content to a cloud model.

## Deployment handoff

The implementation should include a Dockerfile, compose.yaml, Caddyfile, .env.example, version-locked dependencies, a database migration command, first-admin setup, a health endpoint, backup/restore scripts and deployment instructions.

The owner supplies the server, domain, DNS and secret values. Target workflow once those deployment files exist:

1. Clone the GitHub repository onto the server.
2. Copy .env.example to .env and configure the domain, application secret and local model.
3. Start the Compose services, initialise storage and create the first administrator.
4. Download the selected model and test a synthetic case end to end.
5. Configure encrypted backups and perform a restore test.

For upgrades: back up persistent data, fetch a reviewed Git revision, rebuild containers, apply migrations, and verify health. Keep a known-good application revision and a matching database backup for rollback. Do not remove persistent volumes during routine updates.

## Implementation sequence and acceptance

| Step | Deliverable | Acceptance |
| --- | --- | --- |
| 1 | Login, bilingual UI and case management | Language preference persists; unauthorised users cannot read another case; concurrent creation does not duplicate references |
| 2 | Uploads and local extraction | A scan and a text PDF produce reviewable page text; private files cannot be fetched anonymously |
| 3 | Local model chat and sources | A synthetic case gets a sourced answer; missing evidence is flagged; embedded document instructions do not override system rules |
| 4 | Drafts, review and exports | A reviewed version exports to usable DOCX/PDF with the correct parties and references |
| 5 | One-server deployment | Recreating containers preserves cases; restore recovers the database and corresponding files; model endpoint stays private |

## Operating boundary

This server layout simplifies infrastructure. It does not itself authorise personalised legal services. German-law advice offered from Mexico remains subject to the relevant German legal-service rules. Before public use, establish the authorised service model, review the public brand, and assess privacy/data-transfer obligations for the actual operator and clients. A review status describes document workflow, not a legal authorisation.

## References

- [Docker Compose](https://docs.docker.com/compose/)
- [Ollama local-only settings and resource guidance](https://docs.ollama.com/faq)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [German RDG territorial scope](https://www.gesetze-im-internet.de/rdg/__1.html)

<details>
<summary>🥚 Easter egg: wenn die Akte eskaliert</summary>

![Wenn die Akte eskaliert](docs/assets/akten-chaos-easter-egg.jpg)

</details>

Plan prepared 3 October 2026.
