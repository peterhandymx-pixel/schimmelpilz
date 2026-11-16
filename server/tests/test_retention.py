import io
from datetime import date

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server import app as api, retention
from server.tests import test_inbox


def test_period_ends_six_years_after_the_calendar_year():
    assert retention.retained_until(date(2020, 3, 5)) == date(2026, 12, 31)
    assert retention.retained_until(date(2019, 12, 31)) == date(2025, 12, 31)


class RetentionTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def archived_case(self, client, title):
        case = client.post('/api/cases', json={'title': title, 'description': 'Synthetische Akte für die Aufbewahrung.'}).json()
        client.post(f"/api/cases/{case['id']}/documents", files={'file': ('Brief.pdf', b'%PDF-1.4\n%%EOF', 'application/pdf')})
        return client.put(f"/api/cases/{case['id']}/archive", json={'archived': True, 'expected_version': 0}).json()

    def test_running_period_blocks_destruction_old_file_is_destroyed_with_protocol(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client, 'retention@example.invalid')
            recent = self.archived_case(client, 'Neue Akte')
            old = self.archived_case(client, 'Alte Akte')
            open_case = client.post('/api/cases', json={'title': 'Laufend', 'description': 'Noch nicht archiviert.'}).json()
            overview = client.get('/api/retention').json()
            self.assertEqual(len(overview['items']), 2)
            this_year = int(api.now()[:4])
            self.assertTrue(all(item['retained_until'] == f'{this_year + 6}-12-31' and not item['destroyable'] for item in overview['items']))
            self.assertEqual(client.post(f"/api/retention/{recent['id']}/destroy", json={'confirm': recent['reference']}).status_code, 409)
            self.assertEqual(client.put(f"/api/retention/{open_case['id']}", json={'ended_on': '2018-06-30'}).status_code, 409)
            self.assertEqual(client.put(f"/api/retention/{old['id']}", json={'ended_on': '2099-01-01'}).status_code, 422)
            updated = client.put(f"/api/retention/{old['id']}", json={'ended_on': '2018-06-30'}).json()
            self.assertEqual(updated['retained_until'], '2024-12-31'); self.assertTrue(updated['destroyable'])
            self.assertEqual(client.get('/api/retention').json()['items'][0]['reference'], old['reference'])     # destroyable first
            self.assertEqual(client.post(f"/api/retention/{old['id']}/destroy", json={'confirm': 'falsch'}).status_code, 422)
            self.login(other, 'retention-other@example.invalid')
            self.assertEqual(other.post(f"/api/retention/{old['id']}/destroy", json={'confirm': old['reference']}).status_code, 404)
            done = client.post(f"/api/retention/{old['id']}/destroy", json={'confirm': old['reference']}).json()
            self.assertEqual((done['reference'], done['documents']), (old['reference'], 1))
            self.assertEqual(client.get(f"/api/cases/{old['id']}").status_code, 404)
            self.assertEqual(client.get('/api/retention').json()['log'][0]['reference'], old['reference'])
            text = PdfReader(io.BytesIO(client.get('/api/retention/protocol.pdf').content)).pages[0].extract_text()
            self.assertIn('Vernichtungsprotokoll', text); self.assertIn(old['reference'], text); self.assertIn('31.12.2024', text)
