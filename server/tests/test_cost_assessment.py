from decimal import Decimal

from fastapi.testclient import TestClient

from server import app as api, cost_assessment
from server.tests import test_inbox


def test_calculation_with_credit_vat_and_court_fees():
    payload = cost_assessment.AssessmentInput(value=Decimal('10000'), business_fee_rate=Decimal('1.3'), court_fees_paid=Decimal('849'),
                                              extra_costs=[{'label': 'Zeugenvorschuss', 'amount': '150'}])
    result = cost_assessment.calculate(payload)
    amounts = [line['amount'] for line in result['lawyer_lines']]
    # 1.3 x 652.00 = 847.60; credit 0.65 x 652.00 = 423.80; 1.2 x 652.00 = 782.40; flat rate 20.00; VAT 19 % of 1,226.20
    assert amounts == [Decimal('847.60'), Decimal('-423.80'), Decimal('782.40'), Decimal('20.00'), Decimal('232.98')]
    assert result['lawyer_total'] == Decimal('1459.18')
    assert result['total'] == Decimal('1459.18') + Decimal('849.00') + Decimal('150.00')


def test_credit_capped_and_vat_deductible():
    result = cost_assessment.calculate(cost_assessment.AssessmentInput(value=Decimal('10000'), business_fee_rate=Decimal('2.5'), vat_deductible=True, hearing=False))
    assert result['lawyer_lines'][1]['amount'] == Decimal('-489.00')          # at most 0.75
    assert all('Umsatzsteuer' not in line['label'] for line in result['lawyer_lines'])


class CostAssessmentApiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_draft_text(self):
        with TestClient(api.app) as client, TestClient(api.app) as other:
            self.login(client, 'kfa@example.invalid')
            case = client.post('/api/cases', json={'title': 'Werklohn', 'description': 'Synthetische Akte für den KFA.',
                                                   'details': {'client_name': 'Bernd Schulz', 'opponent_name': 'Müller Bau GmbH', 'court': 'Landgericht Köln, Luxemburger Straße 101, 50939 Köln', 'court_reference': '5 O 123/26'}}).json()
            result = client.post(f"/api/cases/{case['id']}/cost-assessment", json={'value': '10000', 'court_fees_paid': '849', 'title_date': '2026-11-02', 'cost_quota': 70}).json()
            body = result['body']
            self.assertTrue(body.startswith('Landgericht Köln\nLuxemburger Straße 101'))
            self.assertIn('KOSTENFESTSETZUNGSANTRAG', body)
            self.assertIn('auf Grund des Urteils vom 02.11.2026', body)
            self.assertIn('§ 104 Abs. 1 Satz 2 ZPO', body)
            self.assertIn('§ 106 ZPO', body)
            self.assertIn('Verauslagte Gerichtskosten: 849,00 €', body)
            self.assertIn('Gesamtbetrag: 2.812,50 €', body)                        # 1,963.50 + 849.00
            self.assertEqual(result['recipient'], 'Landgericht Köln, Luxemburger Straße 101, 50939 Köln')
            self.login(other, 'kfa-other@example.invalid')
            self.assertEqual(other.post(f"/api/cases/{case['id']}/cost-assessment", json={'value': '10000'}).status_code, 404)
