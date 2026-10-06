# AI Rechtsanwalt Schimmelpilz

Implementation plan for an English/German legal assistant on one self-managed server.

Status: working local prototype for consumers, businesses and law firms. Implemented: bilingual landing page, tailored registration/sign-in, account-owned case files, structured intake, persistent documents with reviewed PDF/DOCX text extraction, editable drafts with private letter-paper PDF exports, manual tasks/activity and a local Ollama research bot with a German federal-law catalogue. OCR, legal calculations and document approval remain planned.

The application restores saved cases, documents, drafts, tasks and research conversations after browser reloads and backend restarts. Open a case under **Aktenbestand** to use its overview, parties, documents, drafts, deadlines/tasks and history registers. Internal references stay unchanged when particulars are edited. Global registers provide search across the account. SQLite and uploaded files are kept under `data/`, outside Git. See [storage and API instructions](server/README.md).

**Recherche** contains the AI bot with case selection, German/English output, six work modes and adoption of an answer as an editable draft. It uses selected account-owned case particulars, bounded chat history, explicitly selected transcription-reviewed PDF/DOCX excerpts and selected or automatically found public legal passages. Filenames alone do not provide file contents. Responses, exact supplied passages, generation IDs, model, token counts and failures are persisted per case. Only one local generation runs at a time.

The new source finder imports 23 federal-law collections from Gesetze im Internet and the published federal decision index from Rechtsprechung im Internet. Search runs locally; only public source identifiers are used for provider downloads. Topic search includes downloaded decision texts, while case-reference search covers the published index. Refresh progress, collection timestamps and failures are visible. Case snapshots and per-answer passages remain unchanged after later refreshes or review changes. Citation IDs link to their originals; unknown or missing IDs are flagged. These technical checks do not verify the legal proposition or applicable historical version. Draft adoption carries the source ledger into the editable text and PDF. See the [implementation plan](docs/legal-research-plan.md) and [coverage/API details](server/README.md#public-legal-source-catalogue).

The project-specific [German-law skill set](.agents/skills/schimmelpilz-german-law/SKILL.md) covers intake, legislation/decisions, jurisdiction, costs, drafting and deadlines. It adapts selected public workflows from [AI-Skills-German-Law](https://github.com/borghei/AI-Skills-German-Law), with provenance and licence in the package. The development-chat Google Drive connector was searched for the named package/project and returned no matching files; no private Drive documents were copied. Website Drive sign-in/ingestion is not implemented.

After registration, the public introduction gives way to a separate workspace with a sidebar, case list, search, document/draft views, manually recorded deadlines and research sources. Registration collects account type and contact details. Consumers and businesses can reuse their profile in case intake; law firms enter client particulars separately.

Company registration includes company name, legal form, user role, representative and registry/VAT details. Law-firm registration includes firm name, role, responsible lawyer, bar association, admission country and practice areas. Optional organisation details are self-declared; they do not verify a licence or grant shared-staff access.

Companies and firms can upload blank PDF, DOC or DOCX letter paper immediately after registration; all accounts can add it later in their profile. Word conversion runs locally through LibreOffice. Preview and confirm the converted paper and writing margins before activation. PDF output preserves the confirmed background at its original size on first and continuation pages. Every new draft stores its letterhead version; existing drafts retain theirs unless explicitly updated. The editor provides PDF preview/download as well as plain-text download. Word font fidelity must be checked in the preview; editable DOCX export remains planned. See [letter-paper setup and API](server/README.md#registration-and-letter-paper).

Case intake supports a new sequential reference or an unchanged existing reference, separate court/opponent references, parties, jurisdiction, legal area, objectives, procedural stage, dates and value/fee details. The draft editor supplies German/English correspondence, civil-claim, application, objection and response templates for courts, authorities, law firms and other recipients. Missing information stays visible as placeholders; automatic filing is not implemented.

The feature catalogue links to federal/EU legislation, judgments and orders, fee statutes and justice directories. Automatic legal, cost and jurisdiction checks are clearly labelled as planned. Register the owner's first account locally: existing pre-account prototype files become its property. Database contents, uploaded files and credentials are excluded from GitHub.

## One-server architecture

Use one Linux server in the location selected by the owner. Run four services through Docker Compose:

| Service | Responsibility |
| --- | --- |
| Frontend | React interface, login, cases, uploads, research chat and draft editor |
| API | FastAPI authentication, ownership checks, SQLite, private uploads and local model requests |
| Ollama | Run the chosen English/German model locally; disable cloud features |
| Caddy | HTTPS and routing to the web application |

The implemented application uses React/Vite and Python/FastAPI. Keep the database in SQLite and uploads in private local directories. Run a single API worker: a process lock serialises local generation and SQLite records pending/completed/failed requests. A durable background queue and OCR are future work. No separate database server, Redis, hosted vector database or external AI API is needed.

Only Caddy exposes public web ports. The application and Ollama communicate over an internal Docker network. The browser never calls Ollama directly. Pin dependency and container versions when implementation starts.

Case storage, AI inference and draft preparation happen on this server; OCR is not implemented. Optional off-server backups are operator-managed and must be treated as a separate data flow. GitHub holds source code and documentation; runtime data stays outside Git.

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

The repository includes Dockerfiles, `compose.yaml`, `Caddyfile`, `.env.example`, version-locked API dependencies, cookie authentication and additive storage migrations. First-admin/invitation workflows and backup/restore automation remain future milestones. Native Shadow PC development runs the API and Vite without Docker.

For a local production-shaped run:

```bash
cp .env.example .env
# Set DOMAIN to the hostname that points to this server.
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:7b
```

The public web service is exposed through Caddy. The API and SQLite data remain on the internal network and persistent `app_data` volume; downloaded models use `ollama_models`. Set `OLLAMA_MODEL` in `.env` and pull that same model when changing it. The supplied Compose configuration uses CPU inference unless the operator adds GPU support; Docker deployment has not been tested on Shadow.

### Shadow PC development

Shadow PC does not provide the nested virtualization that Docker Desktop needs. Develop the application directly on Shadow instead:

```powershell
# Terminal 1: API
python -m uvicorn server.app:app --reload --port 8001

# Terminal 2: landing page
cd landing
pnpm dev

# Terminal 3, after installing Ollama from its official Windows distribution:
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama serve
# Pull once in another terminal: ollama pull qwen2.5:7b
```

Use Docker on the eventual Linux server, where Caddy, the landing page and the API can run together. Do not try to enable Hyper-V or WSL2 inside Shadow to work around this platform limitation.

This workspace has the official portable Ollama 0.35.1 distribution under ignored `data/ollama-v0.35.1/`, with `qwen2.5:7b` downloaded under `data/models`. These runtime files are not on GitHub. Configure `OLLAMA_MODELS` to that directory when restarting the portable runtime. API defaults: `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen2.5:7b`; no external AI key is required. Model quality must be evaluated for the intended legal work.

The installed native services can be started together with `./start-local.ps1` from the repository root. The launcher reuses running services and existing data; it does not install dependencies. Research chat calls the real local model and retains case-specific conversation and supplied document/legal-source passages. The native browser tests use separate synthetic preview data. OCR and automated substantive legal approval remain pending. See [API documentation](server/README.md) for extraction/context limits and endpoint details.

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
