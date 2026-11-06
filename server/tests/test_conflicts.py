from fastapi.testclient import TestClient

from server import app as api, conflicts
from server.tests import test_inbox


def test_party_matching_is_tolerant_but_not_loose():
    assert conflicts.same_party('Müller Bau GmbH', 'mueller bau')
    assert conflicts.same_party('Mueller-Bau GmbH & Co. KG', 'Müller Bau')
    assert conflicts.same_party('Schmidt, Peter', 'Peter Schmidt')
    assert conflicts.same_party('Dr. Anna Weber', 'anna weber')
    assert conflicts.same_party('Vonovia SE', 'Vonovia')          # one distinctive word of 5+ letters
    assert not conflicts.same_party('Peter Schmidt', 'Anna Schmidt')
    assert not conflicts.same_party('AB GmbH', 'AB Bau GmbH')      # short single word is too vague
    assert not conflicts.same_party('', 'Peter Schmidt')


class ConflictTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def make(self, client, title, client_name, opponent_name):
        body = {'title': title, 'description': 'Synthetische Akte für die Kollisionsprüfung.', 'details': {'audience': 'law_firm', 'client_name': client_name, 'opponent_name': opponent_name}}
        return client.post('/api/cases', json=body).json()

    def test_opponent_becoming_client_is_a_conflict(self):
        with TestClient(api.app) as client:
            self.login(client, 'conflicts@example.invalid')
            old = self.make(client, 'Mietsache Weber', 'Anna Weber', 'Müller Bau GmbH')
            client.post(f"/api/cases/{old['id']}/archive")
            result = client.post('/api/conflicts/check', json={'client': 'Mueller-Bau GmbH & Co. KG', 'opponent': 'Peter Schmidt'}).json()
            self.assertTrue(result['conflict'])
            self.assertEqual([(hit['kind'], hit['side'], hit['reference']) for hit in result['hits']], [('conflict', 'opponent', old['reference'])])
            same_side = client.post('/api/conflicts/check', json={'client': 'Anna Weber'}).json()
            self.assertEqual((same_side['conflict'], same_side['hits'][0]['kind']), (False, 'known'))
            # The file itself is not a hit when its own particulars are checked.
            self.assertEqual(client.post('/api/conflicts/check', json={'client': 'Anna Weber', 'exclude_case': old['id']}).json()['hits'], [])
            self.assertEqual(client.post('/api/conflicts/check', json={'client': 'Jemand Ganz Anderes'}).json(), {'hits': [], 'conflict': False})
            self.assertEqual(client.get('/api/conflicts/check').status_code, 405)
