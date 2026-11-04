from fastapi.testclient import TestClient
from server import app as api
from server.tests import test_inbox


class DeadlineControlTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def task(self, case, title):
        return next(item for item in case['tasks'] if item['title'] == title)

    def test_pre_deadline_moves_to_the_previous_working_day(self):
        self.assertEqual(api.pre_deadline('2026-12-28', 7), '2026-12-21')    # Monday → Monday
        self.assertEqual(api.pre_deadline('2027-01-08', 7), '2026-12-31')    # 1 January is a holiday → Thursday before
        self.assertEqual(api.pre_deadline('2026-11-16', 1), '2026-11-13')    # Sunday → Friday
        self.assertIsNone(api.pre_deadline('2026-11-16', 0))
        self.assertIsNone(api.pre_deadline(None, 7))

    def test_kinds_times_and_controlled_completion(self):
        with TestClient(api.app) as client:
            self.login(client)
            case_id = self.case(client)
            # Dated kinds need a date; a deadline gets a one-week pre-deadline by default.
            self.assertEqual(client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Berufungsfrist', 'kind': 'notfrist'}).status_code, 422)
            case = client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Berufungsfrist', 'kind': 'notfrist', 'due_on': '2027-01-08'}).json()
            deadline = self.task(case, 'Berufungsfrist')
            self.assertEqual((deadline['kind'], deadline['pre_days'], deadline['pre_due_on']), ('notfrist', 7, '2026-12-31'))
            case = client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Gütetermin', 'kind': 'appointment', 'due_on': '2026-12-02', 'due_time': '09:30'}).json()
            self.assertEqual(self.task(case, 'Gütetermin')['due_time'], '09:30')
            case = client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Akte ansehen', 'due_time': '10:00'}).json()
            self.assertIsNone(self.task(case, 'Akte ansehen')['due_time'])
            self.assertEqual(client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Termin', 'kind': 'appointment', 'due_on': '2026-12-02', 'due_time': '25:00'}).status_code, 422)

            # A deadline is struck off only with a note on how it was met; the person is recorded.
            body = {'title': 'Berufungsfrist', 'kind': 'notfrist', 'due_on': '2027-01-08', 'priority': 'high', 'completed': True}
            self.assertEqual(client.put(f'/api/cases/{case_id}/tasks/{deadline["id"]}', json=body).json()['detail'], 'completion_note_required')
            case = client.put(f'/api/cases/{case_id}/tasks/{deadline["id"]}', json={**body, 'completion_note': 'Berufung am 05.01. eingelegt'}).json()
            done = self.task(case, 'Berufungsfrist')
            self.assertTrue(done['completed'])
            self.assertEqual(done['completion_note'], 'Berufung am 05.01. eingelegt')
            self.assertTrue(done['completed_by'])
            # Reopening clears the record.
            case = client.put(f'/api/cases/{case_id}/tasks/{deadline["id"]}', json={**body, 'completed': False}).json()
            self.assertEqual((self.task(case, 'Berufungsfrist')['completed_by'], self.task(case, 'Berufungsfrist')['completion_note']), (None, ''))

            calendar = client.get('/api/tasks/calendar.ics').content.decode()
            self.assertIn('VORFRIST', calendar)
            self.assertIn('NOTFRIST', calendar)
            self.assertIn('DTSTART:20261202T093000', calendar)
