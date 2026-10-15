# Correcting an incoming-file assignment

Under **Posteingang → Zugeordnet**, choose **Zuordnung berichtigen**, explicitly select another owned case, and enter a reason (10–1,000 characters). Saving checks the current version, original file size/hash and target ownership in a single transaction. Concurrent edits, unavailable originals and unchanged target cases are rejected.

The old case retains its original document record, transcription, OCR metadata and existing research/draft snapshots. It is marked as a previous assignment with the correction reason; its passages are excluded from new research. Historical research answers stay readable, but cannot be newly adopted as drafts and are excluded from new chatbot conversation context. Existing drafts and self-declared approvals are retained; the old case displays a notice to recheck them before use. The system does not silently rewrite historical answers or claim that earlier legal work is still valid.

The target receives a new document association using the same original bytes, without copying transcription approval. Extract/review text there before using it as a source. No file is deleted or moved. Returning to an earlier case uses another correction with a new association and reason; this preserves the full history rather than undoing the audit trail. Previous copies remain visible in the earlier case as records, so this feature is not a confidentiality purge.

Endpoint: `POST /api/inbox/{id}/correct` with `case_id`, `expected_version`, `reason`. Inbox records include a chronological correction history with references, reasons and dates. Both affected case histories record the action; related case ZIPs include correction records. This is same-account correction only, not cross-account transfer or shared-firm access.

Validated with synthetic data: UI assignment/correction/history; original bytes and historical source snapshots preserved; fresh target unreviewed; correction back; owner/version/unchanged-target/reason/hash guards; transaction rollback; exclusion from new research context and draft adoption.
