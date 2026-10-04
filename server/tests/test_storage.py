import unittest
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from server import app as api


class PersistentStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.original_paths = api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH
        api.DATA_DIR = Path(self.temp.name)
        api.UPLOAD_DIR = api.DATA_DIR / "uploads"
        api.DB_PATH = api.DATA_DIR / "app.db"
        api.failed_logins.clear()

    def tearDown(self):
        api.DATA_DIR, api.UPLOAD_DIR, api.DB_PATH = self.original_paths
        self.temp.cleanup()

    def authenticate(self, client, email="storage-test@example.invalid"):
        client.headers["X-Schimmelpilz-Request"] = "1"
        if client.get("/api/auth/me").status_code == 200:
            return
        payload = {"email": email, "password": "Only-a-test-password-2026", "audience": "consumer", "full_name": "Test Person", "street": "Teststraße 1", "postal_code": "10115", "city": "Berlin", "country": "Deutschland"}
        result = client.post("/api/auth/register", json=payload)
        if result.status_code == 409:
            result = client.post("/api/auth/login", json={"email": email, "password": payload["password"]})
        self.assertIn(result.status_code, [200, 201], result.text)

    def create_case(self, client):
        self.authenticate(client)
        response = client.post("/api/cases", json={"title": "Speichertest", "description": "Nur synthetische Testdaten zur Speicherung.", "language": "de"})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_case_file_and_edited_draft_survive_restart(self):
        body = "Eigener Entwurf mit Umlauten: ÄÖÜ.\n\nDer Wortlaut muss exakt erhalten bleiben."
        content = b"%PDF-1.1\nSynthetic storage fixture\n%%EOF"
        with TestClient(api.app) as client:
            case = self.create_case(client)
            document = client.post(f"/api/cases/{case['id']}/documents", files={"file": ("Beleg.pdf", content, "application/pdf")})
            self.assertEqual(document.status_code, 201, document.text)
            document = document.json()
            draft = client.post(f"/api/cases/{case['id']}/drafts", json={"body": body, "language": "de"})
            self.assertEqual(draft.status_code, 201, draft.text)
            self.assertEqual(draft.json()["body"], body)
            edited = body + "\nNachträgliche Ergänzung."
            result = client.put(f"/api/cases/{case['id']}/drafts/{draft.json()['id']}", json={"body": edited})
            self.assertEqual(result.status_code, 200, result.text)

        # Re-run startup over the same files, as happens after a backend restart.
        with TestClient(api.app) as client:
            self.authenticate(client)
            saved = client.get(f"/api/cases/{case['id']}").json()
            self.assertEqual(saved["reference"], case["reference"])
            self.assertEqual(len(saved["drafts"]), 1)
            self.assertEqual(saved["drafts"][0]["body"], edited)
            self.assertEqual(saved["documents"][0]["original_name"], "Beleg.pdf")
            downloaded = client.get(f"/api/cases/{case['id']}/documents/{document['id']}/download")
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(downloaded.content, content)
            self.assertIn("attachment", downloaded.headers["content-disposition"])

    def test_case_scoping_and_validation(self):
        with TestClient(api.app) as client:
            first = self.create_case(client)
            second = self.create_case(client)
            document = client.post(f"/api/cases/{first['id']}/documents", files={"file": ("../../Beleg.pdf", b"pdf-test", "application/pdf")}).json()
            self.assertEqual(document["original_name"], "Beleg.pdf")
            self.assertEqual(client.get(f"/api/cases/{second['id']}/documents/{document['id']}/download").status_code, 404)
            draft = client.post(f"/api/cases/{first['id']}/drafts", json={"body": "Original"}).json()
            self.assertEqual(client.put(f"/api/cases/{second['id']}/drafts/{draft['id']}", json={"body": "Anderer Fall"}).status_code, 404)
            self.assertEqual(client.put(f"/api/cases/{first['id']}/drafts/{draft['id']}", json={"body": "   "}).status_code, 422)
            before = len(list(api.UPLOAD_DIR.iterdir()))
            self.assertEqual(client.post(f"/api/cases/{first['id']}/documents", files={"file": ("bad.exe", b"test")}).status_code, 415)
            self.assertEqual(client.post(f"/api/cases/{first['id']}/documents", files={"file": ("empty.pdf", b"")}).status_code, 422)
            self.assertEqual(client.post(f"/api/cases/{first['id']}/documents", files={"file": ("big.pdf", b"0" * (api.MAX_UPLOAD_BYTES + 1))}).status_code, 413)
            self.assertEqual(len(list(api.UPLOAD_DIR.iterdir())), before)

    def test_parallel_reference_allocation(self):
        with TestClient(api.app) as client:
            self.authenticate(client)
            with ThreadPoolExecutor(max_workers=4) as pool:
                created = list(pool.map(lambda _: self.create_case(client), range(8)))
            self.assertEqual(len({item["reference"] for item in created}), 8)
            self.assertEqual(len(client.get("/api/cases").json()), 8)

    def test_existing_reference_details_and_generated_collision(self):
        with TestClient(api.app) as client:
            self.authenticate(client)
            payload = {"title": "Neue Mandatsakte", "description": "Ein synthetischer Sachverhalt zur Prüfung.", "reference_mode": "existing", "reference": f"SCH-{datetime.now().year}-000001", "details": {"audience": "law_firm", "client_name": "Testmandant", "opponent_name": "Testgegner", "legal_area": "commercial", "court_reference": "12 O 123/26", "received_on": "2026-10-03", "deadline": "2026-10-30", "dispute_value": 1250.50, "objective": "Vertrag und Zuständigkeit recherchieren."}}
            saved = client.post("/api/cases", json=payload)
            self.assertEqual(saved.status_code, 201, saved.text)
            self.assertEqual(saved.json()["reference"], payload["reference"])
            generated = self.create_case(client)
            self.assertTrue(generated["reference"].endswith("000002"))
            self.assertEqual(client.post("/api/cases", json={**payload, "reference": payload["reference"].lower()}).status_code, 409)
            self.assertEqual(client.post("/api/cases", json={**payload, "reference": None}).status_code, 422)
            self.assertEqual(client.post("/api/cases", json={**payload, "reference": "Other", "details": {"deadline": "not-a-date"}}).status_code, 422)
            draft = client.post(f"/api/cases/{saved.json()['id']}/drafts", json={"body": "Eigener Klageentwurf", "kind": "claim", "recipient": "Testgericht\nTestadresse"}).json()
            client.put(f"/api/cases/{saved.json()['id']}/drafts/{draft['id']}", json={"body": "Eigener geänderter Antrag", "kind": "application", "recipient": "Testbehörde", "language": "en"})
            case_id = saved.json()["id"]
        with TestClient(api.app) as client:
            self.authenticate(client)
            loaded = client.get(f"/api/cases/{case_id}").json()
            self.assertEqual(loaded["details"]["client_name"], "Testmandant")
            self.assertEqual(loaded["details"]["court_reference"], "12 O 123/26")
            self.assertEqual(loaded["details"]["dispute_value"], 1250.50)
            self.assertEqual(loaded["drafts"][0]["body"], "Eigener geänderter Antrag")
            self.assertEqual(loaded["drafts"][0]["kind"], "application")
            self.assertEqual(loaded["drafts"][0]["recipient"], "Testbehörde")
            self.assertEqual(loaded["drafts"][0]["language"], "en")

    def test_authentication_and_account_isolation(self):
        with TestClient(api.app) as first, TestClient(api.app) as other:
            self.assertEqual(first.get("/api/cases").status_code, 401)
            self.assertEqual(first.post("/api/auth/login", json={"email": "x@y.invalid", "password": "no"}).status_code, 403)
            self.authenticate(first)
            case = self.create_case(first)
            document = first.post(f"/api/cases/{case['id']}/documents", files={"file": ("Beleg.pdf", b"test")}).json()
            draft = first.post(f"/api/cases/{case['id']}/drafts", json={"body": "Private draft"}).json()
            self.authenticate(other, "another-account@example.invalid")
            self.assertEqual(other.get("/api/cases").json(), [])
            self.assertEqual(other.get(f"/api/cases/{case['id']}").status_code, 404)
            self.assertEqual(other.get(f"/api/cases/{case['id']}/documents/{document['id']}/download").status_code, 404)
            self.assertEqual(other.post(f"/api/cases/{case['id']}/documents", files={"file": ("Beleg.pdf", b"test")}).status_code, 404)
            self.assertEqual(other.post(f"/api/cases/{case['id']}/drafts", json={"body": "Attempt"}).status_code, 404)
            self.assertEqual(other.put(f"/api/cases/{case['id']}/drafts/{draft['id']}", json={"body": "Attempt"}).status_code, 404)
            duplicate_for_other = other.post("/api/cases", json={"title": "Eigene Akte", "description": "Die Referenz darf in diesem Konto existieren.", "reference_mode": "existing", "reference": case["reference"]})
            self.assertEqual(duplicate_for_other.status_code, 201, duplicate_for_other.text)
            logged_in = first.post("/api/auth/login", json={"email": "STORAGE-TEST@EXAMPLE.INVALID", "password": "Only-a-test-password-2026"})
            self.assertEqual(logged_in.status_code, 200)
            self.assertIn("HttpOnly", logged_in.headers["set-cookie"])
            self.assertIn("SameSite=strict", logged_in.headers["set-cookie"])
            self.assertNotIn("password_hash", logged_in.json())
            with api.db() as connection:
                password = connection.execute("SELECT password_hash FROM users LIMIT 1").fetchone()[0]
                self.assertNotEqual(password, "Only-a-test-password-2026")
            self.assertEqual(first.post("/api/auth/logout").status_code, 204)
            self.assertEqual(first.get("/api/auth/me").status_code, 401)
            self.assertEqual(first.get(f"/api/cases/{case['id']}/documents/{document['id']}/download").status_code, 401)

    def test_legacy_database_migration_preserves_records_and_ownership(self):
        connection = sqlite3.connect(api.DB_PATH)
        connection.executescript("""
            CREATE TABLE cases (id TEXT PRIMARY KEY, reference TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description TEXT NOT NULL, language TEXT NOT NULL, created_at TEXT NOT NULL);
            INSERT INTO cases VALUES ('old-case', 'OLD-2026', 'Alte Akte', 'Bestehende Daten bleiben erhalten.', 'de', '2026-10-03');
        """)
        connection.close()
        with TestClient(api.app) as client:
            self.authenticate(client)
            cases = client.get("/api/cases").json()
            self.assertEqual(cases[0]["reference"], "OLD-2026")
            self.assertEqual(cases[0]["details"], {})
            document = client.post("/api/cases/old-case/documents", files={"file": ("Old.pdf", b"legacy file")}).json()
        with TestClient(api.app) as client:
            self.authenticate(client)
            self.assertEqual(client.get(f"/api/cases/old-case/documents/{document['id']}/download").content, b"legacy file")
            with api.db() as connection:
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_invalid_sign_in_expired_session_and_secure_cookie(self):
        with TestClient(api.app, base_url="https://testserver") as client:
            self.authenticate(client)
            logged_in = client.post("/api/auth/login", json={"email": "storage-test@example.invalid", "password": "Only-a-test-password-2026"})
            self.assertIn("Secure", logged_in.headers["set-cookie"])
            wrong = client.post("/api/auth/login", json={"email": "storage-test@example.invalid", "password": "Definitely-wrong-password"})
            self.assertEqual(wrong.status_code, 401)
            self.assertEqual(client.post("/api/cases", json={"title": "Valid title", "description": "This is a test case.", "details": {"dispute_value": -1}}).status_code, 422)
            case = self.create_case(client)
            self.assertEqual(client.post(f"/api/cases/{case['id']}/drafts", json={"kind": "claim"}).status_code, 422)
            with api.db() as connection:
                connection.execute("UPDATE sessions SET expires_at = '2000-01-01'")
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
            self.assertEqual(client.get("/api/cases").status_code, 401)


if __name__ == "__main__":
    unittest.main()
