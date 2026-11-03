# Administration, teams and subscriptions

## Operator access

A system administrator is an explicit database role; registration never grants it. Create a dedicated local account with `python -m server.bootstrap_admin --data-dir data` (or `data/desk-preview` for the isolated preview). Docker: run the same module inside the API container with `--data-dir /data`. The tool generates a random password, stores it in the private data directory's `admin-access.json`, does not print it, does not reset an existing account and does not claim legacy case records. Keep this file private and outside Git. The first non-admin registration retains the existing legacy-case adoption behavior.

To make an existing account the administrator instead, run `python -m server.bootstrap_admin --data-dir data --promote you@example.com`. Set `ADMIN_EMAILS` (comma-separated) to limit operator powers to those addresses: any other account flagged as admin is refused, and the role cannot be granted to anyone else. Operator functions also require two-factor sign-in (`ADMIN_MFA_REQUIRED`, default true).

After ordinary sign-in with two factors, the separate **ADMIN** section in the sidebar offers:

- **Übersicht** – account and subscription counts, sign-ups, revenue per month (real and test payments apart), accounts ending within seven days, latest bookings.
- **Benutzer** – search and filter accounts; per account: edit master data, mark the email as verified, create a one-hour password-reset link (mailed when mail is set up, always shown to the operator), reset two-factor sign-in, revoke sessions, disable/re-enable, withdraw the admin role, delete the account (confirmed with its email; payments stay for bookkeeping), plus its subscription, payments, team links and audit entries.
- **Abrechnungen** – all subscriptions with status filters, CSV export of every payment; per account: extend the trial, change the plan, credit free months (booked as a 0-amount `manual` payment), record Clip payments, end access, and reverse the latest booking (it stays on record as reversed and access is recalculated).
- **Tools & System** – status of AI model, OCR, catalogue, mail, payments, admin allowlist and disk; pause registrations/AI; refresh the public catalogue; send a test mail and read the local mail outbox.
- **Protokoll** – the full audit log with search, action filter and paging.

Every change requires a reason and is written to the audit log. An administrator cannot disable or demote themselves; at least one active administrator must remain. Operator settings can pause new registrations and new AI questions without deleting saved cases, answers or files. The model, OCR readiness and public catalogue are shown, with a catalogue-refresh action.

The workspace selector lets operators explicitly open an account's workspace. This is broad access to private case contents and should only be assigned to trusted operators. Switches and successful authenticated writes record the actual actor, workspace, action/path and date. Draft version/review actors retain the actual member/operator identity. Audit entries are application records, not an external tamper-proof logging service. User/role actions require reasons and optimistic versions. Disabling an account revokes its sessions and denies further sign-ins.

## Team access

Each person has a separate login. Owners/operators create a single-use, email-bound invitation valid for 48 hours; only its hash is stored. Deliver the displayed code securely to the named recipient. The application does not send invitation email or verify mailbox ownership; possession of the confidential token and a matching registered account is required. Invite acceptance is transactional and replay is rejected.

Roles: **viewer** permits reads/downloads; **editor** permits case work. Grants are either an explicit case list or all owner cases, inbox and contacts. Case-scoped users cannot create cases or open the global inbox/address book, and their case list, costs and calendar exports are filtered/guarded. Module requests are checked server-side, including direct file/ZIP URLs; hidden buttons are not the security boundary. Scoped users use the relevant case rather than the global cost list. Profile, credentials, billing and letter-paper administration remain personal/owner operations. Existing case ownership is not rewritten.

Member edits use expected versions. Revocation/scope changes apply on the next request and invalidate outstanding invitations for that recipient. Already running jobs/downloads cannot be recalled; copied/downloaded information cannot be recovered. Returning to one's personal workspace remains possible after revocation. Administrators are a separate, broader system role, not an invitation role.

## Seven-day trial and prepaid monthly access (Clip)

Prices come from the operator's configuration: `PRICE_CURRENCY` and `PRICE_PERSONAL` / `PRICE_BUSINESS` / `PRICE_FIRM` (final monthly amounts including taxes; default EUR 9.90 / 29.90 / 49.90). The public pricing page reads them from `GET /api/public/pricing`, so it always shows what the payment links charge. Existing pilot access remains free; registration creates no paid agreement. The starting plan follows the account type (personal, business or law firm); it only preselects a tariff and charges nothing. The account's **Abonnement** panel explicitly starts a single seven-day local trial without a card or automatic paid conversion. The trial is refused while pilot access is active or after a payment exists. After expiry, reading/downloads/export/deletion remain available and writes require active entitlement. Pilot access can be granted/withdrawn by an operator with a reason (withdrawing it also ends a paid period, as a correction tool). System operators retain administration access.

Payments go through **reusable Clip payment links**, one per plan, each charging one month. Clip's reusable links do not report back which account paid, so payment is prepaid and confirmed by an operator:

1. The user ticks the consent (amount, Clip as payment page, account email as reference, request to start during the withdrawal period) and continues. `POST /api/billing/checkout` records the payment intent (`billing_orders`, audited) and returns the plan's link; the browser opens Clip. Opening the link grants nothing. Pilot accounts are refused (free anyway).
2. The user pays on Clip, entering their account email.
3. An operator checks the Clip dashboard and records the payment under **Administration → Abonnements & Zahlungen** (`POST /api/admin/billing/{user_id}/payments`): plan, 1–12 months, Clip transaction/receipt number, payment date. The amount must equal plan price × months; the Clip reference is unique, so the same payment cannot be counted twice; the subscription version must match.
4. Paid time starts after any running paid period or trial (paying early never shortens access) and lasts whole calendar months. Status becomes `active` until `period_end`.

Nothing renews or charges automatically. Seven days before `period_end` the panel shows a renewal notice; afterwards writes stop. Payment records (`billing_payments`: email snapshot, plan, months, amount, currency, reference, period) are bookkeeping evidence and are kept when an account is deleted. Card and bank data never reach this server.

### Clip operator setup — required for actual payments

Set these in the root private `.env` (allowlisted loading without shell evaluation; environment values take precedence). Compose forwards them to the API. Never put them in the frontend or Git.

- `PRICE_CURRENCY`, `PRICE_PERSONAL`, `PRICE_BUSINESS`, `PRICE_FIRM`: exactly the currency and monthly amounts of your Clip links, e.g. `MXN` and `199.00`.
- `CLIP_LINK_PERSONAL`, `CLIP_LINK_BUSINESS`, `CLIP_LINK_FIRM`: the reusable Clip payment links (HTTPS). A plan without a link cannot be paid for; the panel says so.

In the Clip dashboard, create one reusable link per plan for one month's amount, ask for the payer's email, and set the success redirect to `https://<domain>/` if Clip offers it. Make one real low-value test payment and record it before going live. There is no Clip webhook or API integration: payments are only as current as the operator's confirmation.
