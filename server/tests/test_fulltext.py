from fastapi.testclient import TestClient

from server import app as api, fulltext
from server.tests import test_inbox


def test_folding_and_excerpt():
    assert fulltext.matches('Herr Müller, Straße 5', [fulltext.fold('mueller'), fulltext.fold('strasse')])
    assert not fulltext.matches('Herr Meier', [fulltext.fold('müller')])
    assert 'Müller' in fulltext.excerpt('x ' * 200 + 'Zahlung an Müller Bau' + ' y' * 200, [fulltext.fold('mueller')])


class FulltextTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_search_finds_particulars_tasks_and_respects_owner(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client, 'fulltext@example.invalid')
            case = client.post('/api/cases', json={'title': 'Werklohn Weber', 'description': 'Synthetische Akte zur Volltextsuche.',
                                                   'details': {'client_name': 'Anna Weber', 'opponent_name': 'Müller Bau GmbH', 'opponent_reference': 'MB-4711/26'}}).json()
            client.post(f"/api/cases/{case['id']}/tasks", json={'title': 'Stellungnahme Müller abwarten', 'note': 'IBAN DE02 1203 0000 0000 2020 51 prüfen', 'due_on': '2026-12-01', 'priority': 'normal', 'kind': 'resubmission'})
            result = client.post('/api/search', json={'q': 'mueller'}).json()
            self.assertEqual(result['groups'][0]['reference'], case['reference'])
            self.assertEqual({hit['kind'] for hit in result['groups'][0]['hits']}, {'case', 'task'})
            self.assertEqual(client.post('/api/search', json={'q': 'MB-4711/26'}).json()['groups'][0]['hits'][0]['tab'], 'overview')
            self.assertEqual(client.post('/api/search', json={'q': '2020 51'}).json()['groups'][0]['hits'][0]['kind'], 'task')
            self.assertEqual(client.post('/api/search', json={'q': 'müller kündigung'}).json()['total'], 0)   # all words must match
            self.assertEqual(client.get('/api/search').status_code, 405)                                   # never in the URL
            self.login(other, 'fulltext-other@example.invalid')
            self.assertEqual(other.post('/api/search', json={'q': 'mueller'}).json()['total'], 0)
