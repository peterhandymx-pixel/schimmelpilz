"""Daily encrypted backups for the Docker installation: create, verify, keep; never overwrite or delete silently."""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .backup import BackupError, create, init_key, verify


def run_once(data, destination, key, revision):
    if not (data / 'app.db').exists():
        raise BackupError('Source database missing; start the application first.')
    destination.mkdir(parents=True, exist_ok=True)
    if not key.exists():
        # A missing key next to existing backups needs recovery, never silent replacement.
        if any(destination.glob('*.spbackup')):
            raise BackupError('Existing backups found but the key is missing. Recover the original key.')
        init_key(key)
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    archive = destination / f'schimmelpilz-{stamp}.spbackup'
    created = create(data, archive, key, revision)
    workspace = destination / 'verification'
    try:
        checked = verify(archive, key, workspace)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    return {'backup': archive.name, 'created': created, 'verified': checked}


def prune(destination, keep_days):
    """Optional retention: only removes verified-format archives older than keep_days; 0 keeps everything."""
    if keep_days <= 0:
        return []
    cutoff = time.time() - keep_days * 86400
    archives = sorted(destination.glob('schimmelpilz-*.spbackup'))
    removed = []
    for archive in archives[:-1]:  # the newest backup is always kept
        if archive.stat().st_mtime < cutoff:
            archive.unlink()
            removed.append(archive.name)
    return removed


def seconds_until(hour):
    now = datetime.now(UTC)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('DATA_DIR', '/data')))
    parser.add_argument('--destination', type=Path, default=Path(os.getenv('BACKUP_DIR', '/backups')))
    parser.add_argument('--key-file', type=Path, default=Path(os.getenv('BACKUP_KEY_FILE', '/backup-keys/master.key')))
    parser.add_argument('--hour', type=int, default=int(os.getenv('BACKUP_HOUR_UTC', '2')))
    parser.add_argument('--keep-days', type=int, default=int(os.getenv('BACKUP_KEEP_DAYS', '0')))
    parser.add_argument('--once', action='store_true', help='Run one backup now and exit.')
    args = parser.parse_args()
    revision = os.getenv('APP_REVISION', 'unknown')
    while True:
        if not args.once:
            time.sleep(seconds_until(args.hour))
        try:
            result = run_once(args.data_dir, args.destination, args.key_file, revision)
            result['pruned'] = prune(args.destination, args.keep_days)
            print(json.dumps({'at': datetime.now(UTC).isoformat(), 'ok': True, **result}), flush=True)
        except (BackupError, OSError, sqlite3.Error, zipfile.BadZipFile, ValueError) as error:
            print(json.dumps({'at': datetime.now(UTC).isoformat(), 'ok': False, 'error': str(error) or 'Backup failed'}), flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(60)  # never run twice within the same scheduled hour


if __name__ == '__main__':
    sys.exit(main())
