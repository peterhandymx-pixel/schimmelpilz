"""The office's own text blocks (Textbausteine), inserted into drafts with case data filled in by the editor."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator


class Snippet(BaseModel):
    model_config = {'extra': 'forbid'}
    title: str = Field(min_length=2, max_length=120)
    category: str = Field(default='', max_length=60)
    body: str = Field(min_length=2, max_length=10000)

    @field_validator('title', 'category', 'body')
    @classmethod
    def stripped(cls, value):
        return value.strip()


def migrate(c):
    c.execute('CREATE TABLE IF NOT EXISTS text_snippets(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)')


def router(db, require_user, now):
    r = APIRouter()

    def listing(c, user):
        return [dict(row) for row in c.execute('SELECT id,title,category,body,updated_at FROM text_snippets WHERE user_id=? ORDER BY category,title', (user['id'],))]

    @r.get('/api/snippets')
    def all_snippets(user: dict = Depends(require_user)):
        with db() as c:
            return listing(c, user)

    @r.post('/api/snippets', status_code=201)
    def create(payload: Snippet, user: dict = Depends(require_user)):
        with db() as c:
            if c.execute('SELECT COUNT(*) FROM text_snippets WHERE user_id=?', (user['id'],)).fetchone()[0] >= 500:
                raise HTTPException(409, 'too_many_snippets')
            c.execute('INSERT INTO text_snippets VALUES(?,?,?,?,?,?,?)', (str(uuid.uuid4()), user['id'], payload.title, payload.category, payload.body, now(), now()))
            return listing(c, user)

    @r.put('/api/snippets/{snippet_id}')
    def update(snippet_id: str, payload: Snippet, user: dict = Depends(require_user)):
        with db() as c:
            if not c.execute('UPDATE text_snippets SET title=?,category=?,body=?,updated_at=? WHERE id=? AND user_id=?', (payload.title, payload.category, payload.body, now(), snippet_id, user['id'])).rowcount:
                raise HTTPException(404, 'Not found')
            return listing(c, user)

    @r.delete('/api/snippets/{snippet_id}', status_code=204)
    def remove(snippet_id: str, user: dict = Depends(require_user)):
        with db() as c:
            if not c.execute('DELETE FROM text_snippets WHERE id=? AND user_id=?', (snippet_id, user['id'])).rowcount:
                raise HTTPException(404, 'Not found')
        return Response(status_code=204)

    return r
