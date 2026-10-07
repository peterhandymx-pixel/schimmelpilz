# Draft review and account-holder approval

The signed-in draft editor preserves immutable content versions and an append-only review history. This is a manual working-paper review workflow. It does not automatically determine legal truth, verify admission to practise, grant staff roles or file a document.

1. Save the text, recipient (or identify internal use), language, document type and chosen letterhead.
2. Begin review of this version. Check facts/evidence, applicable source versions/proposition support, counterarguments/adverse authority and jurisdiction/form/deadlines/recipient/signature.
3. Review every text block and save a note of at least 10 characters for each checked item. Original supplied legal passages appear alongside blocks containing matching citation IDs. Blocks without linked passages remain explicitly flagged for manual factual/source review. Reviewed document extracts appear in the facts checklist. Neither a linked ID nor a checked box proves substantive support.
4. Resolve blocking particulars: missing recipient, bracketed placeholders and citation IDs absent from the saved original source context. Even completed review notes cannot override these blocks. The editable source appendix is not treated as source authority.
5. Confirm your own review and save a final approval note of at least 20 characters. Approval captures account ID/name, timestamp, version, immutable snapshot hash and all current review notes. It is labelled as the account holder's own review.

Editing actual text, recipient, language, type or selected letter-paper ID/layout creates a new content version, resets current approval and gives the new version an empty checklist. A save with unchanged values keeps the version and review state. Reopening an approved version clears current approval but retains previous evidence; same-version checklist entries remain available to revisit.

Research adoption accepts only a completed run belonging to the same account-owned case. The server snapshots legal and document passages, citation audit, retrieval report, question/answer and model metadata. Later research/source changes do not modify that context. Legacy drafts receive a snapshot of their existing version; no earlier versions or trusted sources are fabricated from their text.

Browser saves send `expected_version`. Review writes require both `expected_version` and `expected_review_revision`; conflicting concurrent writes return 409 without overwriting the saved state. Older API clients may omit the version on ordinary draft updates for compatibility, but still create a new version and reset approval when editing. All history and source endpoints enforce existing account/case ownership.

Saved PDF export uses the stored body and briefpaper version, returning current version/review headers and a version/status filename. It remains possible to export an unapproved draft, explicitly labelled by its filename. No legal approval stamp or signature is added to the document. Editor PDF preview exports unsaved text separately and does not establish approval. Historical versions can be read in the editor; historical PDF rendering is not implemented.

Tests cover source snapshot ownership, non-authoritative editable appendices, approval evidence, restart/backfill, edit reset, unchanged saves, metadata/letter-paper changes, blockers, concurrent review revisions, stale content/version writes and saved PDF headers.
