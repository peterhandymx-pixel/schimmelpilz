import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app as api, court_lookup
from server.tests import test_inbox

RESULT = '''<h5 class="mt-3">Gesucht wurde: <strong>Arbeitsgerichtssachen, 85221&nbsp;Dachau</strong></h5><hr>
<h6>Arbeitsgericht München</h6><div class="row clearfix"><div class="col-12 col-md-5">
<address><strong>Lieferanschrift</strong><br>Winzererstraße 106<br>80797 München<br></address>
<address><strong>Postanschrift</strong><br>Postfach 40 01 80<br>80701 München<br></address></div>
<div class="col-12 col-md-7"><address><strong>Kontakt</strong><br><span>Telefon:</span> 089 30619-0<br>
<span>Internet:</span> <a href="https://www.arbg.bayern.de/muenchen/" target="_blank">x</a><br></address>
<address><span>XJustiz-ID:</span> D6257<br></address></div></div><hr>
<h6>Landesarbeitsgericht München</h6><div><address><strong>Postanschrift</strong><br>Winzererstraße 106<br>80797 München<br></address></div>
<footer>'''

STREETS = '''<h4>Straßenauswahl</h4><p>20095 Hamburg gehört zum Bezirk des <a href="https://www.justizadressen.nrw.de/de/justiz/gericht?key=2!02!1!01!01&ang=nachlass&plz=20095&ort=Hamburg">Amtsgericht Hamburg</a>. Für einige Straßen bestehen jedoch abweichende Zuständigkeiten. Bitte wählen Sie die gesuchte Straße.</p>
<a href="https://www.justizadressen.nrw.de/de/justiz/gericht?key=2!02!1!01!08&ang=nachlass&plz=20095&ort=Hamburg&str=Klosterwall!U!1!23"><i class="fa fa-caret-right"></i> Klosterwall</a>'''


class CourtLookupTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_directory_page_is_read_into_courts_and_street_choices(self):
        courts = court_lookup.parse(RESULT)['courts']
        self.assertEqual([court['name'] for court in courts], ['Arbeitsgericht München', 'Landesarbeitsgericht München'])
        self.assertEqual(courts[0]['postal'], ['Postfach 40 01 80', '80701 München'])
        self.assertEqual(courts[0]['street'], ['Winzererstraße 106', '80797 München'])
        self.assertEqual((courts[0]['phone'], courts[0]['xjustiz_id']), ('089 30619-0', 'D6257'))
        streets = court_lookup.parse(STREETS)
        self.assertEqual(streets['courts'], [])
        self.assertIn('abweichende Zuständigkeiten', streets['notice'])
        self.assertEqual([choice['label'] for choice in streets['choices']], ['Amtsgericht Hamburg', 'Klosterwall'])
        self.assertTrue(all(court_lookup.CHOICE.match(choice['query']) for choice in streets['choices']))

    def test_lookup_route_validates_input_and_reports_an_unreachable_directory(self):
        with TestClient(api.app) as client:
            self.assertEqual(client.get('/api/courts/lookup', params={'area': 'arbeit', 'plz': '85221', 'ort': 'Dachau'}).status_code, 401)
            self.login(client)
            with patch.object(court_lookup, 'lookup', return_value={'courts': [], 'choices': [], 'notice': '', 'source': 'x', 'checked_at': '2026-11-03'}) as found:
                self.assertEqual(client.get('/api/courts/lookup', params={'area': 'arbeit', 'plz': '85221', 'ort': 'Dachau'}).status_code, 200)
                self.assertEqual(found.call_args.args[:3], ('arbeit', '85221', 'Dachau'))
            self.assertEqual(client.get('/api/courts/lookup', params={'area': 'unbekannt', 'plz': '85221', 'ort': 'Dachau'}).status_code, 422)
            self.assertEqual(client.get('/api/courts/lookup', params={'area': 'arbeit', 'plz': '8522', 'ort': 'Dachau'}).status_code, 422)
            # Only the directory's own parameters may come back as a choice, and only for the same subject area.
            self.assertEqual(client.get('/api/courts/lookup', params={'area': 'arbeit', 'choice': 'key=1&ang=arbeit&url=https://evil.example'}).status_code, 422)
            self.assertEqual(client.get('/api/courts/lookup', params={'area': 'arbeit', 'choice': 'key=1&ang=zivil&plz=85221'}).status_code, 422)
            with patch.object(court_lookup, 'lookup', side_effect=court_lookup.DirectoryUnavailable('down')):
                self.assertEqual(client.get('/api/courts/lookup', params={'area': 'arbeit', 'plz': '85221', 'ort': 'Dachau'}).json()['detail'], 'directory_unavailable')


if __name__ == '__main__':
    unittest.main()
