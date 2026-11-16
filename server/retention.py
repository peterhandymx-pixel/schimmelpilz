"""Retention of closed files and their destruction (§ 50 Abs. 1 BRAO): six years after the end of the calendar year
in which the mandate ended. The end is the archiving date unless a different date is recorded.

Destruction deletes the case with its documents (deletion.delete_case) and keeps a minimal protocol: reference, title,
dates, number of documents, who and when. Invoices and bookings stay untouched (§ 147 AO, § 257 HGB: up to ten years).
"""
import io
import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import deletion

YEARS = 6


def migrate(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS retention_dates(case_id TEXT PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE, ended_on TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS destruction_log(id TEXT PRIMARY KEY, user_id TEXT NOT NULL, reference TEXT NOT NULL, title TEXT NOT NULL, ended_on TEXT NOT NULL,
            retained_until TEXT NOT NULL, documents INTEGER NOT NULL, destroyed_at TEXT NOT NULL, destroyed_by TEXT NOT NULL);
    ''')


def retained_until(ended_on: date) -> date:
    return date(ended_on.year + YEARS, 12, 31)


class EndDate(BaseModel):
    model_config = {'extra': 'forbid'}
    ended_on: date


class Destroy(BaseModel):
    model_config = {'extra': 'forbid'}
    confirm: str = Field(min_length=1, max_length=100)


def protocol_pdf(entries, firm):
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=8.8, leading=11, textColor=colors.HexColor('#1f2d26'))
    bold = ParagraphStyle('bold', parent=base, fontName='Helvetica-Bold')
    small = ParagraphStyle('small', parent=base, fontSize=8, textColor=colors.HexColor('#5d6b60'))
    title = ParagraphStyle('title', parent=base, fontName='Helvetica-Bold', fontSize=15, leading=19, spaceAfter=3)
    cell = lambda text, style=base: Paragraph(escape(str(text)), style)
    when = lambda value: date.fromisoformat(value[:10]).strftime('%d.%m.%Y')
    rows = [[cell(text, bold) for text in ('Aktenzeichen', 'Bezeichnung', 'Mandat beendet', 'Aufbewahrt bis', 'Dokumente', 'Vernichtet am')]]
    rows += [[cell(item['reference']), cell(item['title']), cell(when(item['ended_on'])), cell(when(item['retained_until'])), cell(item['documents']), cell(when(item['destroyed_at']))] for item in entries]
    table = Table(rows, colWidths=[32 * mm, None, 24 * mm, 24 * mm, 18 * mm, 24 * mm], repeatRows=1)
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#2f5d4d')),
                               ('LINEBELOW', (0, 1), (-1, -1), 0.3, colors.HexColor('#c9d3cc')), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story = [Paragraph('Vernichtungsprotokoll', title), cell(f'{firm} · Stand {date.today().strftime("%d.%m.%Y")} · {len(entries)} Akten', small), Spacer(1, 6),
             table if entries else cell('Bisher wurden keine Akten vernichtet.'), Spacer(1, 10),
             cell('Vernichtet wurden die elektronischen Handakten einschließlich aller Dokumente, Entwürfe, Fristen und Notizen nach Ablauf der Aufbewahrungsfrist '
                  'von sechs Jahren (§ 50 Abs. 1 BRAO). Rechnungen und Buchungen bleiben nach § 147 AO, § 257 HGB gesondert erhalten.', small),
             Spacer(1, 30), cell('______________________________', base), cell('Datum, Unterschrift', small)]
    output = io.BytesIO()
    SimpleDocTemplate(output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title='Vernichtungsprotokoll', author='').build(story)
    return output.getvalue()


def router(db, require_user, now, upload_dir):
    routes = APIRouter()

    def entry(connection, row, today):
        override = connection.execute('SELECT ended_on FROM retention_dates WHERE case_id=?', (row['id'],)).fetchone()
        details = json.loads(row['details'] or '{}')
        ended = date.fromisoformat(override['ended_on']) if override else date.fromisoformat(row['archived_at'][:10])
        until = retained_until(ended)
        documents = connection.execute('SELECT COUNT(*) FROM documents WHERE case_id=?', (row['id'],)).fetchone()[0]
        open_tasks = connection.execute('SELECT COUNT(*) FROM tasks WHERE case_id=? AND completed=0', (row['id'],)).fetchone()[0]
        invoices = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='invoices'").fetchone()[0] and \
            connection.execute('SELECT COUNT(*) FROM invoices WHERE case_id=?', (row['id'],)).fetchone()[0]
        return {'case_id': row['id'], 'reference': row['reference'], 'title': row['title'], 'client_name': details.get('client_name') or '',
                'archived_at': row['archived_at'], 'ended_on': ended.isoformat(), 'ended_manually': bool(override), 'retained_until': until.isoformat(),
                'destroyable': today > until, 'documents': documents, 'open_tasks': open_tasks, 'invoices': invoices}

    def owned_archived(connection, case_id, user):
        row = connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (case_id, user['id'])).fetchone()
        if not row or (user.get('allowed_cases') is not None and case_id not in user['allowed_cases']):
            raise HTTPException(404, 'Case not found')
        if not row['archived_at']:
            raise HTTPException(409, 'case_not_archived')
        return row

    @routes.get('/api/retention')
    def overview(user: dict = Depends(require_user)):
        today = date.fromisoformat(now()[:10])
        with db() as connection:
            items = [entry(connection, row, today) for row in connection.execute('SELECT * FROM cases WHERE user_id=? AND archived_at IS NOT NULL', (user['id'],))
                     if user.get('allowed_cases') is None or row['id'] in user['allowed_cases']]
            log = [dict(row) for row in connection.execute('SELECT reference, title, ended_on, retained_until, documents, destroyed_at FROM destruction_log WHERE user_id=? ORDER BY destroyed_at DESC', (user['id'],))]
        items.sort(key=lambda item: (not item['destroyable'], item['retained_until'], item['reference']))
        return {'items': items, 'log': log, 'years': YEARS}

    @routes.put('/api/retention/{case_id}')
    def set_end(case_id: str, payload: EndDate, user: dict = Depends(require_user)):
        with db() as connection:
            row = owned_archived(connection, case_id, user)
            # Files taken over from an earlier system may have ended long before they were created here; only the future is ruled out.
            if payload.ended_on > date.fromisoformat(now()[:10]):
                raise HTTPException(422, 'implausible_end_date')
            connection.execute('INSERT INTO retention_dates VALUES(?,?,?) ON CONFLICT(case_id) DO UPDATE SET ended_on=excluded.ended_on, updated_at=excluded.updated_at',
                               (case_id, payload.ended_on.isoformat(), now()))
            return entry(connection, owned_archived(connection, case_id, user), date.fromisoformat(now()[:10]))

    @routes.post('/api/retention/{case_id}/destroy')
    def destroy(case_id: str, payload: Destroy, user: dict = Depends(require_user)):
        deletion.require_owner(user)
        today = date.fromisoformat(now()[:10])
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = owned_archived(connection, case_id, user)
            item = entry(connection, row, today)
            if not item['destroyable']:
                raise HTTPException(409, 'retention_period_running')
            if payload.confirm.strip().casefold() != row['reference'].casefold():
                raise HTTPException(422, 'case_reference_confirmation_required')
            log = {'id': str(uuid.uuid4()), 'user_id': user['id'], 'reference': row['reference'], 'title': row['title'], 'ended_on': item['ended_on'],
                   'retained_until': item['retained_until'], 'documents': item['documents'], 'destroyed_at': now(), 'destroyed_by': user.get('actor_id', user['id'])}
            connection.execute('INSERT INTO destruction_log VALUES(:id,:user_id,:reference,:title,:ended_on,:retained_until,:documents,:destroyed_at,:destroyed_by)', log)
            connection.execute('DELETE FROM retention_dates WHERE case_id=?', (case_id,))
            orphans = deletion.delete_case(connection, case_id, user['id'])
        deletion.remove_files(upload_dir(), orphans)
        return {key: log[key] for key in ('reference', 'title', 'ended_on', 'retained_until', 'documents', 'destroyed_at')}

    @routes.get('/api/retention/protocol.pdf')
    def protocol(user: dict = Depends(require_user)):
        with db() as connection:
            entries = [dict(row) for row in connection.execute('SELECT * FROM destruction_log WHERE user_id=? ORDER BY destroyed_at', (user['id'],))]
            firm = connection.execute('SELECT organisation, full_name FROM users WHERE id=?', (user['id'],)).fetchone()
        return Response(protocol_pdf(entries, (firm['organisation'] or firm['full_name']) if firm else ''), media_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="Vernichtungsprotokoll.pdf"', 'Cache-Control': 'no-store'})

    return routes
