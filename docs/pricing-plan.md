# Planned launch pricing

Decision, 2026-10-07: offer three audience-specific monthly plans at accessible entry prices. The landing page is bilingual and the buttons open existing registration with the relevant audience selected.

| Plan | Proposed final monthly price | Launch trial | Licence unit |
| --- | --- | --- | --- |
| Personal | €9.90 | 7 days free | One individual account |
| Business | €29.90 | 7 days free | One individual account |
| Law firm | €49.90 | 7 days free | One individual account |

The proposed amounts include applicable taxes. Before paid launch the operator must confirm actual tax/invoicing treatment and commercial terms. There is no annual-payment prerequisite. No unlimited-use promise, additional staff seats, verified legal advice, paid database access or support SLA is offered. Features describe the existing software's relevant workflows; audience selection currently configures profile/intake, not paid access restrictions.

## Basis for the starting prices

Primary provider pricing inspected on 2026-10-07: [Lawlift](https://www.lawlift.com/de/preise) publishes €99 per month for a single document-automation user with AI; [Lawlift terms](https://www.lawlift.com/terms) describe its prices as net unless specified otherwise. This is a broader commercial product, not an equivalent feature/security offering. Our law-firm entry hypothesis is substantially below that benchmark; personal and business entry prices reflect lighter expected individual use. These are proposed commercial choices, not evidence that the server can profitably serve unlimited accounts.

Validate willingness to pay, GPU inference time, document-storage use and support costs during the free pilot before enabling billing. Do not silently reserve arbitrary usage allowances or claim plan exclusivity for functionality currently available to all accounts.

## Current boundary

Only the price overview and registration routing are implemented. The current pilot remains free. The seven-day trial is a launch offer, not an enforced countdown today. There is no payment provider, subscription record, tariff entitlement, trial expiry or automatic charge. Both the price section and registration state this explicitly.

For a paid launch implement persistent plan/trial state, seven-day start/end timestamps, disclosed terms, an explicit customer subscription decision, payment-provider callbacks with idempotency, invoices, cancellation and account access after trial expiry. Keep trial limits and actual plan entitlements consistent across the website and API. Never start paid billing solely from the existing account registration button.
