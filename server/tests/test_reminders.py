import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from server import app as api
from server import reminders
from server.tests import test_inbox


class ReminderTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_pre_and_last_reminder_once_each_and_opt_out(self):
        outbox = Path(tempfile.mkdtemp())
        previous = os.environ.get('MAIL_OUTBOX_DIR')
        os.environ['MAIL_OUTBOX_DIR'] = str(outbox)
        try:
            with TestClient(api.app) as client:
                self.login(client, 'reminder@example.invalid')
                case_id = self.case(client)
                today = date.today()
                due = today + timedelta(days=10)
                client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Widerspruch Mahnbescheid', 'due_on': due.isoformat(), 'kind': 'notfrist', 'pre_days': 7})
                done = client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Erledigte Sache', 'due_on': due.isoformat(), 'kind': 'deadline', 'pre_days': 7}).json()
                task = next(t for t in done['tasks'] if t['title'] == 'Erledigte Sache')
                client.put(f'/api/cases/{case_id}/tasks/{task["id"]}', json={'title': 'Erledigte Sache', 'due_on': due.isoformat(), 'kind': 'deadline', 'pre_days': 7, 'completed': True, 'completion_note': 'Widerspruch abgeschickt'})
                pre_day = date.fromisoformat(api.pre_deadline(due.isoformat(), 7))
                self.assertEqual(reminders.run(api.db, api.pre_deadline, pre_day - timedelta(days=1)), 0)
                self.assertEqual(reminders.run(api.db, api.pre_deadline, pre_day), 1)
                self.assertEqual(reminders.run(api.db, api.pre_deadline, pre_day), 0)  # never twice
                mails = list(outbox.glob('*.eml'))
                text = mails[0].read_bytes().decode('utf-8', 'replace')
                self.assertIn('Widerspruch Mahnbescheid', text)
                self.assertNotIn('Erledigte Sache', text)
                self.assertEqual(reminders.run(api.db, api.pre_deadline, due - timedelta(days=1)), 1)
                self.assertEqual(client.put('/api/reminders/settings', json={'enabled': False}).json()['enabled'], False)
                self.assertFalse(client.get('/api/reminders/settings').json()['enabled'])
                client.post(f'/api/cases/{case_id}/tasks', json={'title': 'Neue Frist', 'due_on': (today + timedelta(days=1)).isoformat(), 'kind': 'deadline'})
                self.assertEqual(reminders.run(api.db, api.pre_deadline, today), 0)
        finally:
            if previous is None:
                os.environ.pop('MAIL_OUTBOX_DIR', None)
            else:
                os.environ['MAIL_OUTBOX_DIR'] = previous
