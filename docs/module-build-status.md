# Automatic module build

Updated 2026-10-15. User requests automatic implementation of all missing modules, prioritizing usable legal work. Continue this checklist in order; mark items complete only after implementation and validation. Existing account recovery/operational extras were previously deferred, but remain listed for a complete system.

| Module | Status | Acceptance |
|---|---|---|
| Case intake, private storage, references | Implemented | Owned cases, retained/generated internal reference, separate court reference |
| Address book and incoming-file assignment | Implemented | Owned contacts/files; transactional assignment and version conflicts |
| Research chatbot and primary-source catalogue | Implemented with bounded coverage | Persistent local-model answers and exact supplied passages; legal conclusions remain unverified |
| Drafts, own review and letter-paper PDF | Implemented | Editable drafts, versions, manual review, preserved PDF backgrounds |
| Invoice arithmetic | Implemented | Decimal recalculation, discrepancies, case versions, PDF reports and clarification drafts |
| Editable Word export | Implemented and validated | Text remains editable; saved letter-paper version, first/continuation page images, page size/margins; own-review status cannot imply approval of edited Word files |
| Case archive and data export | Implemented and validated | Reversible archive filter, original files plus structured case records exported privately |
| List and document exports | Implemented and API/browser validated (2026-10-22) | Cases, deadlines/tasks, contacts and inbox as CSV (semicolon, UTF-8 BOM, German number/date format) or Excel; cost-review lines as CSV/Excel; cost reviews, route plans, saved research answers and saved drafts as PDF and Word. Spreadsheet cells never become formulas; case-scoped members export only granted cases and no global lists |
| Deadlines and reminders | Implemented calendar export and validated | Explicit manually entered dates, upcoming/overdue views, downloadable calendar reminders; legal deadline computation separate |
| Jurisdiction and procedural routes | Implemented bounded working papers and validated | Case-linked working paper with supported rules, required facts and formal requirements; no guessed court or filing channel |
| Statutory fee calculator | Implemented basic 2025 value-fee tables and validated | Dated sourced fee table, explicit applicability, bounded fee events and credits, independently checked examples |
| OCR | Implemented and validated; automatic since 2026-10-23 | Local page text generation, resource bounds, transcription review against original before research use; every new upload, app scan and inbox assignment is read automatically (text layer, then OCR for photos and scanned pages) |
| Inbox correction | Implemented and validated | Versioned reversible correction without losing original bytes or silently invalidating document/research snapshots |
| Research quality and broader coverage | Implemented bounded extension | Public-source freshness, retrieval examples, missing/unknown citation handling, clearly stated jurisdiction coverage |
| Shared firm workspace | Implemented and browser/API validated | Membership, staff/case permissions and revocation; account profile alone is not membership |
| System administration | Implemented; local dedicated admin access | Explicit operator role, user/session controls, settings, workspace selection and audit |
| Account self-service and deletion | Implemented and browser/API validated (2026-10-20) | Profile, email and password changes; owner-only deletion of cases, documents, drafts, tasks, contacts, inbox entries and the whole account, with orphaned files removed |
| Account recovery and email verification | Implemented and validated; SMTP credentials required for delivery | Hashed single-use reset links (1 h) and confirmation links (48 h), no address enumeration, rate limits, session revocation on reset |
| Two-factor sign-in | Implemented and validated | TOTP with replay protection and eight single-use recovery codes; mandatory for operator functions (`ADMIN_MFA_REQUIRED`) |
| Statutory deadline calculator | Implemented calculation aid and validated | §§ 187, 188, 193 BGB / § 222 ZPO forward periods, statewide holidays 2015–2035, explanation steps, adoption as task; no backward periods or local holidays |
| Draft email delivery | Implemented and validated; SMTP required | Explicitly confirmed sending of one saved version as PDF/DOCX, reply-to sender, evidence with attachment hash; not formal filing |
| Email inbox import | Implemented and validated against a simulated IMAP server | Owner-configured IMAP, encrypted password, read-only fetch of unread mail, attachment import without automatic assignment, private-network hosts refused |
| Supervised operation | Implemented in Docker Compose and validated locally (2026-10-22) | Health checks, restart policy, ordered start, daily verified encrypted backups; external uptime alerting remains operator setup ([production.md](production.md)) |
| Public-server deployment | Stack validated locally over HTTPS; operator setup required | Host/domain, credentials, off-site backup copy and legal review per [production.md](production.md); no production host configured |
| Subscriptions and seven-day trial | Trial/entitlements and prepaid Clip payment links implemented and API-tested (2026-10-24); Clip links and one real test payment required | Persistent plan/trial, explicit checkout, tested callbacks/cancellation; existing pilot stays free until consent |
| Research AI provider | Gemini API implemented and tested with a mocked transport (2026-10-24); `AI_PROVIDER=ollama` keeps the local model | Key in `.env`; data flow to Google stated in UI and privacy notice |
| Impressum, privacy notice, terms | Implemented (2026-10-24); legal review required | Pages from `OPERATOR_*` configuration, linked from footer, registration and workspace; missing particulars shown as missing |
| Electronic court filing (beA/EGVP) | Not implementable without official access | Requires beA software certificates/access; email delivery above is not formal filing |

External source links are working links, not third-party account integrations. No provider credentials, paid databases or production host are fabricated. Keep local synthetic preview data separate from real accounts and the public Git repository.

Implementation details and tested limits: [office modules](office-modules.md).

Details: [administration, teams and subscriptions](admin-team-billing.md), [extended research](advanced-research.md).
