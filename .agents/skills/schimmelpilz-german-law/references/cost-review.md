# Fees and invoice review

Classify the document first: lawyer's statutory fee note, fee agreement/hourly bill, court cost demand, consumer/business invoice or operating-cost statement. Do not apply RVG to an ordinary commercial invoice or assume that all invoice types share objection routes and dates.

Extract issuer, date, matter, service period, asserted value, line items, rates, quantity, expenses, tax, advances, credits and total. Record page/line for each input. Obtain a fee agreement, value decision, procedural history and service evidence where needed. Missing facts remain open inputs.

For lawyer fees inspect the applicable dated [RVG](https://www.gesetze-im-internet.de/rvg/), its schedules and transition provisions; separate legal value/rate judgments from arithmetic. For court charges inspect [GKG](https://www.gesetze-im-internet.de/gkg_2004/), [FamGKG](https://www.gesetze-im-internet.de/famgkg/) or another applicable statute. Verify the table version, charging event, rate, scope of matter, credits and advances. Recompute amounts using decimal arithmetic with an explicit rounding rule; a general language model is not the calculator. The app has a bounded lookup for basic 1.0 RVG/GKG/FamGKG value fees from the 2025 tables, with explicit user-declared applicability. It does not choose the governing version or assess fee events, special/minimum fees, credits or entitlement.

For ordinary invoices compare contract, performed service/delivery, items and evidence. For operating costs examine agreement, period, allocation, expense evidence and applicable tenancy provisions; do not import fee-law rules.

Return a line-item table with billed amount, checked basis, recalculation if supportable, discrepancy, evidence and unresolved valuation issue. Keep arithmetic corrections separate from legal objections. State which documents or current tables prevent a conclusion. Draft any request for clarification without asserting an unsupported refund entitlement.

The app now has a deterministic arithmetic tool (invoice-decimal-v1): manual net unit amount × quantity/multiplier, line-net rounding half-up to cents, tax rounded per rate group and gross advances deducted after tax. It stores account-owned case-linked versions and PDF working papers. This does not choose a statutory table, applicable law, entitlement, VAT rate or legally correct rounding method. Record alternate rounding conventions as unresolved when comparing invoices. The draft clarification letter is editable and never dispatched automatically.
