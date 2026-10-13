import unittest
from server.calendar_export import calendar,fold
from server.tests import test_case_tools
from fastapi.testclient import TestClient
from server import app as api


class CalendarUnitTests(unittest.TestCase):
    def test_dates_alarms_escaping_and_utf8_folding(self):
        data=calendar([{'uid':'test','due_on':'2026-10-31','title':'Ä'*70+'\nBEGIN:VEVENT','note':'Text, with; separators\\ and\nlines'}],'20261013T120000Z',3)
        raw=data.decode('utf-8');unfolded=raw.replace('\r\n ','')
        self.assertIn('DTSTART;VALUE=DATE:20261031',raw)
        self.assertIn('DTEND;VALUE=DATE:20261101',raw)
        self.assertIn('TRIGGER:-P3D',raw)
        self.assertEqual(unfolded.count('\r\nBEGIN:VEVENT\r\n'),1)
        self.assertIn('\\nBEGIN:VEVENT',unfolded)
        self.assertIn('Text\\, with\\; separators\\\\ and\\nlines',unfolded)
        self.assertTrue(all(len(line)<=75 for line in data.split(b'\r\n')))
        self.assertNotIn('VALARM',calendar([{'uid':'test','due_on':'2026-10-31','title':'Test','note':''}],'20261013T120000Z',0).decode())


class CalendarApiTests(test_case_tools.CaseToolsTests):
    # Reuse isolated database helpers without rerunning inherited case-tool tests.
    test_archive_restore_version_and_persistence=None
    test_export_originals_versions_hashes_and_isolation=None
    test_export_fails_for_missing_or_unsafe_original=None

    def test_owned_open_dates_archived_filter_and_alarm_validation(self):
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'calendar-foreign@example.invalid')
            case=self.case(owner)
            endpoint='/api/tasks/calendar.ics'
            owner.post(f'/api/cases/{case["id"]}/tasks',json={'title':'Calendar task ÄÖÜ','due_on':'2026-10-15','note':'Synthetic date'})
            owner.post(f'/api/cases/{case["id"]}/tasks',json={'title':'Undated task'})
            data=owner.get(endpoint).content.decode()
            self.assertIn('Calendar task ÄÖÜ',data)
            self.assertNotIn('Undated task',data)
            self.assertNotIn('Calendar task',other.get(endpoint).content.decode())
            self.assertEqual(other.get(endpoint+'?case_id='+case['id']).status_code,404)
            self.assertEqual(owner.get(endpoint+'?alarm_days=31').status_code,422)
            owner.put(f'/api/cases/{case["id"]}/archive',json={'archived':True,'expected_version':0})
            self.assertNotIn('Calendar task',owner.get(endpoint).content.decode())
            self.assertIn('Calendar task',owner.get(endpoint+'?case_id='+case['id']).content.decode())


if __name__=='__main__':
    unittest.main()
