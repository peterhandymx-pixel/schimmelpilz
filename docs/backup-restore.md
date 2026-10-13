# Encrypted backup and restore

Implemented 2026-10-12 for the local one-server installation. This is an operator tool, not a global-data download available to ordinary website accounts.

## What is protected

The tool uses SQLite's backup API to produce a consistent database snapshot, then includes exactly the original uploads and letter-paper originals/normalized PDFs referenced by that snapshot. This covers pending inbox files, all saved letter-paper versions, account/password records, case/contact/task data, draft versions/reviews and exact stored research provenance. Uploaded files and confirmed letter paper currently use immutable generated filenames. Any future operation that modifies/deletes these files must coordinate with backup creation or retain immutable versions.

Private keys, runtime logs, loose unreferenced files, model weights and the rebuildable public-source catalogue are excluded. Case-attached legal snapshots and per-answer supplied passages remain in the database. Reinstall dependencies/models and refresh the public catalogue on a replacement host. Host/domain/email/payment configuration is not part of this archive; preserve deployment configuration separately.

Backups use authenticated [Fernet encryption](https://cryptography.io/en/latest/fernet/) from pinned `cryptography`. Each bounded encrypted record contains an archive identifier, sequence number and final marker; decrypt rejects wrong keys, tampering, reordered/substituted records, truncation and appended data. SHA-256, expected byte sizes, database integrity/foreign keys, record counts and exact archive inventory are checked before restore. The v1 archive has a 20 GiB content/archive limit and 100,000-file limit.

The key is generated once at `backups/keys/master.key`. Never replace it: without the matching key, the existing backups cannot be decrypted. Keys and archives are ignored by Git. Backup/private staging directories are restricted to the current Windows user and SYSTEM (0700 directories/0600 files on POSIX). Verification briefly decrypts into that protected local staging area, then removes it. Local account access and whole-disk protection remain operator responsibilities.

## Shadow PC operation

`backup-local.ps1` creates a timestamped encrypted archive and immediately verifies it. A missing key with existing archives causes failure instead of silent replacement. An existing archive is never overwritten.

```powershell
.\backup-local.ps1
.\backup-local.ps1 -DataDirectory data/desk-preview -DestinationDirectory backups/preview
```

Both installations have separate backup destinations; their current local archives have been verified. Scheduled tasks are installed for the current Windows account, using limited permissions, daily at 03:00 in the Windows host's timezone and at Windows sign-in. They run only while that account is signed in; missed runs can start when available. A task already running is not started again. Failures retry up to three times at five-minute intervals, with a 30-minute execution limit. The scheduled environment may not have Git on PATH; backup still succeeds and records an unknown revision.

```powershell
.\install-backup-task.ps1
.\install-backup-task.ps1 -DataDirectory data/desk-preview -DestinationDirectory backups/preview
```

The protected destination holds `last-run.json` and `last-run.log`; the Windows task result must be zero and `success` true. A schedule alone is not proof that a backup was made. Both installed tasks were manually triggered and returned zero after their verified archives were created.

Local copies do not protect against loss/reset of the Shadow PC. A separate encrypted backup destination and a separately protected recovery-key copy are still required for that. No cloud/off-host upload has been configured. Keep all current archives until that copy is verified. Recommended future retention: seven daily, four weekly and twelve monthly recovery points, adjusted to actual storage and retention policy. No automatic backup deletion is enabled; review storage growth and free space.

## Restore without overwriting the installation

Use a **new, nonexistent directory**. The tool refuses an existing destination, even if it appears empty. It authenticates/decrypts, rejects unsafe paths/links/duplicates, verifies all hashes and database references, then publishes the restored files. Any publication failure leaves a partial destination for inspection instead of deleting an operator-selected path. The source installation is never modified by restore.

```powershell
.\.venv\Scripts\python.exe -m server.backup restore --backup backups/local/CHOSEN.spbackup --key-file backups/keys/master.key --destination data/recovered-new
.\.venv\Scripts\python.exe -m server.backup status --data-dir data/recovered-new
```

Restore revokes all saved login sessions. Users sign in again with their existing password; case files and password hashes are preserved. Test the restored installation on separate ports before switching production to it. Do not point two independent application installations at the restored directory during validation. Check the archive's recorded application revision and rehearse any needed additive migration before deployment.

Standalone verification and storage health checks:

```powershell
.\.venv\Scripts\python.exe -m server.backup verify --backup backups/local/CHOSEN.spbackup --key-file backups/keys/master.key --workspace backups/local/verification
.\.venv\Scripts\python.exe -m server.backup status --data-dir data
```

These commands report counts and health, never key values or case contents. The API has no backup/restore route: a user's normal account cannot download every account's data or overwrite the server through the website.

## Verification completed

- Four new backup tests: restore/login/session revocation; original files, draft versions, letter-paper PDF export and exact research provenance; missing originals and non-overwrite safety; invalid keys, tampering/truncation/reorder/replay; authenticated unsafe archive paths.
- Full backend suite: 40 tests passed.
- Actual encrypted archives created and verified for `data` and `data/desk-preview`.
- Preview archive restored to a unique isolated `data/restore-checks` directory; database, all ten referenced files and record counts passed storage checks.
- Both installed scheduled tasks executed successfully with verified archives and zero exit codes. Existing runtime data and earlier backups were retained.
