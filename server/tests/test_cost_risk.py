import io
from decimal import Decimal

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server import app as api, cost_risk
from server.tests import test_inbox


def amounts(result):
    return {item['id']: Decimal(item['amount']) for item in result['scenarios']}


def test_civil_first_instance_10000():
    result = cost_risk.calculate(Decimal('10000'), 'civil_first')
    # 1.0 fee 652.00 EUR (RVG 2025), court 1.0 fee 283.00 EUR (GKG 2025)
    assert result['base_fee_rvg'] == '652.00' and result['base_fee_court'] == '283.00'
    lines = [line['amount'] for line in result['own_lawyer']['lines']]
    assert lines == ['847.60', '782.40', '20.00', '313.50']           # 1.3 + 1.2 + flat rate, 19 % VAT on 1,650.00
    assert result['own_lawyer']['total'] == '1963.50'
    assert result['court']['amount'] == '849.00' and result['court']['settled_amount'] == '283.00'
    scenario = amounts(result)
    assert scenario['loss'] == Decimal('4776.00')                       # court + both lawyers
    assert scenario['win'] == Decimal('0')
    assert scenario['quota'] == Decimal('2388.00')                      # 50 % of everything (§ 92 ZPO)
    # Settlement: own lawyer with 1.0 settlement fee (652.00) -> 2302.00 net + VAT 437.38, plus half of the 1.0 court fee
    assert scenario['settlement'] == Decimal('2739.38') + Decimal('141.50')
    assert result['advance'] == '849.00'


def test_labour_court_and_vat_deductible():
    result = cost_risk.calculate(Decimal('10000'), 'labour_first', own_vat_deductible=True)
    scenario = amounts(result)
    assert result['own_lawyer']['total'] == '1650.00'                   # no VAT for a client who can deduct it
    assert scenario['win'] == Decimal('1650.00')                         # § 12a ArbGG: own lawyer even when winning
    assert scenario['loss'] == Decimal('566.00') + Decimal('1650.00')    # 2.0 court fee + own lawyer, never the other side's
    assert result['court']['settled_amount'] == '0.00' and result['advance'] == '0.00'


def test_brackets_and_limits():
    assert cost_risk.base_fees(Decimal('500.01'))[2] == 1000
    assert cost_risk.base_fees(Decimal('500000'))[2] == 500000
    for wrong in (Decimal('0'), Decimal('500000.01')):
        try:
            cost_risk.base_fees(wrong)
        except ValueError:
            continue
        raise AssertionError(wrong)


class CostRiskApiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_api_and_pdf(self):
        with TestClient(api.app) as client:
            self.assertIn(client.post('/api/cost-risk/calculate', json={'value': 10000}).status_code, (401, 403))
            self.login(client, 'costrisk@example.invalid')
            result = client.post('/api/cost-risk/calculate', json={'value': '10000', 'win_percent': 70}).json()
            self.assertEqual(Decimal(result['scenarios'][1]['amount']), Decimal('1432.80'))
            self.assertEqual(client.post('/api/cost-risk/calculate', json={'value': 600000}).status_code, 422)
            pdf = client.post('/api/cost-risk/report.pdf', json={'value': '10000', 'client_name': 'Anna Weber', 'reference': '12/26'})
            self.assertEqual(pdf.status_code, 200)
            text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
            self.assertIn('Prozesskostenrisiko', text)
            self.assertIn('4.776,00 €', text)
            self.assertIn('Anna Weber', text)
