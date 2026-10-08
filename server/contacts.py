"""Account-owned address book. Links never overwrite legacy case particulars."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

ContactKind = Literal['client', 'opponent', 'law_firm', 'court', 'authority', 'company', 'person', 'other']
CaseRole = Literal['client', 'opponent', 'counsel', 'court', 'authority', 'other']


class CaseLink(BaseModel):
    model_config = {'extra': 'forbid'}
    case_id: uuid.UUID
    role: CaseRole = 'other'


class ContactInput(BaseModel):
    model_config = {'extra': 'forbid'}
    name: str = Field(min_length=1, max_length=160)
    kind: ContactKind = 'person'
    attention: str = Field(default='', max_length=160)
    address: str = Field(default='', max_length=500)
    email: str = Field(default='', max_length=254)
    phone: str = Field(default='', max_length=80)
    note: str = Field(default='', max_length=2000)
    case_links: list[CaseLink] = Field(default_factory=list, max_length=200)

    @field_validator('name', 'attention', 'address', 'email', 'phone', 'note', mode='before')
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if any(ord(c) < 32 and c not in '\n\r\t' or ord(c) == 127 for c in value):
                raise ValueError('Control characters are not allowed')
        return value

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        if value and (value.count('@') != 1 or any(c.isspace() for c in value) or not all(value.split('@'))):
            raise ValueError('Invalid contact email')
        return value

    @model_validator(mode='after')
    def unique_cases(self):
        if len({item.case_id for item in self.case_links}) != len(self.case_links):
            raise ValueError('Duplicate case link')
        return self


class ContactUpdate(ContactInput):
    expected_version: int = Field(ge=1)


def migrate(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL, kind TEXT NOT NULL, attention TEXT NOT NULL,
            address TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
            note TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS contacts_owner ON contacts(user_id);
        CREATE TABLE IF NOT EXISTS contact_cases (
            contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            role TEXT NOT NULL, PRIMARY KEY(contact_id, case_id)
        );
    ''')


def public_contact(connection, row):
    links = connection.execute('''SELECT cc.case_id, cc.role, c.reference, c.title
        FROM contact_cases cc JOIN cases c ON c.id=cc.case_id
        WHERE cc.contact_id=? AND c.user_id=? ORDER BY c.reference''', (row['id'], row['user_id']))
    return {key: row[key] for key in row.keys() if key != 'user_id'} | {'case_links': [dict(link) for link in links]}


def router(db, require_user, now, record_activity):
    routes = APIRouter()

    def owned(connection, contact_id, user_id):
        row = connection.execute('SELECT * FROM contacts WHERE id=? AND user_id=?', (contact_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Contact not found')
        return row

    def validate_links(connection, links, user_id):
        for link in links:
            if not connection.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?', (str(link.case_id), user_id)).fetchone():
                raise HTTPException(404, 'Case not found')

    def set_links(connection, contact_id, links):
        connection.execute('DELETE FROM contact_cases WHERE contact_id=?', (contact_id,))
        connection.executemany('INSERT INTO contact_cases(contact_id,case_id,role) VALUES(?,?,?)', [(contact_id, str(link.case_id), link.role) for link in links])

    @routes.get('/api/contacts')
    def list_contacts(user: dict = Depends(require_user)):
        with db() as connection:
            return [public_contact(connection, row) for row in connection.execute('SELECT * FROM contacts WHERE user_id=? ORDER BY name COLLATE NOCASE,id', (user['id'],)).fetchall()]

    @routes.get('/api/contacts/{contact_id}')
    def read_contact(contact_id: str, user: dict = Depends(require_user)):
        with db() as connection:
            return public_contact(connection, owned(connection, contact_id, user['id']))

    @routes.post('/api/contacts', status_code=201)
    def create_contact(payload: ContactInput, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            validate_links(connection, payload.case_links, user['id'])
            contact_id, timestamp = str(uuid.uuid4()), now()
            connection.execute('''INSERT INTO contacts(id,user_id,name,kind,attention,address,email,phone,note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (contact_id, user['id'], payload.name, payload.kind, payload.attention, payload.address, payload.email, payload.phone, payload.note, timestamp, timestamp))
            set_links(connection, contact_id, payload.case_links)
            for link in payload.case_links:
                record_activity(connection, str(link.case_id), 'contact_linked', payload.name)
            return public_contact(connection, owned(connection, contact_id, user['id']))

    @routes.put('/api/contacts/{contact_id}')
    def update_contact(contact_id: str, payload: ContactUpdate, user: dict = Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            old = owned(connection, contact_id, user['id'])
            if old['version'] != payload.expected_version:
                raise HTTPException(409, 'Contact version changed')
            validate_links(connection, payload.case_links, user['id'])
            previous = {row['case_id']: row['role'] for row in connection.execute('SELECT case_id,role FROM contact_cases WHERE contact_id=?', (contact_id,))}
            current = {str(link.case_id): link.role for link in payload.case_links}
            connection.execute('''UPDATE contacts SET name=?,kind=?,attention=?,address=?,email=?,phone=?,note=?,version=version+1,updated_at=? WHERE id=? AND user_id=?''', (payload.name, payload.kind, payload.attention, payload.address, payload.email, payload.phone, payload.note, now(), contact_id, user['id']))
            set_links(connection, contact_id, payload.case_links)
            for case_id in previous.keys() | current.keys():
                action = 'contact_unlinked' if case_id not in current else 'contact_linked' if case_id not in previous else 'contact_updated'
                record_activity(connection, case_id, action, payload.name)
            return public_contact(connection, owned(connection, contact_id, user['id']))

    return routes
