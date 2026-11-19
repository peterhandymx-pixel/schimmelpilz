from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app as api
from server import letter_ai, research
from server.tests import test_inbox

LETTER = 'Creditum Inkasso GmbH\nHamburg, 28.10.2026\nHauptforderung 38,97 EUR, Gesamtforderung 192,37 EUR. Zahlen Sie bis 11.11.2026.'


class LetterAiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_ai_reading_is_validated_merged_and_optional(self):
        model = {'kind': 'inkasso', 'sender': 'Creditum Inkasso GmbH', 'creditor': 'StreamFlix Media AG', 'amount': '192,37', 'letter_date': '2026-10-28',
                 'letter_deadline': 'nächste Woche', 'reference': '', 'summary': 'Ein Inkassobüro fordert 192,37 €.', 'demands': ['Zahlung', 42]}
        with TestClient(api.app) as client:
            self.login(client, 'letter-ai@example.invalid')
            with patch.object(research, 'generate_json', return_value=model) as reader:
                plain = client.post('/api/letter-assistant/analyze', json={'text': LETTER}).json()
                self.assertFalse(plain['ai']); reader.assert_not_called()
                read = client.post('/api/letter-assistant/analyze', json={'text': LETTER, 'use_ai': True}).json()
            self.assertTrue(read['ai'])
            self.assertEqual((read['kind']['id'], read['fields']['creditor'], read['fields']['amount']), ('inkasso', 'StreamFlix Media AG', 192.37))
            # An invalid date from the model never replaces the rule-based reading.
            self.assertEqual(read['fields']['letter_deadline'], '2026-11-11')
            self.assertEqual(read['demands'], ['Zahlung', '42'])
            with patch.object(research, 'generate_json', return_value={**model, 'kind': 'erfunden'}):
                self.assertEqual(client.post('/api/letter-assistant/analyze', json={'text': LETTER, 'use_ai': True}).json()['kind']['id'], plain['kind']['id'])
            with patch.object(research, 'generate_json', side_effect=TimeoutError):
                failed = client.post('/api/letter-assistant/analyze', json={'text': LETTER, 'use_ai': True}).json()
            self.assertFalse(failed['ai'])
            self.assertEqual(failed['fields'], plain['fields'])

    def test_explanation_gets_rule_deadline_readable_answers_and_respects_operator_switch(self):
        seen = {}

        def answer(messages):
            seen['user'] = messages[1]['content']
            return {'answer': 'Die Frist endet am 11.11.2026.'}
        with TestClient(api.app) as client:
            self.login(client, 'letter-explain@example.invalid')
            body = {'kind': 'inkasso', 'fields': {'sender': 'Creditum', 'amount': 192.37, 'letter_deadline': '2026-11-11'}, 'answers': {'received_on': '2026-11-03', 'owes': 'unsure'}, 'text': LETTER}
            with patch.object(research, 'generate_answer', side_effect=answer):
                result = client.post('/api/letter-assistant/explain', json=body)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertIn('bis 11.11.2026', seen['user'])
            self.assertIn('Schulden Sie den geforderten Betrag?', seen['user'])
            self.assertIn('(verbindlich)', seen['user'])
            with patch.object(research, 'generate_answer', side_effect=OSError):
                self.assertEqual(client.post('/api/letter-assistant/explain', json=body).status_code, 503)
            with api.db() as connection:
                connection.execute('UPDATE operator_settings SET ai_enabled=0 WHERE id=1')
            with patch.object(research, 'generate_json') as reader:
                self.assertFalse(client.post('/api/letter-assistant/analyze', json={'text': LETTER, 'use_ai': True}).json()['ai'])
                reader.assert_not_called()
            self.assertEqual(client.post('/api/letter-assistant/explain', json=body).status_code, 503)


class LetterDirectionTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_own_filing_is_outgoing_and_model_court_replaces_pattern_guess(self):
        filing = ('Synthetic Person, Testweg 1, 10115 Berlin\nAn das Landessozialgericht\nAktenzeichen: L 9 SO 1/26 B ER\n(Vorinstanz: Sozialgericht Köln)\n'
                  'Replik auf den Schriftsatz der Antragsgegnerin vom 21.09.2026')
        seen = {}

        def model(messages):
            seen['system'] = messages[0]['content']
            return {'kind': 'sonstiges', 'direction': 'outgoing', 'sender': 'Synthetic Person', 'court': 'Landessozialgericht', 'opponent': 'Landesbehörde',
                    'reference': 'L 9 SO 1/26 B ER', 'summary': 'Eigener Schriftsatz.'}
        with TestClient(api.app) as client:
            self.login(client, 'direction@example.invalid')
            with patch.object(research, 'generate_json', side_effect=model):
                read = client.post('/api/letter-assistant/analyze', json={'text': filing, 'use_ai': True}).json()
        self.assertEqual(read['direction'], 'outgoing')
        self.assertEqual(read['fields']['court'], 'Landessozialgericht')
        self.assertEqual(read['fields']['creditor'], 'Landesbehörde')
        self.assertIn('Synthetic Person', seen['system'])
        self.assertEqual(letter_ai.merge({'creditor': 'auf den Schriftsatz', 'court': 'Sozialgericht Köln', 'sender': 'X'},
                                         {'fields': {'creditor': '', 'court': '', 'sender': ''}}), {'creditor': '', 'court': '', 'sender': 'X'})


class AuthorityAreaTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_social_authority_decision_stays_social_when_the_model_picks_the_kind(self):
        text = 'Versorgungsamt Köln\nBescheid über die Feststellung des Grades der Behinderung nach dem SGB IX\nRechtsbehelfsbelehrung: Widerspruch innerhalb eines Monats.'
        with TestClient(api.app) as client:
            self.login(client, 'authority@example.invalid')
            with patch.object(research, 'generate_json', return_value={'kind': 'bescheid', 'sender': 'Versorgungsamt Köln', 'summary': 'GdB-Bescheid.'}):
                read = client.post('/api/letter-assistant/analyze', json={'text': text, 'use_ai': True}).json()
        self.assertEqual((read['kind']['id'], read['kind']['legal_area']), ('bescheid', 'social'))
