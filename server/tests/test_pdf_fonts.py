"""Every PDF the app generates embeds its fonts (§ 2 Abs. 1 ERVV) – checked with the same test the beA export uses."""
from decimal import Decimal

from server import calendar_export, claims, cost_risk, email_import, exports, forms, pdfa, retention
from server.letterheads import compose_pdf
from server.tests.test_email_import import sample_eml


def assert_embedded(data, label):
    report = pdfa.check(data)
    assert report['ok'], (label, report)
    assert report['fonts'] > 0, label


def test_all_generated_pdfs_embed_their_fonts():
    assert_embedded(calendar_export.deadline_book_pdf([{'due_on': '2026-11-20', 'pre_on': '2026-11-13', 'reference': '1/26', 'case_title': 'Test',
                                                         'title': 'Berufungsfrist', 'kind': 'notfrist', 'label': 'Notfrist'}], '2026-11-01', '2026-11-30', 'Kanzlei'), 'Fristenbuch')
    risk = cost_risk.calculate(Decimal('10000'), 'civil_first')
    assert_embedded(cost_risk.report_pdf(risk, cost_risk.RiskInput(value=Decimal('10000'), client_name='Anna Weber')), 'Kostenrisiko')
    assert_embedded(retention.protocol_pdf([{'reference': '1/26', 'title': 'Altakte', 'ended_on': '2018-01-01', 'retained_until': '2024-12-31',
                                             'documents': 2, 'destroyed_at': '2026-11-16T10:00:00'}], 'Kanzlei'), 'Vernichtungsprotokoll')
    assert_embedded(exports.blocks_pdf('Kostenprüfung', [('Title', 'Kostenprüfung'), ('Heading2', 'Prüfung'), ('BodyText', 'Text mit Umlauten äöü')]), 'Export')
    assert_embedded(email_import.mail_pdf(email_import.parse_eml(sample_eml()), '1/26', [], []), 'E-Mail')
    user = {'full_name': 'Dr. Test', 'organisation': 'Kanzlei', 'street': 'Weg 1', 'postal_code': '50667', 'city': 'Köln'}
    assert_embedded(compose_pdf(forms.body('vollmacht', {'reference': '1/26', 'title': 'Test', 'details': {}}, user), None,
                                {'top_mm': 20, 'bottom_mm': 20, 'left_mm': 25, 'right_mm': 20, 'font_size': 10.5}), 'Formular')
    case = {'reference': '1/26', 'title': 'Forderung'}
    data = {'as_of': '2026-11-16', 'entries': [{'day': '2026-10-01', 'text': 'Hauptforderung', 'amount': Decimal('1000')}], 'principal': Decimal('1000'),
            'interest': Decimal('12.34'), 'costs': Decimal('0'), 'total': Decimal('1012.34'), 'daily_interest': Decimal('0.22')}
    items = [{'kind': 'principal', 'description': 'Rechnung 1', 'booked_on': '2026-10-01', 'amount_minor': 100000, 'interest_mode': 'consumer', 'interest_rate': None, 'interest_from': '2026-10-02'}]
    assert_embedded(claims.report_pdf(case, data, items), 'Forderungsaufstellung')
