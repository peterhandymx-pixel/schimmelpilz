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
| Deadlines and reminders | Implemented calendar export and validated | Explicit manually entered dates, upcoming/overdue views, downloadable calendar reminders; legal deadline computation separate |
| Jurisdiction and procedural routes | Implemented bounded working papers and validated | Case-linked working paper with supported rules, required facts and formal requirements; no guessed court or filing channel |
| Statutory fee calculator | Implemented basic 2025 value-fee tables and validated | Dated sourced fee table, explicit applicability, bounded fee events and credits, independently checked examples |
| OCR | Implemented and validated | Local page text generation, resource bounds, transcription review against original before research use |
| Inbox correction | Implemented and validated | Versioned reversible correction without losing original bytes or silently invalidating document/research snapshots |
| Research quality and broader coverage | Queued | Public-source freshness, retrieval examples, missing/unknown citation handling, clearly stated jurisdiction coverage |
| Shared firm workspace | Queued | Membership, staff/case permissions and revocation; account profile alone is not membership |
| Account recovery and supervised operation | Deferred earlier / queued | Verified email, expiring recovery, session revocation, startup/restart; email credentials required for delivery |
| Public-server deployment | Operator setup required | Host/domain/HTTPS, private runtime networks, measured capacity; no production host configured |
| Subscriptions and seven-day trial | Queued; provider setup required | Persistent plan/trial, explicit checkout, tested callbacks/cancellation; existing pilot stays free until consent |
| Email and electronic filing | Provider/authority integration required | Authenticated provider, permitted channel, preview/review and explicitly authorized sending; ordinary email is not automatically formal filing |

External source links are working links, not third-party account integrations. No provider credentials, paid databases or production host are fabricated. Keep local synthetic preview data separate from real accounts and the public Git repository.

Implementation details and tested limits: [office modules](office-modules.md).
