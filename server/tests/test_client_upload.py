from fastapi.testclient import TestClient

from server import app as api, client_upload
from server.tests import test_inbox

PDF = b'%PDF-1.4\n%%EOF'
HEADERS = {'X-Schimmelpilz-Request': '1'}


class ClientUploadTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_link_page_upload_into_inbox_limits_and_revoke(self):
        client_upload.RATE.clear()
        with TestClient(api.app) as firm, TestClient(api.app) as anonymous, TestClient(api.app) as other:
            self.login(firm, 'upload@example.invalid')
            case = firm.post('/api/cases', json={'title': 'Mietminderung', 'description': 'Synthetische Akte für Mandanten-Uploads.', 'details': {'client_name': 'Anna Weber'}}).json()
            link = firm.post(f"/api/cases/{case['id']}/upload-links", json={'days': 7, 'max_files': 2, 'message': 'Bitte Mietvertrag und Fotos hochladen.'}).json()
            self.assertEqual(link['state'], 'active')
            page = anonymous.get(link['path'])
            self.assertEqual(page.status_code, 200)
            self.assertIn('Bitte Mietvertrag und Fotos hochladen.', page.text)
            self.assertIn(case['reference'], page.text)
            self.assertNotIn('Anna Weber', page.text)                      # no client data on the public page
            self.assertIn("script-src 'nonce-", page.headers['content-security-policy'])
            ok = anonymous.post(link['path'], headers=HEADERS, files={'file': ('Mietvertrag.pdf', PDF, 'application/pdf')}, data={'name': 'Anna W.', 'note': 'Seite 3 fehlt noch'})
            self.assertEqual(ok.status_code, 201, ok.text)
            self.assertEqual(anonymous.post(link['path'], headers=HEADERS, files={'file': ('foto.jpg', PDF, 'image/jpeg')}).status_code, 415)   # signature mismatch
            self.assertEqual(anonymous.post(link['path'], headers=HEADERS, files={'file': ('tool.exe', b'MZ', 'application/octet-stream')}).status_code, 415)
            self.assertEqual(anonymous.post(link['path'], headers=HEADERS, files={'file': ('bild.png', b'\x89PNG\r\n\x1a\n' + b'0' * 20, 'image/png')}).status_code, 201)
            self.assertEqual(anonymous.post(link['path'], headers=HEADERS, files={'file': ('drei.pdf', PDF, 'application/pdf')}).status_code, 410)   # max 2 files
            self.assertEqual(anonymous.get(link['path']).status_code, 410)
            inbox = firm.get('/api/inbox').json()
            self.assertEqual(sorted(item['original_name'] for item in inbox), ['Mietvertrag.pdf', 'bild.png'])
            entry = next(item for item in inbox if item['original_name'] == 'Mietvertrag.pdf')
            self.assertEqual((entry['suggested_case_id'], entry['case_id'], entry['sender'], entry['note']), (case['id'], None, 'Upload-Link: Anna W.', 'Seite 3 fehlt noch'))
            tasks = firm.get(f"/api/cases/{case['id']}").json()['tasks']
            self.assertEqual(sum(task['title'].startswith('Mandanten-Upload') for task in tasks), 1)
            links = firm.get(f"/api/cases/{case['id']}/upload-links").json()
            self.assertEqual((links[0]['uploaded'], links[0]['state']), (2, 'full'))
            self.assertNotIn('token', links[0])
            second = firm.post(f"/api/cases/{case['id']}/upload-links", json={}).json()
            self.assertEqual(firm.delete(f"/api/cases/{case['id']}/upload-links/{second['id']}").status_code, 204)
            self.assertEqual(anonymous.get(second['path']).status_code, 410)
            self.assertEqual(anonymous.get('/api/public/upload/' + 'x' * 32).status_code, 410)
            self.login(other, 'upload-other@example.invalid')
            self.assertEqual(other.get(f"/api/cases/{case['id']}/upload-links").status_code, 404)
            self.assertEqual(other.post(f"/api/cases/{case['id']}/upload-links", json={}).status_code, 404)
            svg = firm.post('/api/upload-links/qr', json={'text': 'https://kanzlei.example/api/public/upload/abc123456789'})
            self.assertTrue(svg.text.lstrip().startswith('<?xml') or '<svg' in svg.text)
