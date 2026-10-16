# Administration, teams and subscriptions

## Operator access

A system administrator is an explicit database role; registration never grants it. Create a dedicated local account with `python -m server.bootstrap_admin --data-dir data` (or `data/desk-preview` for the isolated preview). Docker: run the same module inside the API container with `--data-dir /data`. The tool generates a random password, stores it in the private data directory's `admin-access.json`, does not print it, does not reset an existing account and does not claim legacy case records. Keep this file private and outside Git. The first non-admin registration retains the existing legacy-case adoption behavior.

After ordinary sign-in, **Administration** offers account counts, user disable/re-enable, operator role changes, session revocation, subscription state/pilot controls and the latest 100 audited actions. An administrator cannot disable or demote themselves; at least one active administrator must remain. Operator settings can pause new registrations and new AI questions without deleting saved cases, answers or files. The model, OCR readiness and public catalogue are shown, with a catalogue-refresh action.

The workspace selector lets operators explicitly open an account's workspace. This is broad access to private case contents and should only be assigned to trusted operators. Switches and successful authenticated writes record the actual actor, workspace, action/path and date. Draft version/review actors retain the actual member/operator identity. Audit entries are application records, not an external tamper-proof logging service. User/role actions require reasons and optimistic versions. Disabling an account revokes its sessions and denies further sign-ins.

## Team access

Each person has a separate login. Owners/operators create a single-use, email-bound invitation valid for 48 hours; only its hash is stored. Deliver the displayed code securely to the named recipient. The application does not send invitation email or verify mailbox ownership; possession of the confidential token and a matching registered account is required. Invite acceptance is transactional and replay is rejected.

Roles: **viewer** permits reads/downloads; **editor** permits case work. Grants are either an explicit case list or all owner cases, inbox and contacts. Case-scoped users cannot create cases or open the global inbox/address book, and their case list, costs and calendar exports are filtered/guarded. Module requests are checked server-side, including direct file/ZIP URLs; hidden buttons are not the security boundary. Scoped users use the relevant case rather than the global cost list. Profile, credentials, billing and letter-paper administration remain personal/owner operations. Existing case ownership is not rewritten.

Member edits use expected versions. Revocation/scope changes apply on the next request and invalidate outstanding invitations for that recipient. Already running jobs/downloads cannot be recalled; copied/downloaded information cannot be recovered. Returning to one's personal workspace remains possible after revocation. Administrators are a separate, broader system role, not an invitation role.

## Seven-day trial and paid subscriptions

Prices: personal EUR 9.90, business EUR 29.90, firm EUR 49.90 per owner workspace/month. Existing pilot access remains free; registration creates no paid agreement. The account's **Abonnement** panel explicitly starts a single seven-day local trial without a card or automatic paid conversion. After expiry, reading/downloads remain available and writes require active entitlement. Paid checkout is blocked during the local trial to prevent early charges. Pilot access can be granted/withdrawn by an operator with a reason; Stripe-managed subscriptions cannot be overridden by that control. System operators retain administration access.

Paid checkout and billing/cancellation are hosted by Stripe. The server validates the configured Price against EUR, the advertised amount, monthly recurrence and inclusive tax behavior before opening checkout. Checkout requires explicit cost/data-transfer acknowledgement. Returning from Checkout never grants access: a signed subscription webhook fetches authoritative current subscription state, validates its server-created order/customer/price and persists it. Duplicate event IDs are ignored; delayed event payloads cannot themselves restore old state. Expired periods, cancellation, unpaid and past-due states restrict writes. A scheduled period-end cancellation retains access through the confirmed period. Customer Portal provides payment methods, invoices and cancellation; configure it to permit the required operations. A canceled subscription can use a new checkout, without a second local trial.

### Stripe operator setup — still required for actual payments

Set these server-side environment variables or the root private `.env` (allowlisted loading without shell evaluation; environment values take precedence). Compose forwards them to the API. Never put them in the frontend or Git.

- `PUBLIC_APP_URL`: the real HTTPS application origin.
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`: matching test or live merchant credentials.
- `STRIPE_PRICE_PERSONAL`, `STRIPE_PRICE_BUSINESS`, `STRIPE_PRICE_FIRM`: EUR monthly Price IDs, inclusive tax behavior, amounts 990 / 2990 / 4990 cents.

Configure an HTTPS webhook at `/api/billing/webhook` for `customer.subscription.created`, `.updated`, `.deleted` and enable Customer Portal. This one endpoint is exempt from the browser custom-header requirement because it verifies Stripe's raw-body HMAC signature with a five-minute timestamp tolerance. Other write endpoints retain the custom-header guard. No merchant account, prices, payment method, domain or live charge was created by the implementation.

Provider code follows [Checkout Sessions](https://docs.stripe.com/api/checkout/sessions/create), [signed webhook guidance](https://docs.stripe.com/events/manage-webhook-endpoints), [Subscriptions](https://docs.stripe.com/api/subscriptions) and [Customer Portal](https://docs.stripe.com/api/customer_portal/sessions/create), checked 2026-10-15. API version is pinned to `2025-03-31.basil`; current-period fields support item-level period dates.

Validation distinguishes local/API tests and mocked provider responses from a real Stripe sandbox purchase. The latter requires operator credentials and a reachable HTTPS webhook and has not been performed. Configure merchant details, taxes, customer terms, cancellation behavior and production monitoring before accepting payments. Missing credentials keep checkout disabled; there is no fake successful payment path.
