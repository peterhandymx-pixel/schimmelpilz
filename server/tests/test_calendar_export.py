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
            # German by default, English on request.
            self.assertIn('Manuell erfasster Termin',data)
            self.assertIn('Manually recorded date',owner.get(endpoint+'?lang=en').content.decode())
            self.assertEqual(owner.get(endpoint+'?lang=fr').status_code,422)
            self.assertNotIn('Calendar task',other.get(endpoint).content.decode())
            self.assertEqual(other.get(endpoint+'?case_id='+case['id']).status_code,404)
            self.assertEqual(owner.get(endpoint+'?alarm_days=31').status_code,422)
            owner.put(f'/api/cases/{case["id"]}/archive',json={'archived':True,'expected_version':0})
            self.assertNotIn('Calendar task',owner.get(endpoint).content.decode())
            self.assertIn('Calendar task',owner.get(endpoint+'?case_id='+case['id']).content.decode())


if __name__=='__main__':
    unittest.main()


class DeadlineBookTests(test_case_tools.CaseToolsTests):
    test_archive_restore_version_and_persistence=None
    test_export_originals_versions_hashes_and_isolation=None
    test_export_fails_for_missing_or_unsafe_original=None

    def test_deadline_book_lists_open_deadlines_with_pre_deadline(self):
        import io
        from pypdf import PdfReader
        with TestClient(api.app) as owner,TestClient(api.app) as other:
            self.login(owner);self.login(other,'book-foreign@example.invalid')
            case=self.case(owner)
            owner.post(f'/api/cases/{case["id"]}/tasks',json={'title':'Berufungsfrist','due_on':'2026-12-14','kind':'notfrist','pre_days':7})
            owner.post(f'/api/cases/{case["id"]}/tasks',json={'title':'Stellungnahme','due_on':'2026-12-10','kind':'deadline'})
            owner.post(f'/api/cases/{case["id"]}/tasks',json={'title':'Mandant anrufen','due_on':'2026-12-11'})
            owner.post(f'/api/cases/{case["id"]}/tasks',json={'title':'Ausserhalb','due_on':'2027-06-01','kind':'deadline'})
            response=owner.get('/api/tasks/deadline-book.pdf?start=2026-12-01&end=2026-12-31')
            self.assertEqual(response.status_code,200)
            text=''.join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
            self.assertIn('Fristenbuch',text)
            self.assertIn('Berufungsfrist',text);self.assertIn('NOTFRIST',text)
            self.assertIn('Mo 07.12.2026',text)          # Vorfrist 7 days before Mon 14.12.
            self.assertLess(text.index('Stellungnahme'),text.index('Berufungsfrist'))
            self.assertNotIn('Mandant anrufen',text);self.assertNotIn('Ausserhalb',text)
            self.assertIn('2 offene Fristen',text)
            self.assertEqual(owner.get('/api/tasks/deadline-book.pdf?start=2026-12-31&end=2026-12-01').status_code,422)
            foreign=''.join(page.extract_text() for page in PdfReader(io.BytesIO(other.get('/api/tasks/deadline-book.pdf?start=2026-12-01&end=2026-12-31').content)).pages)
            self.assertNotIn('Berufungsfrist',foreign)
