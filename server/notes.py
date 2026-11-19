"""Telephone and meeting notes in the case file: who, when, how long, what was discussed; optionally a follow-up date.

A note is recorded in the case activity and found by the full-text search. A follow-up creates a Wiedervorlage task.
"""
import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

KINDS = {'call_in': 'Anruf eingehend', 'call_out': 'Anruf ausgehend', 'meeting': 'Besprechung', 'video': 'Videogespräch', 'other': 'Notiz'}


def migrate(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS case_notes(id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL, kind TEXT NOT NULL, person TEXT NOT NULL DEFAULT '', happened_at TEXT NOT NULL, minutes INTEGER,
        note TEXT NOT NULL, recorded_by TEXT, created_at TEXT NOT NULL)''')
    connection.execute('CREATE INDEX IF NOT EXISTS case_notes_case ON case_notes(case_id, happened_at)')


class NoteInput(BaseModel):
    model_config = {'extra': 'forbid'}
    kind: Literal['call_in', 'call_out', 'meeting', 'video', 'other'] = 'call_in'
    person: str = Field(default='', max_length=200)
    happened_at: datetime
    minutes: int | None = Field(default=None, ge=1, le=600)
    note: str = Field(min_length=3, max_length=10000)
    follow_up_on: date | None = None
    follow_up_title: str = Field(default='', max_length=200)

    @field_validator('person', 'note', 'follow_up_title', mode='before')
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


def router(db, require_user, now, record_activity):
    routes = APIRouter()

    def owned(connection, case_id, user):
        allowed = user.get('allowed_cases')
        row = connection.execute('SELECT id FROM cases WHERE id=? AND user_id=?', (case_id, user['id'])).fetchone()
        if not row or (allowed is not None and case_id not in allowed):
            raise HTTPException(404, 'Case not found')

    def listing(connection, case_id):
        return [dict(row) | {'kind_label': KINDS.get(row['kind'], 'Notiz')} for row in
                connection.execute('SELECT id, kind, person, happened_at, minutes, note, created_at FROM case_notes WHERE case_id=? ORDER BY happened_at DESC, created_at DESC', (case_id,))]

    @routes.get('/api/cases/{case_id}/notes')
    def list_notes(case_id: str, user: dict = Depends(require_user)):
        with db() as connection:
            owned(connection, case_id, user)
            return listing(connection, case_id)

    @routes.post('/api/cases/{case_id}/notes', status_code=201)
    def add_note(case_id: str, payload: NoteInput, user: dict = Depends(require_user)):
        with db() as connection:
            owned(connection, case_id, user)
            happened = payload.happened_at.replace(tzinfo=None).isoformat(timespec='minutes')
            connection.execute('INSERT INTO case_notes VALUES(?,?,?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), case_id, user['id'], payload.kind, payload.person,
                                                                                    happened, payload.minutes, payload.note, user.get('actor_id', user['id']), now()))
            label = KINDS[payload.kind] + (f' mit {payload.person}' if payload.person else '')
            record_activity(connection, case_id, 'note_recorded', f'{label}: {payload.note[:120]}')
            if payload.follow_up_on:
                title = payload.follow_up_title or f'Wiedervorlage: {label}'
                connection.execute('INSERT INTO tasks(id, case_id, title, note, due_on, priority, created_at, kind, due_time, pre_days) VALUES (?,?,?,?,?,?,?,?,?,?)',
                                   (str(uuid.uuid4()), case_id, title[:200], payload.note[:2000], payload.follow_up_on.isoformat(), 'normal', now(), 'resubmission', None, 0))
            return listing(connection, case_id)

    @routes.delete('/api/cases/{case_id}/notes/{note_id}', status_code=204)
    def remove_note(case_id: str, note_id: str, user: dict = Depends(require_user)):
        if user.get('workspace_role', 'owner') != 'owner':
            raise HTTPException(403, 'workspace_owner_required_for_deletion')
        with db() as connection:
            owned(connection, case_id, user)
            if not connection.execute('DELETE FROM case_notes WHERE id=? AND case_id=?', (note_id, case_id)).rowcount:
                raise HTTPException(404, 'Not found')
            record_activity(connection, case_id, 'note_deleted', '')
        return Response(status_code=204)

    return routes
