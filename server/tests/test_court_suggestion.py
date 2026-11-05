import unittest
from unittest.mock import patch

from server import court_lookup

COURTS = {'courts': [{'name': 'Amtsgericht Köln', 'street': ['Luxemburger Straße 101', '50939 Köln'], 'postal': ['50922 Köln']},
                     {'name': 'Landgericht Köln', 'street': ['Luxemburger Straße 101', '50939 Köln'], 'postal': ['50922 Köln']},
                     {'name': 'Sozialgericht Köln', 'street': ['Blumenthalstraße 33', '50670 Köln'], 'postal': []},
                     {'name': 'Arbeitsgericht Köln', 'street': ['Blumenthalstraße 33', '50670 Köln'], 'postal': []}], 'choices': [], 'notice': ''}


class CourtSuggestionTests(unittest.TestCase):
    def suggest(self, details, area=None):
        with patch.object(court_lookup, 'lookup', return_value=COURTS) as lookup:
            result = court_lookup.suggest(details, area)
        return result, lookup

    def test_civil_value_decides_between_local_and_regional_court(self):
        small, lookup = self.suggest({'opponent_address': 'Musterweg 2\n50667 Köln', 'dispute_value': 10000})
        self.assertEqual(small['name'], 'Amtsgericht Köln')
        self.assertIn('§ 23 Nr. 1 GVG', small['basis'])
        lookup.assert_called_with('zivil', '50667', 'Köln')
        large, _ = self.suggest({'opponent_address': 'Musterweg 2\n50667 Köln', 'dispute_value': 10000.01})
        self.assertEqual(large['name'], 'Landgericht Köln')
        self.assertIn('§ 71 Abs. 1, § 23 Nr. 1 GVG', large['basis'])
        unknown, _ = self.suggest({'opponent_address': 'Musterweg 2\n50667 Köln'})
        self.assertEqual(unknown['name'], 'Amtsgericht Köln')
        self.assertIn('Streitwert nicht erfasst', unknown['basis'])

    def test_tenancy_social_and_labour_use_their_court_and_address(self):
        tenancy, lookup = self.suggest({'client_address': 'Testweg 1\n50667 Köln', 'opponent_address': 'Fern 1\n80331 München', 'legal_area': 'tenancy', 'dispute_value': 50000})
        self.assertEqual(tenancy['name'], 'Amtsgericht Köln')
        self.assertIn('§ 29a', tenancy['basis'])
        lookup.assert_called_with('zivil', '50667', 'Köln')
        social, lookup = self.suggest({'client_address': 'Testweg 1\n50667 Köln', 'opponent_address': 'Amt 1\n45130 Essen'}, 'social')
        self.assertEqual(social['name'], 'Sozialgericht Köln')
        lookup.assert_called_with('sozial', '50667', 'Köln')
        labour, lookup = self.suggest({'opponent_address': 'Firma\n50667 Köln', 'legal_area': 'employment'})
        self.assertEqual(labour['name'], 'Arbeitsgericht Köln')
        lookup.assert_called_with('arbeit', '50667', 'Köln')

    def test_missing_address_is_reported_never_guessed(self):
        result, lookup = self.suggest({'opponent_name': 'X GmbH'})
        self.assertFalse(result['ok'])
        self.assertIn('Anschrift der Gegenseite', result['message'])
        lookup.assert_not_called()
