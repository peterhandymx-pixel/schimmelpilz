import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app as api
from server import law_skills, letter_assistant, research
from server.tests import test_inbox


class LawSkillSelectionTests(unittest.TestCase):
    def test_all_skills_load_and_every_letter_kind_has_one(self):
        self.assertEqual(len(law_skills.index()), 319)
        for kind, skill_id in law_skills.KIND_SKILLS.items():
            self.assertIsNotNone(law_skills.find(skill_id), kind)
            self.assertIn(kind, letter_assistant.KIND_IDS)

    def test_questions_find_the_matching_expert_skill(self):
        cases = [('Darf ich wegen Schimmel die Miete mindern?', 'tenancy', 'mietrecht/mietmangel-minderung'),
                 ('Mein Vermieter zahlt die Kaution nicht zurück', 'tenancy', 'mietrecht/kaution-mietsicherheit'),
                 ('Mein Chef hat mir gekündigt, was kann ich tun?', 'employment', 'arbeitsrecht/kuendigungs-pruefung'),
                 ('Ist die Forderung verjährt?', 'contract', 'vertragsrecht/verjaehrung-pruefung'),
                 ('Was kann ich gegen die Nebenkostenabrechnung tun?', 'tenancy', 'mietrecht/betriebskostenabrechnung')]
        for question, area, expected in cases:
            self.assertEqual(law_skills.select(question, [], area)['id'], expected, question)
        self.assertIsNone(law_skills.select('Wie wird das Wetter morgen?', [], 'general'))
        self.assertEqual(law_skills.select('', ['§ 536 BGB · Mietminderung bei Sach- und Rechtsmängeln'], 'tenancy')['id'], 'mietrecht/mietmangel-minderung')

    def test_instructions_are_bounded_and_without_frontmatter(self):
        text = law_skills.instructions(law_skills.find('mietrecht/mietmangel-minderung'))
        self.assertLessEqual(len(text), law_skills.LIMIT + 20)
        self.assertNotIn('provider_variants', text)
        self.assertNotIn('Sub-Agent-Architektur', text)
        self.assertIn('536', text)


class LawSkillApiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_research_and_letter_explanation_receive_the_skill(self):
        prompts = []

        def answer(messages):
            prompts.append(messages[0]['content'])
            return {'answer': 'Antwort.', 'input_tokens': 1, 'output_tokens': 1, 'truncated': False}
        with TestClient(api.app) as client:
            self.login(client, 'skills@example.invalid')
            case = client.post('/api/cases', json={'title': 'Synthetic tenancy case', 'description': 'Only synthetic testing, no real client data.', 'details': {'legal_area': 'tenancy'}}).json()
            with patch.object(api, 'generate_answer', side_effect=answer):
                run = client.post(f"/api/cases/{case['id']}/research", json={'request_id': '0a1b2c3d-1111-4222-8333-444455556666', 'question': 'Darf ich wegen Schimmel die Miete mindern?'})
            self.assertEqual(run.status_code, 201, run.text)
            self.assertEqual(run.json()['retrieval_report']['skill']['id'], 'mietrecht/mietmangel-minderung')
            self.assertIn('EXPERT WORKING INSTRUCTIONS', prompts[-1])
            with patch.object(research, 'generate_answer', side_effect=answer):
                explained = client.post('/api/letter-assistant/explain', json={'kind': 'mahnbescheid', 'fields': {}, 'answers': {}, 'text': ''}).json()
            self.assertEqual(explained['skill']['id'], 'prozessrecht/mahnverfahren')
            self.assertIn('Fachliche Arbeitsanleitung', prompts[-1])
