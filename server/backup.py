"""Operator-only encrypted backups. No HTTP route; restore never overwrites data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import struct
import subprocess
import sys
import zipfile
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet, InvalidToken

MAGIC = b'SCHIMMELPILZ-BACKUP-1\n'
CHUNK = 1024 * 1024
MAX_CONTENT = 20 * 1024**3
MAX_FILES = 100_000


class BackupError(ValueError):
    pass


def private_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise BackupError('Private directory cannot be a symbolic link')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'nt':
        identity = subprocess.check_output(['whoami'], text=True).strip()
        subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                        identity + ':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        path.chmod(0o700)
    return path


def init_key(path):
    path = Path(path)
    private_directory(path.parent)
    # Exclusive creation: never replace a key required by existing backups.
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        stream.write(Fernet.generate_key())


def cipher(path):
    try:
        raw = Path(path).read_bytes()
        if len(raw) != 44:
            raise ValueError()
        return Fernet(raw)
    except (OSError, ValueError):
        raise BackupError('Missing or invalid backup key') from None


@contextmanager
def readonly(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=30)
    try:
        yield connection
    finally:
        connection.close()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def integrity(connection):
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise BackupError('Database integrity check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchone():
        raise BackupError('Database contains broken references')


def references(connection):
    """Only immutable files referenced by the database snapshot; exclude keys/logs/models."""
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'users', 'cases', 'documents', 'drafts', 'sessions', 'letterheads'} <= tables:
        raise BackupError('Not an initialized Schimmelpilz database')
    result = {}

    def add(folder, filename, size=None, sha=None):
        if not isinstance(filename, str) or not filename or filename in {'.', '..'} or any(c in filename for c in '/\\:'):
            raise BackupError('Unsafe stored filename in database')
        name = folder + '/' + filename
        existing = result.setdefault(name, {})
        for key, value in (('size', size), ('sha256', sha)):
            if value is not None:
                if key in existing and existing[key] != value:
                    raise BackupError('Conflicting stored file metadata')
                existing[key] = value

    for name, size in connection.execute('SELECT stored_name,size_bytes FROM documents'):
        add('uploads', name, size=size)
    if 'inbox_documents' in tables:
        for name, size, sha in connection.execute('SELECT stored_name,size_bytes,sha256 FROM inbox_documents'):
            add('uploads', name, size=size, sha=sha)
    for original, pdf, sha in connection.execute('SELECT original_stored,pdf_stored,pdf_sha256 FROM letterheads'):
        add('letterheads', original)
        add('letterheads', pdf, sha=sha)
    return result


def safe_file(root, name):
    root = Path(root).resolve()
    target = root / name
    # Reject symlinks/junctions resolving outside the intended root.
    if not target.resolve().is_relative_to(root) or target.is_symlink() or not target.is_file():
        raise BackupError('A required original file is missing or unsafe')
    return target


def check_file(path, expected):
    size, sha = path.stat().st_size, digest(path)
    if expected.get('size', size) != size or expected.get('sha256', sha) != sha:
        raise BackupError('A required file does not match its stored metadata')
    return {'size': size, 'sha256': sha}


def counts(connection):
    names = ('users', 'cases', 'documents', 'drafts', 'contacts', 'inbox_documents', 'letterheads', 'research_runs')
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {name: connection.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in names if name in tables}


def encrypt_archive(source, destination, key):
    fernet = cipher(key)
    identifier = secrets.token_bytes(16)
    with Path(source).open('rb') as incoming, Path(destination).open('xb') as outgoing:
        os.chmod(destination, 0o600)
        outgoing.write(MAGIC + identifier)
        index = 0
        while True:
            chunk = incoming.read(CHUNK)
            # Each authenticated record binds the archive, sequence and final marker.
            payload = identifier + struct.pack('>Q', index) + bytes([not chunk]) + chunk
            token = fernet.encrypt(payload)
            outgoing.write(struct.pack('>I', len(token)) + token)
            if not chunk:
                break
            index += 1
        outgoing.flush()
        os.fsync(outgoing.fileno())


def decrypt_archive(source, destination, key):
    fernet = cipher(key)
    with Path(source).open('rb') as incoming, Path(destination).open('xb') as outgoing:
        os.chmod(destination, 0o600)
        if incoming.read(len(MAGIC)) != MAGIC:
            raise BackupError('Unsupported backup format')
        identifier = incoming.read(16)
        if len(identifier) != 16:
            raise BackupError('Truncated backup')
        index, total = 0, 0
        while True:
            length = incoming.read(4)
            if len(length) != 4:
                raise BackupError('Backup is incomplete')
            size = struct.unpack('>I', length)[0]
            if not 100 <= size <= CHUNK * 2:
                raise BackupError('Invalid encrypted record')
            token = incoming.read(size)
            try:
                payload = fernet.decrypt(token)
            except InvalidToken:
                raise BackupError('Wrong key or damaged backup') from None
            if len(payload) < 25 or payload[:24] != identifier + struct.pack('>Q', index):
                raise BackupError('Backup records were reordered or substituted')
            final, chunk = payload[24], payload[25:]
            if final == 1:
                if chunk or incoming.read(1):
                    raise BackupError('Invalid backup end marker')
                break
            if final != 0 or not chunk or len(chunk) > CHUNK:
                raise BackupError('Invalid backup record')
            total += len(chunk)
            if total > MAX_CONTENT:
                raise BackupError('Backup exceeds supported size')
            outgoing.write(chunk)
            index += 1


def create(data, output, key, revision='unknown'):
    data, output = Path(data).resolve(), Path(output).absolute()
    if output.exists():
        raise BackupError('Backup destination already exists')
    cipher(key)
    private_directory(output.parent)
    with TemporaryDirectory(prefix='.backup-', dir=output.parent) as temporary:
        stage = Path(temporary)
        snapshot = stage / 'app.db'
        with readonly(data / 'app.db') as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        with readonly(snapshot) as connection:
            integrity(connection)
            refs, records = references(connection), counts(connection)
        files = {'app.db': check_file(snapshot, {})}
        archive = stage / 'payload.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
            bundle.write(snapshot, 'app.db')
            for name, expected in sorted(refs.items()):
                target = safe_file(data, name)
                # Hash the same bytes copied into the archive, detecting mutation during copying.
                sha, size = hashlib.sha256(), 0
                with target.open('rb') as incoming, bundle.open(name, 'w', force_zip64=True) as outgoing:
                    while chunk := incoming.read(CHUNK):
                        sha.update(chunk); size += len(chunk); outgoing.write(chunk)
                files[name] = {'size': size, 'sha256': sha.hexdigest()}
                if expected.get('size', size) != size or expected.get('sha256', sha.hexdigest()) != sha.hexdigest():
                    raise BackupError('Original file changed or failed metadata validation')
            if len(files) > MAX_FILES or sum(f['size'] for f in files.values()) > MAX_CONTENT:
                raise BackupError('Backup exceeds supported size')
            manifest = {'format': 1, 'created_at': datetime.now(UTC).isoformat(), 'revision': revision,
                        'files': files, 'records': records, 'excluded': ['sessions on restore', 'runtime logs', 'keys', 'models', 'rebuildable public catalogue']}
            bundle.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        if archive.stat().st_size > MAX_CONTENT:
            raise BackupError('Backup exceeds supported archive size')
        encrypted = stage / 'encrypted.spbackup'
        encrypt_archive(archive, encrypted, key)
        # Hard link publication fails rather than overwriting an existing destination.
        os.link(encrypted, output)
        return {'created_at': manifest['created_at'], 'files': len(files), 'records': records, 'bytes': output.stat().st_size}


def unpack_verified(archive, stage):
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        names = [item.filename for item in entries]
        if len(entries) > MAX_FILES + 1 or len(set(names)) != len(names) or 'manifest.json' not in names:
            raise BackupError('Invalid backup inventory')
        if bundle.getinfo('manifest.json').file_size > 8 * CHUNK:
            raise BackupError('Manifest is too large')
        manifest = json.loads(bundle.read('manifest.json'))
        if not isinstance(manifest, dict):
            raise BackupError('Invalid manifest')
        files = manifest.get('files')
        if manifest.get('format') != 1 or not isinstance(files, dict) or set(names) != set(files) | {'manifest.json'} or 'app.db' not in files:
            raise BackupError('Backup inventory does not match manifest')
        if sum(entry.file_size for entry in entries) > MAX_CONTENT:
            raise BackupError('Backup exceeds supported size')
        if shutil.disk_usage(stage).free < sum(entry.file_size for entry in entries) + 16 * CHUNK:
            raise BackupError('Not enough free disk space for restore')
        for name, expected in files.items():
            parts = PurePosixPath(name).parts
            allowed = name == 'app.db' or (len(parts) == 2 and parts[0] in {'uploads', 'letterheads'} and parts[1] not in {'.', '..'})
            if not allowed or '\\' in name or ':' in name or name != '/'.join(parts):
                raise BackupError('Unsafe archive path')
            entry = bundle.getinfo(name)
            if entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise BackupError('Archive links are not supported')
            if not isinstance(expected, dict) or expected.get('size') != entry.file_size:
                raise BackupError('Invalid file metadata')
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with bundle.open(entry) as incoming, target.open('xb') as outgoing:
                os.chmod(target, 0o600)
                shutil.copyfileobj(incoming, outgoing, CHUNK)
            if check_file(target, expected) != expected:
                raise BackupError('Invalid integrity metadata')
        with readonly(stage / 'app.db') as connection:
            integrity(connection)
            refs = references(connection)
            if set(files) != {'app.db'} | set(refs) or counts(connection) != manifest.get('records'):
                raise BackupError('Database and backup inventory disagree')
            for name, expected in refs.items():
                check_file(safe_file(stage, name), expected)
        return manifest


def restore(backup, destination, key):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise BackupError('Restore requires a new, nonexistent destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.restore-', dir=destination.parent) as temporary:
        stage = private_directory(temporary)
        archive, restored = stage / 'payload.zip', stage / 'restored'
        decrypt_archive(backup, archive, key)
        restored.mkdir(mode=0o700)
        manifest = unpack_verified(archive, restored)
        with closing(sqlite3.connect(restored / 'app.db')) as connection:
            # Backups must not revive previously issued login sessions.
            connection.execute('DELETE FROM sessions')
            connection.commit()
            connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            connection.execute('PRAGMA journal_mode=DELETE')
        (restored / 'uploads').mkdir(exist_ok=True, mode=0o700)
        (restored / 'letterheads').mkdir(exist_ok=True, mode=0o700)
        # Claim an empty destination exclusively. Never rename over an existing directory.
        destination.mkdir(mode=0o700)
        private_directory(destination)
        try:
            for entry in restored.iterdir():
                entry.rename(destination / entry.name)
        except Exception:
            # Leave any partial restore for inspection; never recursively delete an operator path.
            raise BackupError('Restore publication failed; destination may contain partial data') from None
        return {'backup_created_at': manifest['created_at'], 'files': len(manifest['files']), 'records': manifest['records'], 'sessions_revoked': True}


def verify(backup, key, workspace):
    private_directory(workspace)
    with TemporaryDirectory(prefix='.verify-', dir=workspace) as temporary:
        stage = Path(temporary)
        archive, extracted = stage / 'payload.zip', stage / 'checked'
        decrypt_archive(backup, archive, key)
        extracted.mkdir(mode=0o700)
        manifest = unpack_verified(archive, extracted)
        return {'valid': True, 'created_at': manifest['created_at'], 'files': len(manifest['files']), 'records': manifest['records']}


def status(data):
    data = Path(data)
    with readonly(data / 'app.db') as connection:
        integrity(connection)
        refs, records = references(connection), counts(connection)
        for name, expected in refs.items():
            check_file(safe_file(data, name), expected)
    return {'healthy': True, 'required_files': len(refs), 'records': records, 'free_bytes': shutil.disk_usage(data).free}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('init-key', 'create', 'verify', 'restore', 'status'):
        item = sub.add_parser(name)
        if name != 'status':
            item.add_argument('--key-file', type=Path, required=True)
        if name in {'create', 'status'}:
            item.add_argument('--data-dir', type=Path, required=True)
        if name == 'create':
            item.add_argument('--output', type=Path, required=True)
            item.add_argument('--revision', default='unknown')
        if name in {'verify', 'restore'}:
            item.add_argument('--backup', type=Path, required=True)
        if name == 'restore':
            item.add_argument('--destination', type=Path, required=True)
        if name == 'verify':
            item.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init-key':
            init_key(args.key_file); result = {'key_created': True}
        elif args.command == 'create':
            result = create(args.data_dir, args.output, args.key_file, args.revision)
        elif args.command == 'verify':
            result = verify(args.backup, args.key_file, args.workspace)
        elif args.command == 'restore':
            result = restore(args.backup, args.destination, args.key_file)
        else:
            result = status(args.data_dir)
        print(json.dumps(result))
    except (BackupError, OSError, sqlite3.Error, zipfile.BadZipFile, ValueError):
        print('Backup operation failed. Check the key, storage integrity, free space and destination; existing data was not overwritten.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
