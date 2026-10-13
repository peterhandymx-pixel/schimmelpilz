import json
import io
import os
import sqlite3
import struct
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from server import app as api
from server import backup
from server.tests.test_document_research import synthetic_pdf
from server.tests.test_letterheads import paper
from pypdf import PdfReader


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH
        api.DATA_DIR = self.root / 'source'
        api.UPLOAD_DIR = api.DATA_DIR / 'uploads'
        api.DB_PATH = api.DATA_DIR / 'app.db'
        self.key = self.root / 'keys/backup.key'
        backup.init_key(self.key)
        self.output = self.root / 'archives/test.spbackup'
        api.failed_logins.clear()

    def tearDown(self):
        api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH = self.paths
        self.temp.cleanup()

    def seed(self):
        with TestClient(api.app) as client:
            client.headers['X-Schimmelpilz-Request'] = '1'
            register = client.post('/api/auth/register', json={
                'email': 'backup-test@example.invalid', 'password': 'Synthetic-backup-2026!',
                'audience': 'consumer', 'full_name': 'Backup Test', 'street': 'Testweg 1',
                'postal_code': '10115', 'city': 'Berlin', 'country': 'Deutschland'})
            self.assertEqual(register.status_code, 201, register.text)
            case = client.post('/api/cases', json={'title': 'Synthetic backup case', 'description': 'Backup test only.'}).json()
            document = client.post('/api/cases/' + case['id'] + '/documents', files={'file': ('synthetic.pdf', synthetic_pdf(), 'application/pdf')}).json()
            inbox = client.post('/api/inbox', data={'received_on': '2026-10-12'}, files={'file': ('pending.pdf', b'Only synthetic pending upload', 'application/pdf')}).json()
            head = client.post('/api/auth/letterheads', files={'file': ('Paper.pdf', paper(count=1), 'application/pdf')}).json()
            self.assertEqual(client.put('/api/auth/letterheads/' + head['id'] + '/activate', json={'confirmed': True}).status_code, 200)
            draft = client.post('/api/cases/' + case['id'] + '/drafts', json={'language': 'de', 'recipient': 'Synthetic Recipient', 'kind': 'letter', 'body': 'Synthetic saved draft.'}).json()
            with api.db() as conn:
                conn.execute('INSERT INTO research_runs(id,case_id,question,language,workflow,answer,status,model,created_at,sources) VALUES(?,?,?,?,?,?,?,?,?,?)',
                             ('synthetic-research', case['id'], 'Synthetic research question', 'de', 'research', 'Synthetic answer', 'completed', 'mock', api.now(), json.dumps([{'text': 'Exact synthetic passage', 'sha256': 'synthetic-provenance'}])))
            return case, document, inbox, draft, client.cookies.get('schimmelpilz_session')

    def test_round_trip_login_files_drafts_and_sessions_revoked(self):
        case, doc, inbox, draft, old_token = self.seed()
        # Never copy loose, unreferenced data, keys or logs.
        (api.UPLOAD_DIR / 'unreferenced.pdf').write_bytes(b'Excluded')
        (api.DATA_DIR / 'secret.key').write_text('Excluded', encoding='utf-8')
        summary = backup.create(api.DATA_DIR, self.output, self.key, 'synthetic-revision')
        self.assertEqual(summary['files'], 5)
        self.assertTrue(backup.verify(self.output, self.key, self.root / 'verify')['valid'])
        restored = self.root / 'restored'
        result = backup.restore(self.output, restored, self.key)
        self.assertTrue(result['sessions_revoked'])
        self.assertFalse((restored / 'uploads/unreferenced.pdf').exists())
        self.assertFalse((restored / 'secret.key').exists())
        api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH = restored, restored / 'uploads', restored / 'app.db'
        with TestClient(api.app) as client:
            client.cookies.set('schimmelpilz_session', old_token)
            self.assertEqual(client.get('/api/auth/me').status_code, 401)
            client.headers['X-Schimmelpilz-Request'] = '1'
            self.assertEqual(client.post('/api/auth/login', json={'email': 'backup-test@example.invalid', 'password': 'Synthetic-backup-2026!'}).status_code, 200)
            saved = client.get('/api/cases/' + case['id']).json()
            self.assertEqual(saved['drafts'][0]['body'], draft['body'])
            self.assertEqual(client.get(f"/api/cases/{case['id']}/documents/{doc['id']}/download").content, synthetic_pdf())
            self.assertEqual(client.get(f"/api/inbox/{inbox['id']}/download").content, b'Only synthetic pending upload')
            self.assertEqual(client.get('/api/auth/letterheads').json()['active_id'], draft['letterhead_id'])
            exported = client.get(f"/api/cases/{case['id']}/drafts/{draft['id']}/pdf")
            self.assertEqual(exported.status_code, 200)
            self.assertIn('HEADER VERSION ONE', PdfReader(io.BytesIO(exported.content)).pages[0].extract_text())
            self.assertIn('Synthetic saved draft.', PdfReader(io.BytesIO(exported.content)).pages[0].extract_text())
            with api.db() as connection:
                run = connection.execute('SELECT answer,sources FROM research_runs WHERE id=?', ('synthetic-research',)).fetchone()
                self.assertEqual(run['answer'], 'Synthetic answer')
                self.assertEqual(json.loads(run['sources'])[0]['text'], 'Exact synthetic passage')
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM draft_versions').fetchone()[0], 1)
        self.assertTrue(backup.status(restored)['healthy'])

    def test_missing_original_refuses_backup_and_never_replaces_existing(self):
        self.seed()
        with api.db() as connection:
            original = connection.execute('SELECT original_stored FROM letterheads').fetchone()[0]
        (api.DATA_DIR / 'letterheads' / original).unlink()
        with self.assertRaises(backup.BackupError):
            backup.create(api.DATA_DIR, self.output, self.key)
        self.assertFalse(self.output.exists())
        sentinel = self.root / 'occupied'; sentinel.mkdir(); (sentinel / 'keep.txt').write_text('Keep')
        with self.assertRaises(backup.BackupError):
            backup.restore(self.output, sentinel, self.key)
        self.assertEqual((sentinel / 'keep.txt').read_text(), 'Keep')
        original_key = self.key.read_bytes()
        with self.assertRaises(FileExistsError):
            backup.init_key(self.key)
        self.assertEqual(self.key.read_bytes(), original_key)

    def test_wrong_key_tamper_truncation_reorder_and_replay_fail(self):
        self.seed(); backup.create(api.DATA_DIR, self.output, self.key)
        other_key = self.root / 'keys/other.key'; backup.init_key(other_key)
        with self.assertRaises(backup.BackupError):
            backup.verify(self.output, other_key, self.root / 'verify')
        raw = self.output.read_bytes()
        modified = self.root / 'archives/modified.spbackup'
        for payload in (raw[:-1], raw + b'x', raw[:50] + bytes([raw[50] ^ 1]) + raw[51:]):
            modified.write_bytes(payload)
            with self.assertRaises(backup.BackupError):
                backup.restore(modified, self.root / 'never-published', self.key)
            self.assertFalse((self.root / 'never-published').exists())
        # More than one chunk exercises authenticated sequence and archive identity.
        plain = self.root / 'chunks'; plain.write_bytes(os.urandom(backup.CHUNK + 100))
        chunked = self.root / 'archives/chunks.spbackup'; backup.encrypt_archive(plain, chunked, self.key)
        raw = chunked.read_bytes(); header_size = len(backup.MAGIC) + 16
        first_length = struct.unpack('>I', raw[header_size:header_size+4])[0] + 4
        first = raw[header_size:header_size+first_length]
        rest = raw[header_size+first_length:]
        for payload in (raw[:header_size] + rest + first, raw[:header_size] + first + first + rest):
            modified.write_bytes(payload)
            with self.assertRaises(backup.BackupError):
                backup.verify(modified, self.key, self.root / 'verify')

    def test_authenticated_bad_inventory_and_path_traversal_rejected(self):
        self.seed(); backup.create(api.DATA_DIR, self.output, self.key)
        work = self.root / 'mutate'; work.mkdir()
        plain = work / 'plain.zip'; backup.decrypt_archive(self.output, plain, self.key)
        with zipfile.ZipFile(plain) as bundle:
            entries = {item.filename: bundle.read(item) for item in bundle.infolist()}
        for malicious_name in ('../escaped.txt', 'uploads/../escaped.txt', '/absolute.txt', 'uploads\\escaped.txt'):
            bad = work / 'bad.zip'
            manifest = json.loads(entries['manifest.json'])
            manifest['files'][malicious_name] = {'size': 1, 'sha256': backup.hashlib.sha256(b'x').hexdigest()}
            with zipfile.ZipFile(bad, 'w') as bundle:
                for name, value in entries.items():
                    bundle.writestr(name, json.dumps(manifest) if name == 'manifest.json' else value)
                bundle.writestr(malicious_name, b'x')
            encrypted = work / ('bad-' + os.urandom(4).hex() + '.spbackup')
            backup.encrypt_archive(bad, encrypted, self.key)
            with self.assertRaises(backup.BackupError):
                backup.restore(encrypted, self.root / 'never-published', self.key)
            self.assertFalse((self.root / 'escaped.txt').exists())
            self.assertFalse((self.root / 'never-published').exists())


if __name__ == '__main__':
    unittest.main()
