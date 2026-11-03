# Account, mail and deadline functions

Added 2026-10-20. All functions are tested in `server/tests/test_account.py`, `test_deletion.py`, `test_deadlines.py`, `test_send.py` and `test_mailbox.py`.

## Operator configuration (`.env`)

| Setting | Purpose |
| --- | --- |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SECURITY` (`starttls`, `ssl`, `none`) | Outgoing mail for password reset, address confirmation and sending drafts. Nothing is sent until `SMTP_HOST` and `SMTP_FROM` are set. |
| `PUBLIC_APP_URL` | Base address used in reset and confirmation links. Required in production; without it only `localhost` origins are used for links. |
| `MAIL_OUTBOX_DIR` | Local testing only: write every message as an `.eml` file instead of sending it. |
| `ADMIN_MFA_REQUIRED` (default `true`) | Operator functions need an administrator with two-factor sign-in. Set `false` only for local development. |
| `MAILBOX_ALLOW_PRIVATE_HOSTS` (default off) | Allow IMAP servers on private/loopback addresses, e.g. a mail server inside the same network. |

## Self-service account

- **Profile:** name, organisation, address, phone and organisation details are editable. Account type and email confirmation status are not.
- **Email change:** requires the current password, clears confirmation and sends a new confirmation link.
- **Password change:** requires the current password; all other sessions are signed out.
- **Password reset:** "Passwort vergessen?" appears on the sign-in form when mail is configured. Links are single-use, valid one hour, stored only as hashes. The answer is identical for unknown addresses. Limits: 3 requests per address and 10 per client address per hour. A reset signs out every session.
- **Email confirmation:** sent on registration and email change (48 h). Unconfirmed accounts keep working; the profile shows a reminder.
- **Two-factor sign-in:** TOTP (RFC 6238) for any authenticator app. Enabling shows eight single-use recovery codes once. A code cannot be reused within its time window. Administrators cannot disable it while `ADMIN_MFA_REQUIRED` is on.

## Deletion

Deletion is permanent and owner-only (team editors and viewers cannot delete). It remains available after a trial or subscription ends.

| What | Confirmation | Effect |
| --- | --- | --- |
| Case | Type the case reference | Removes documents and their text/OCR, drafts with versions and review history, tasks, research, legal snapshots, cost reviews, procedural working papers, contact links and activity. Removes the case from team grants. Inbox originals return to the Posteingang. |
| Document | Confirmation dialog | Removes the record and extracted text. An inbox original stays in the inbox and becomes unassigned. Cost reviews keep their figures but lose the link. |
| Draft | Confirmation dialog, current version | Removes all versions and review history. |
| Task, contact | Confirmation dialog (contacts: current version) | Drafts keep their copied address. |
| Inbox entry | Only when unassigned | Removes the original file. |
| Account | Password, the word LÖSCHEN/DELETE, two-factor code if enabled | Removes all cases, inbox, contacts, letter paper, team memberships and invitations, subscription records and the user's own audit entries. Blocked for the last active administrator and while a paid subscription is still running. |

Files are removed from disk only when no remaining record references them. Historical research answers that quoted a deleted document stay in the case history until the case itself is deleted. Encrypted backups made earlier still contain the data until they are rotated.

## Fristenrechner (deadline calculator)

Calculation aid for forward periods in days, weeks, months or years:

- Start under § 187 Abs. 1 BGB (event during the day) or Abs. 2 (beginning of a day counts).
- End under § 188 Abs. 1–3 BGB.
- Optional shift from Saturday, Sunday or a statewide public holiday to the next working day (§ 193 BGB, § 222 Abs. 2 ZPO).

Holidays are statewide for the 16 Länder, 2015–2035, including year-dependent ones (e.g. Reformationstag in HB/HH/NI/SH from 2018, Frauentag in Berlin from 2019 and Mecklenburg-Vorpommern from 2023). The result shows every step and can be saved as a high-priority task.

**Not covered:** periods counted backwards, hour periods, local-only holidays, court closures, service fictions (e.g. § 122 AO, § 41 VwVfG), and the choice of the applicable period. Always check the result yourself.

## Sending drafts by email

A saved draft version can be sent as PDF (with letter paper) or editable Word to exactly one address, after an explicit confirmation. Replies go to the sender's own address. The review history records recipient, subject, attachment name, SHA-256 of the attachment, message ID and the review status at the time. The case activity log notes the delivery. Unsaved changes are never sent. Limit: 20 messages per person per hour.

Email is not formal filing with a court (beA/EGVP) and does not meet requirements for a specific form of submission. **beA filing is not implemented**: it needs official beA access and software certificates.

## Email inbox import

The workspace owner can store one IMAP mailbox (SSL on port 993 or STARTTLS on port 143) under Posteingang → "E-Mail-Postfach abrufen":

- The password is encrypted with `DATA_DIR/mailbox.key`. Backups exclude keys, so re-enter the password after a restore.
- "Jetzt abrufen" reads up to 25 unread messages read-only; messages stay unread and are never moved or deleted.
- Permitted attachments (≤ 10 MB) become unassigned inbox entries with subject, sender and date. Each message is imported once.
- Hosts on private, loopback or link-local addresses are refused unless explicitly allowed.
- Nothing is assigned to a case automatically.
