# Production go-live

This is the operator runbook for the one-server Docker installation. The code side is prepared; the items marked **Operator** need accounts, credentials or decisions that cannot be made in the repository.

## What the installation does by itself

| Area | Provided |
| --- | --- |
| HTTPS | Caddy obtains and renews certificates for `DOMAIN`; HSTS, a strict Content-Security-Policy (no inline scripts, no third-party hosts) and other security headers are set in `Caddyfile`. Request bodies are capped at 220 MB. |
| Supervision | Every long-running service has `restart: unless-stopped` and a health check. Caddy starts only when the web front end and the API report healthy. Enable the Docker service at boot (`systemctl enable docker`) so the stack returns after a reboot. |
| AI model | Research chat calls the Gemini API (`GEMINI_API_KEY`, `GEMINI_MODEL`). The question, case particulars, selected document excerpts and found legal passages are sent to Google with each research question; nothing else is. Use a paid (billing-enabled) key so Google does not use prompts for training. Without a key, or with a model name Google does not know, research reports "not ready" and the office functions keep working; the admin panel shows the model in use. |
| OCR | German/English OCR models are built into the API image (`server/Dockerfile`). |
| Backups | The `backup` service creates an encrypted backup every day at `BACKUP_HOUR_UTC`, verifies it by decrypting and checking every file, and logs one JSON line per run (`docker compose logs backup`). The key is created once in the `backup_keys` volume and is never replaced while backups exist. No backup is deleted unless `BACKUP_KEEP_DAYS` is set; the newest is always kept. |
| Payments | Reusable Clip payment links, one per plan, prepaid one month at a time. An administrator records each payment seen in the Clip dashboard, which unlocks the paid months; no automatic renewal. Expired access keeps reading and export. Details: [admin-team-billing.md](admin-team-billing.md). |
| Legal pages | Impressum, privacy notice and terms at `/#impressum`, `/#datenschutz`, `/#agb`, linked from the footer, registration and workspace sidebar. Operator particulars come from `OPERATOR_*` in `.env`; missing required values are shown as missing on the page. |
| Tests | `.github/workflows/ci.yml` runs the server tests, the front-end build and tests, and validates `compose.yaml` on every pull request. |

## Go-live steps

1. **Operator – server and domain.** Linux host with Docker Engine and the Compose plugin; 2 vCPU / 4 GB RAM / 50 GB disk is enough because the AI model runs at Google (OCR and LibreOffice conversion run locally). Point the domain's A/AAAA record to the host and open only ports 80 and 443.
2. **Operator – configuration.** `cp .env.example .env`, then set `DOMAIN`, `PUBLIC_APP_URL=https://<domain>`, `GEMINI_API_KEY`, the `OPERATOR_*` particulars for the Impressum and privacy notice, the SMTP values and, when payments start, the price and Clip link values (below). Keep `.env` out of Git (already ignored).
3. **Start.** `docker compose up -d --build`. Watch `docker compose ps` until all services are `healthy`.
4. **First administrator.** `docker compose exec api python -m server.bootstrap_admin --data-dir /data --email <your-admin-email>`; read the generated password once with `docker compose exec api cat /data/admin-access.json`, sign in, enable two-factor sign-in (required for operator functions), then delete the file: `docker compose exec api rm /data/admin-access.json`.
5. **Operator – Clip.** In the Clip dashboard create one reusable payment link per plan for one month's amount and ask for the payer's email. Put the links in `CLIP_LINK_PERSONAL` / `_BUSINESS` / `_FIRM` and the same amounts and currency in `PRICE_*` / `PRICE_CURRENCY`. Make one real low-value test payment, then record it under Administration → Abonnements & Zahlungen and check that the account becomes active. Check the Clip dashboard regularly (at least daily) and record new payments; users see their pending payment until then.
6. **Operator – email.** Set `SMTP_*`; send yourself a password reset to confirm delivery. Configure SPF/DKIM for the sender domain.
7. **Operator – off-site backup.** Copy `BACKUP_PATH` **and** the key (`docker run --rm -v <project>_backup_keys:/k alpine cat /k/master.key`) to a second location, kept apart from each other. Rehearse a restore as described in [backup-restore.md](backup-restore.md) before real data arrives.
8. **Operator – legal and privacy.** Before charging or onboarding consumers: have the supplied Impressum, privacy notice and terms (`landing/src/LegalPages.jsx`) reviewed and adapted by a qualified lawyer, sign Google's data-processing terms for the Gemini API, prepare a data-processing agreement for law-firm customers, and a review by a qualified lawyer of whether the consumer research assistant falls under the Rechtsdienstleistungsgesetz. Hosting country is part of that review.
9. **Smoke test on the live domain.** Register, create a case, upload and review a PDF, ask the research assistant, save and export a draft as PDF/Word, add a deadline and import the calendar file, run `docker compose exec backup python -m server.backup_scheduler --once`.

## Updating

`git pull && docker compose up -d --build`. Database migrations are additive and run at API start. Take a manual backup first (`docker compose exec backup python -m server.backup_scheduler --once`).

## Not provided

No electronic court filing (beA/EGVP), no automatic legal approval, no external uptime alerting: connect an external monitor (any HTTPS check on `https://<domain>/api/health`) if you need notifications.
