"""E-mail reminders for open deadlines and appointments: once at the Vorfrist and once on the day before the deadline.

One mail per person and day, collecting every due item. Sent items are recorded, so a restart never sends twice.
Runs in a background thread when mail is configured; people can switch reminders off in their account.
"""
import os
import sys
import threading
import time
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import mailer

DATED_KINDS = ('deadline', 'notfrist', 'appointment', 'resubmission', 'task')
KIND_LABEL = {'deadline': 'Frist', 'notfrist': 'Notfrist', 'appointment': 'Termin', 'resubmission': 'Wiedervorlage', 'task': 'Aufgabe'}


def migrate(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS task_reminders(task_id TEXT NOT NULL, stage TEXT NOT NULL, sent_on TEXT NOT NULL, PRIMARY KEY(task_id, stage))')
    connection.execute('CREATE TABLE IF NOT EXISTS reminder_settings(user_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1)')


def german(day):
    return day.strftime('%d.%m.%Y')


def due_items(connection, today, pre_deadline):
    """[(user_row, task_row, stage)] for everything that needs a reminder today."""
    rows = connection.execute('''SELECT t.id, t.title, t.due_on, t.due_time, t.kind, t.pre_days, c.title AS case_title, c.reference, u.id AS user_id, u.email, u.full_name
        FROM tasks t JOIN cases c ON c.id = t.case_id JOIN users u ON u.id = c.user_id
        LEFT JOIN reminder_settings s ON s.user_id = u.id
        WHERE t.completed = 0 AND t.due_on IS NOT NULL AND c.archived_at IS NULL AND COALESCE(s.enabled, 1) = 1''').fetchall()
    sent = {(row['task_id'], row['stage']) for row in connection.execute('SELECT task_id, stage FROM task_reminders')}
    found = []
    for row in rows:
        due = date.fromisoformat(row['due_on'])
        if due < today:
            continue
        pre = pre_deadline(row['due_on'], row['pre_days'])
        if (due - today).days <= 1 and (row['id'], 'last') not in sent:
            found.append((row, 'last'))
        elif pre and date.fromisoformat(pre) <= today and (row['id'], 'pre') not in sent and (row['id'], 'last') not in sent:
            found.append((row, 'pre'))
    return found


def message(name, items, today, link):
    lines = [f'Guten Tag {name},', '', 'hier Ihre Erinnerung an anstehende Fristen und Termine:', '']
    for row, stage in sorted(items, key=lambda item: item[0]['due_on']):
        due = date.fromisoformat(row['due_on'])
        left = (due - today).days
        when = 'HEUTE' if left == 0 else 'morgen' if left == 1 else f'in {left} Tagen'
        time_text = f' um {row["due_time"]} Uhr' if row['due_time'] else ''
        lines.append(f'• {KIND_LABEL.get(row["kind"], "Frist")}: {row["title"]}')
        lines.append(f'  am {german(due)}{time_text} ({when}) – Akte {row["reference"]}: {row["case_title"]}')
        lines.append('')
    if link:
        lines += [f'Zur Übersicht: {link}', '']
    lines += ['Erledigte Fristen können Sie in der App abhaken, dann kommt keine weitere Erinnerung.', '', 'Rechtsassistentin Schimmelpilz',
              'Erinnerungen abschalten: Mein Konto → Erinnerungen per E-Mail.']
    return '\n'.join(lines)


def run(db, pre_deadline, today=None):
    """Sends today's reminders. Returns the number of mails sent."""
    if not mailer.configured():
        return 0
    today = today or date.today()
    link = os.getenv('PUBLIC_APP_URL', '').strip().rstrip('/')
    with db() as connection:
        items = due_items(connection, today, pre_deadline)
    by_user = {}
    for row, stage in items:
        by_user.setdefault(row['user_id'], []).append((row, stage))
    sent = 0
    for _user_id, entries in by_user.items():
        first = entries[0][0]
        urgent = any(stage == 'last' for _row, stage in entries)
        subject = ('Frist läuft morgen ab' if urgent else 'Erinnerung an Ihre Fristen') + f' ({len(entries)})'
        try:
            mailer.send(first['email'], subject, message(first['full_name'], entries, today, link))
        except Exception:
            continue
        with db() as connection:
            connection.executemany('INSERT OR IGNORE INTO task_reminders(task_id, stage, sent_on) VALUES (?,?,?)', [(row['id'], stage, today.isoformat()) for row, stage in entries])
        sent += 1
    return sent


def start(db, pre_deadline, interval=3600):
    """Background loop; not started inside the test runner."""
    if 'pytest' in sys.modules or os.getenv('REMINDERS', 'on').lower() == 'off':
        return None

    def loop():
        time.sleep(30)
        while True:
            try:
                run(db, pre_deadline)
            except Exception:
                pass
            time.sleep(interval)

    thread = threading.Thread(target=loop, name='deadline-reminders', daemon=True)
    thread.start()
    return thread


class Settings(BaseModel):
    model_config = {'extra': 'forbid'}
    enabled: bool


def router(db, require_user):
    routes = APIRouter()

    @routes.get('/api/reminders/settings')
    def read_settings(user: dict = Depends(require_user)):
        with db() as connection:
            row = connection.execute('SELECT enabled FROM reminder_settings WHERE user_id=?', (user['id'],)).fetchone()
        return {'enabled': bool(row['enabled']) if row else True, 'mail_available': mailer.configured()}

    @routes.put('/api/reminders/settings')
    def save_settings(payload: Settings, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('INSERT INTO reminder_settings(user_id, enabled) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled', (user['id'], int(payload.enabled)))
        return {'enabled': payload.enabled, 'mail_available': mailer.configured()}

    return routes
