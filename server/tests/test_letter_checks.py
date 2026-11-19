import json
from datetime import date
from pathlib import Path

from server import check_letters, letter_assistant as la

LETTERS = {item['id']: item for item in json.loads(Path(check_letters.CHECKS).read_text(encoding='utf-8'))}


def test_payment_order_is_not_taken_for_an_enforcement_order():
    # A Mahnbescheid warns that a Vollstreckungsbescheid may follow; it must stay a Mahnbescheid (2-week Widerspruch, § 692 ZPO).
    assert la.classify(LETTERS['mahnbescheid']['text'])[0]['id'] == 'mahnbescheid'
    real = 'Amtsgericht Euskirchen\nVollstreckungsbescheid\nAuf der Grundlage des Mahnbescheids vom 01.10.2026 wird dieser Vollstreckungsbescheid erlassen.'
    assert la.classify(real)[0]['id'] == 'vollstreckungsbescheid'


def test_notice_without_objection_procedure_gets_claim_deadline():
    fields = la.read_fields(LETTERS['bauamt-ablehnung']['text'])
    assert fields['remedy'] == 'klage'
    outcome = la.evaluate('bescheid', {**fields, 'legal_area': 'administrative'}, {'received_on': '2026-11-04'}, today=date(2026, 11, 6))
    assert '§ 74 Abs. 1 VwGO' in outcome['deadline']['norm']
    assert outcome['samples'][0] == 'klage-verwaltungsgericht'
    social = la.read_fields(LETTERS['versorgungsamt-gdb']['text'])
    assert social['remedy'] == 'widerspruch'
    assert '§ 84 Abs. 1 SGG' in la.evaluate('bescheid', {**social, 'legal_area': 'social'}, {'received_on': '2026-11-04'}, today=date(2026, 11, 6))['deadline']['norm']


def test_every_check_letter_is_classified_correctly_by_the_rules_alone():
    # Without AI (quota, outage) the rule reading must still get every check letter right.
    wrong = {key: la.classify(item['text'])[0]['id'] for key, item in LETTERS.items() if la.classify(item['text'])[0]['id'] not in item['kind']}
    assert wrong == {}
