import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app as api
from server import legal_catalogue, letter_ai, nulegal, research
from server.tests import test_inbox

DECISION = {'court': 'BGH', 'decided': '2018-12-05', 'aktenzeichen': 'VIII ZR 67/18', 'doktyp': 'Urteil', 'snippet': 'Schimmelpilzgefahr durch Wärmebrücken als Sachmangel', 'url': 'https://recht.nulegal.eu/rechtsprechung/bgh/2018-12-05/viii-zr-67-18'}


class NulegalTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def setUp(self):
        super().setUp()
        # The statute catalogue lives in its own folder; a test must never write into the real one.
        self.legal_dir = legal_catalogue.LEGAL_DIR
        legal_catalogue.LEGAL_DIR = api.DATA_DIR / 'public-catalogue'
        legal_catalogue.init_catalogue()
        os.environ['NULEGAL_IN_TESTS'] = '1'
        nulegal._cache.clear()

    def tearDown(self):
        os.environ.pop('NULEGAL_IN_TESTS', None)
        legal_catalogue.LEGAL_DIR = self.legal_dir
        super().tearDown()

    def test_citations_are_extracted_and_checked_without_other_answer_text(self):
        answer = ('Frau Müller aus der Lindenstraße 4 darf nach § 536 Abs. 1 BGB mindern (BGH, Urteil vom 05.12.2018 – VIII ZR 67/18). '
                  'Siehe auch BGH VIII ZR 999/99 und §§ 535 BGB.')
        found = nulegal.extract_citations(answer)
        self.assertIn('§ 536 Abs. 1 BGB', found)
        self.assertEqual(nulegal.extract_citations('nach § 312g Abs. 2 Nr. 1 BGB und § 356 Abs. 2 Nr. 1 lit. a BGB'), ['§ 312g Abs. 2 Nr. 1 BGB', '§ 356 Abs. 2 Nr. 1 lit. a BGB'])
        self.assertTrue(any('VIII ZR 67/18' in item for item in found))
        self.assertTrue(any('VIII ZR 999/99' in item for item in found))
        sent = {}

        def call(method, path, params=None, body=None):
            sent['body'] = body
            return {'results': [{'input': body['citations'][0], 'status': 'resolved', 'citation_kind': 'norm'},
                                {'input': 'BGH VIII ZR 999/99', 'status': 'unknown', 'citation_kind': 'docket'},
                                {'input': 'BGH VIII ZR 67/18', 'status': 'resolved', 'citation_kind': 'docket', 'citation_check': {'date_matches': False, 'actual_date': '2018-12-05'}}]}
        with patch.object(nulegal, '_call', side_effect=call):
            checked = nulegal.check_citations(answer)
        self.assertEqual([item['status'] for item in checked], ['resolved', 'unknown', 'mismatch'])
        self.assertNotIn('Müller', json.dumps(sent['body'], ensure_ascii=False))
        self.assertNotIn('Lindenstraße', json.dumps(sent['body'], ensure_ascii=False))

    def test_research_gets_decisions_from_statute_headings_and_stores_citation_check(self):
        def norm(number, title, text):
            return f'<norm doknr="N{number}"><metadaten><enbez>§ {number}</enbez><titel>{title}</titel></metadaten><textdaten><text><Content><P>{text}</P></Content></text></textdaten></norm>'
        xml = ('<?xml version="1.0"?><dokumente><norm doknr="HEADER"><metadaten><jurabk>BGB</jurabk></metadaten></norm>'
               + norm('536', 'Mietminderung bei Sach- und Rechtsmängeln', 'Hat die Mietsache einen Mangel, ist die Miete herabgesetzt.') + '</dokumente>').encode()
        legal_catalogue.store_rows(legal_catalogue.parse_law(xml, 'bgb'), 'law:bgb')
        queries, prompts = [], []

        def call(method, path, params=None, body=None):
            if path == '/v1/case-search':
                queries.append(params['q'])
                return {'results': [DECISION], 'source': {'attribution': 'Source: nu:legal – recht.nulegal.eu'}}
            return {'results': [{'input': body['citations'][0], 'status': 'resolved', 'citation_kind': 'norm'}]}

        def answer(messages):
            prompts.append(messages[0]['content'])
            return {'answer': 'Die Miete ist nach § 536 BGB gemindert [L1], so auch der BGH [R1].', 'input_tokens': 1, 'output_tokens': 1, 'truncated': False}
        with TestClient(api.app) as client:
            self.login(client, 'nulegal@example.invalid')
            case_id = self.case(client)
            with patch.object(nulegal, '_call', side_effect=call), patch.object(api, 'generate_answer', side_effect=answer), patch.object(legal_catalogue, 'fetch_public', side_effect=AssertionError('no network')):
                run = client.post(f'/api/cases/{case_id}/research', json={'request_id': '6f1c2d4e-1111-4222-8333-444455556666', 'question': 'Frau Müller hat Schimmel im Schlafzimmer, darf sie mindern?', 'use_legal_catalogue': True})
            self.assertEqual(run.status_code, 201, run.text)
            report = run.json()['retrieval_report']
            self.assertTrue(run.json()['legal_sources'])
            self.assertEqual(report['case_law'][0]['aktenzeichen'], 'VIII ZR 67/18')
            self.assertEqual(report['case_law'][0]['citation_id'], 'R1')
            self.assertIn('VIII ZR 67/18', prompts[0])
            self.assertTrue(all('Müller' not in query and 'Schlafzimmer' not in query for query in queries))
            self.assertIn('schimmel', ' '.join(queries).lower())
            self.assertEqual(report['citation_check'][0]['status'], 'resolved')

    def test_letter_explanation_uses_kind_query_only(self):
        queries = []

        def call(method, path, params=None, body=None):
            if path == '/v1/case-search':
                queries.append(params['q'])
                return {'results': [DECISION]}
            return {'results': []}
        with TestClient(api.app) as client:
            self.login(client, 'nulegal-letter@example.invalid')
            body = {'kind': 'inkasso', 'fields': {'sender': 'Creditum', 'amount': 192.37}, 'answers': {}, 'text': 'Herr Beispiel, Sie schulden 192,37 EUR.'}
            with patch.object(nulegal, '_call', side_effect=call), patch.object(research, 'generate_answer', return_value={'answer': 'Siehe BGH VIII ZR 67/18 [R1].'}):
                result = client.post('/api/letter-assistant/explain', json=body).json()
        self.assertEqual(queries, [letter_ai.CASE_LAW_QUERY['inkasso']])
        self.assertEqual(result['case_law'][0]['citation_id'], 'R1')
        self.assertIn('citation_check', result)

    def test_offline_and_disabled_return_nothing(self):
        with patch.object(nulegal, '_call', side_effect=OSError):
            self.assertEqual(nulegal.case_search('Mietminderung'), [])
            self.assertEqual(nulegal.check_citations('§ 536 BGB'), [])
        os.environ.pop('NULEGAL_IN_TESTS', None)
        with patch.object(nulegal, '_call') as call:
            self.assertEqual(nulegal.case_search('Mietminderung'), [])
            call.assert_not_called()
