"""Every letter kind of the letter assistant, followed through to the court a claim would go to.

A wrong court type (e.g. administrative court for a disability decision) is a serious error, so each kind
has its expected court spelled out here; a new kind without an entry fails this test.
"""
import unittest
from unittest.mock import patch

from server import court_lookup, letter_assistant as la

DIRECTORY = {'courts': [{'name': f'{prefix} Köln', 'street': ['Weg 1', '50667 Köln'], 'postal': []} for prefix in
                        ('Amtsgericht', 'Landgericht', 'Arbeitsgericht', 'Sozialgericht', 'Verwaltungsgericht', 'Finanzgericht')], 'choices': [], 'notice': ''}
DETAILS = {'client_address': 'Kläger 1\n50667 Köln', 'opponent_address': 'Gegner 2\n50667 Köln', 'dispute_value': 2000}

# kind -> expected first-instance court, or None where no claim exists (objection instead)
EXPECTED = {
    'gerichtsvollzieher': 'Amtsgericht', 'pfaendung': 'Amtsgericht', 'vollstreckungsbescheid': 'Amtsgericht', 'mahnbescheid': 'Amtsgericht',
    'klage': 'Amtsgericht', 'strafbefehl': None, 'bussgeld': None, 'anhoerung': None,
    'betriebspruefung': 'Finanzgericht', 'steuerbescheid': 'Finanzgericht', 'bescheid': 'Verwaltungsgericht',
    'abmahnung_urheber': 'Amtsgericht', 'abmahnung_arbeit': 'Arbeitsgericht', 'eigenkuendigung': 'Arbeitsgericht', 'kuendigung_arbeit': 'Arbeitsgericht',
    'kuendigung_wohnung': 'Amtsgericht', 'mieterhoehung': 'Amtsgericht', 'betriebskosten': 'Amtsgericht',
    'versicherung_ablehnung': 'Amtsgericht', 'inkasso': 'Amtsgericht', 'zahlungsaufforderung': 'Amtsgericht', 'sonstiges': 'Amtsgericht',
}

# Authorities whose decisions belong to the social courts (§ 51 SGG), not the administrative courts.
SOCIAL_AUTHORITIES = ['Versorgungsamt Köln', 'Jobcenter Köln', 'Agentur für Arbeit Köln', 'Deutsche Rentenversicherung Bund', 'AOK Rheinland Krankenkasse',
                      'Pflegekasse', 'Sozialamt der Stadt Köln', 'Berufsgenossenschaft Holz', 'Elterngeldstelle', 'Wohngeldstelle']


class CourtMatrixTests(unittest.TestCase):
    def court(self, legal_area, details=DETAILS):
        with patch.object(court_lookup, 'lookup', return_value=DIRECTORY):
            return court_lookup.suggest({**details, 'legal_area': legal_area})

    def test_every_letter_kind_has_an_expected_court(self):
        self.assertEqual(set(EXPECTED), set(la.KIND_IDS), 'a letter kind is missing from the court matrix')
        for kind, expected in EXPECTED.items():
            result = self.court(la.KIND_INFO[kind]['legal_area'])
            if expected is None:
                self.assertFalse(result['ok'], kind)
                self.assertIn('Einspruch', result['message'], kind)
            else:
                self.assertTrue(result['ok'], kind)
                self.assertEqual(result['name'], f'{expected} Köln', kind)

    def test_social_authority_decisions_go_to_the_social_court(self):
        for authority in SOCIAL_AUTHORITIES:
            text = f'{authority}\nBescheid\nRechtsbehelfsbelehrung: Gegen diesen Bescheid kann Widerspruch erhoben werden.'
            kind, _ = la.classify(text)
            self.assertEqual((kind['id'], kind['legal_area']), ('bescheid', 'social'), authority)
            self.assertEqual(self.court(kind['legal_area'])['name'], 'Sozialgericht Köln', authority)

    def test_other_authority_decisions_go_to_the_administrative_court(self):
        for authority in ['Stadt Köln – Bauaufsichtsamt', 'Landratsamt Starnberg – Führerscheinstelle', 'Gemeinde Remagen – Ordnungsamt']:
            kind, _ = la.classify(f'{authority}\nBescheid\nRechtsbehelfsbelehrung: Widerspruch innerhalb eines Monats.')
            self.assertEqual(kind['legal_area'], 'administrative', authority)
            self.assertEqual(self.court(kind['legal_area'])['name'], 'Verwaltungsgericht Köln', authority)

    def test_tax_and_family_matters(self):
        kind, _ = la.classify('Finanzamt Köln-Mitte\nEinkommensteuerbescheid 2024\nRechtsbehelfsbelehrung: Einspruch')
        self.assertEqual((kind['id'], kind['legal_area']), ('steuerbescheid', 'tax'))
        tax = self.court('tax')
        self.assertEqual(tax['name'], 'Finanzgericht Köln')
        self.assertIn('§ 38 Abs. 1 FGO', tax['basis'])
        family = self.court('family')
        self.assertEqual(family['name'], 'Amtsgericht Köln')
        self.assertIn('Familiengericht', family['basis'])

    def test_value_threshold_and_tenancy_exception(self):
        self.assertEqual(self.court('contract', {**DETAILS, 'dispute_value': 10000})['name'], 'Amtsgericht Köln')
        self.assertEqual(self.court('contract', {**DETAILS, 'dispute_value': 10001})['name'], 'Landgericht Köln')
        self.assertEqual(self.court('tenancy', {**DETAILS, 'dispute_value': 90000})['name'], 'Amtsgericht Köln')
