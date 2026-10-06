# Source-backed research implementation

Requested 2026-10-06. Keep the existing single-server, local-model architecture.

1. Import structured federal legislation from Gesetze im Internet and the decision index from Rechtsprechung im Internet. Index public material locally; never send a case question or document to an external search service. Import a bounded selection of recent decisions for topic search and fetch indexed decisions on demand by their public identifier.
2. Add a bilingual source finder to Recherche: legislation/topic search, court-reference search, original links, statutory version notes, court/date/type/ECLI where supplied, exact passages, retrieval times and hashes. Show catalogue coverage, refresh progress and failures. Preserve a usable prior catalogue when a refresh fails.
3. Attach immutable source snapshots to the selected case. Record the user's version/relevance review separately from technical retrieval. Exclusion is reversible. Enforce account and case ownership on every attachment/review/request.
4. Give the local model bounded source passages with [L1] citation identifiers. Check returned identifiers against the supplied passages; flag missing or unknown references. Retrieval and identifier checks do not prove legal correctness. Save the exact passages and review state with each generation.
5. Carry that source ledger into editable drafts and existing letterhead PDF exports. Verify adapters, isolation, failed retrieval, historical provenance, citations and the complete native browser flow with synthetic cases. Build, run the existing tests and push source code only to GitHub.

Scope: current consolidated German federal texts and the published federal decision index, with only downloaded decisions available for topic/full-text search. No assertion of exhaustive coverage, historical-version applicability, legal approval, automatic fees/deadlines or electronic filing. EUR-Lex, state repositories and proprietary databases need separate adapters.

Acceptance: a question can retrieve actual imported statutory/decision passages, show traceable citations, survive reloads and create a PDF draft retaining the source ledger. An unavailable, stale or missing source must never become a fabricated verified result.

Provider references: [GII download documentation](https://www.gesetze-im-internet.de/hinweise.html), [GII index](https://www.gesetze-im-internet.de/gii-toc.xml), [RII index](https://www.rechtsprechung-im-internet.de/rii-toc.xml).

## Implementation and validation — 2026-10-06

All five implementation steps are complete locally. The successful native refresh contains 8,515 provisions across the 23 collections, 84,448 published decision index entries and 57 downloaded decision texts (56 recent seeds plus an on-demand decision). Counts describe this import, not exhaustive legal coverage. Refresh completed with no failed collections. A browser-discovered write-lock problem was corrected with rowid-based FTS maintenance, a preserved-content index migration and write reservation before reads; concurrent-write and migration regressions pass.

Validation: 23 Python API tests, six Node tests (hosting and draft-ledger provenance), and the production frontend build passed. In the separate synthetic preview account, the browser retained an existing test reference, found § 535 BGB and BGH VIII ZR 109/18, attached original passages, saved a review note, ran the actual local qwen2.5:7b model, and adopted its answer into a saved draft. Automatic local retrieval was exercised alongside explicit source selection. Returned [L3]/[L4] identifiers link to the supplied § 535 passages, and saved history survives reload. An earlier model answer without identifiers was visibly flagged rather than treated as a verified answer.

The PDF endpoint exported a five-page draft with the stored first/continuation letter paper. Every supplied URL and excerpt hash was recovered from the PDF, exact excerpts were retained in the saved draft, and all five rendered pages were inspected. The test uses synthetic data; real accounts and files were preserved. Docker configuration includes persistent catalogue storage, but Docker deployment on a Linux host was not executed on Shadow PC.

Remaining boundaries: source/citation checks are technical; they do not verify semantic support, adverse authority or the applicable historical version. User review remains self-declared. Topic search covers downloaded decisions, not the whole index. Extracts are bounded and can omit statutory footnotes or other reasoning. No scheduled refresh, EU/state/Mexico adapter, automated fee/deadline/jurisdiction calculation or filing was added.
