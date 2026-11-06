"""Claim account per case: principal and cost items, default interest, payments credited under § 367 BGB.

Interest is simple (§ 289 BGB), day-exact, actual days / 365, for the period from "interest from" up to the day before a
payment (or up to and including the statement date). The base rate (§ 247 BGB) changes on 1 January and 1 July.
"""
import json
import os
import re
import sys
import threading
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator

CENT = Decimal('0.01')


def euro(value, rounding=None):
    """German money text for ledger lines: 1.234,50 €."""
    amount = value.quantize(CENT, rounding) if rounding else value.quantize(CENT)
    return f'{amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'


# Basiszinssatz (§ 247 BGB) as published by the Deutsche Bundesbank. Add each new value on 1 January / 1 July.
BASE_RATES = [
    (date(2015, 1, 1), '-0.83'), (date(2016, 7, 1), '-0.88'), (date(2023, 1, 1), '1.62'), (date(2023, 7, 1), '3.12'),
    (date(2024, 1, 1), '3.62'), (date(2024, 7, 1), '3.37'), (date(2025, 1, 1), '2.27'), (date(2025, 7, 1), '1.27'),
    (date(2026, 1, 1), '1.27'), (date(2026, 7, 1), '1.52'),
]
KNOWN_UNTIL = date(2026, 12, 31)
SPREAD = {'consumer': Decimal(5), 'business': Decimal(9)}   # § 288 Abs. 1 und Abs. 2 BGB


# The Bundesbank publishes the rate as a monthly series; it is fetched at most once a day and cached next to the data.
RATE_URL = 'https://api.statistiken.bundesbank.de/rest/data/BBIN1/M.DE.BBK.BBKBAS2.EUR.ME?format=csv&lang=de&startPeriod=2015-01'
RATE_CACHE = Path(os.getenv('DATA_DIR', Path(__file__).resolve().parents[1] / 'data')) / 'base-rates.json'
_FETCHED = {'rates': None, 'until': None, 'checked': 0.0}
_RATE_LOCK = threading.Lock()


def parse_rates(text):
    """Monthly 'YYYY-MM;1,52;' rows -> [(first day of month, '1.52')] and the last day the newest value is known for."""
    rates = []
    for year, month, value in re.findall(r'^(\d{4})-(\d{2});(-?\d+,\d+);', text, re.MULTILINE):
        number = Decimal(value.replace(',', '.'))
        if abs(number) < 20:
            rates.append((date(int(year), int(month), 1), str(number)))
    if not rates:
        raise ValueError('no_rates')
    last = rates[-1][0]
    # The rate is fixed per half-year, so the newest observation is valid to the end of its half-year.
    until = date(last.year, 6, 30) if last.month <= 6 else date(last.year, 12, 31)
    return rates, until


def _load_cache():
    if _FETCHED['rates'] is None:
        try:
            data = json.loads(RATE_CACHE.read_text(encoding='utf-8'))
            _FETCHED.update(rates=[(date.fromisoformat(day), rate) for day, rate in data['rates']], until=date.fromisoformat(data['until']), checked=data.get('checked', 0.0))
        except (OSError, ValueError, KeyError, TypeError):
            _FETCHED['rates'] = []


def refresh_rates(force=False):
    """Fetch the series if the cache is older than a day. Never raises; the built-in table stays the fallback."""
    if 'pytest' in sys.modules and not os.getenv('BASE_RATE_FETCH_IN_TESTS'):
        return False
    with _RATE_LOCK:
        _load_cache()
        if not force and time.time() - _FETCHED['checked'] < 86400:
            return False
        _FETCHED['checked'] = time.time()
        try:
            request = Request(RATE_URL, headers={'Accept': 'text/csv', 'User-Agent': 'schimmelpilz-server/1.0'})
            with urlopen(request, timeout=20) as response:
                rates, until = parse_rates(response.read(2 * 1024 * 1024).decode('utf-8-sig', 'replace'))
            _FETCHED.update(rates=rates, until=until)
            RATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            RATE_CACHE.write_text(json.dumps({'rates': [(day.isoformat(), rate) for day, rate in rates], 'until': until.isoformat(), 'checked': _FETCHED['checked'], 'source': RATE_URL}), encoding='utf-8')
            return True
        except (OSError, ValueError):
            return False


def refresh_in_background():
    threading.Thread(target=refresh_rates, daemon=True).start()


def rate_table():
    """Built-in table merged with the fetched Bundesbank series (fetched values win for the same month)."""
    _load_cache()
    merged = dict(BASE_RATES)
    merged.update(dict(_FETCHED['rates'] or []))
    return sorted(merged.items())


def known_until():
    return max(KNOWN_UNTIL, _FETCHED['until'] or KNOWN_UNTIL)


def base_rate(day):
    table = rate_table()
    if day < table[0][0]:
        raise HTTPException(422, 'date_before_rate_table')
    return Decimal([rate for start, rate in table if start <= day][-1])


def rate_changes(start, end):
    """Dates in (start, end) on which the base rate may change."""
    days, year = [], start.year
    while date(year, 1, 1) < end:
        for change in (date(year, 1, 1), date(year, 7, 1)):
            if start < change < end:
                days.append(change)
        year += 1
    return days


def interest(amount, item, start, end):
    """Simple interest on `amount` for the days start ≤ d < end."""
    if amount <= 0 or item['interest_mode'] == 'none' or not item['interest_from']:
        return Decimal(0)
    start = max(start, date.fromisoformat(item['interest_from']))
    if start >= end:
        return Decimal(0)
    total, points = Decimal(0), [start, *rate_changes(start, end), end]
    for left, right in zip(points, points[1:]):
        if item['interest_mode'] == 'fixed':
            yearly = Decimal(item['interest_rate'])
        else:
            yearly = max(base_rate(left) + SPREAD[item['interest_mode']], Decimal(0))
        total += amount * yearly / 100 * (right - left).days / 365
    return total


def statement(items, payments, as_of):
    """Chronological account with § 367 BGB crediting. Amounts in Decimal; rounded for display only."""
    open_amount = {item['id']: Decimal(item['amount_minor']) / 100 for item in items}
    interest_due, last = Decimal(0), None
    entries = []
    start_day = min([date.fromisoformat(item['booked_on']) for item in items] + [date.fromisoformat(item['interest_from']) for item in items if item['interest_from']] or [as_of])
    cursor = start_day
    principal = [item for item in items if item['kind'] == 'principal']
    costs = [item for item in items if item['kind'] == 'cost']
    for item in sorted(items, key=lambda value: value['booked_on']):
        entries.append({'day': item['booked_on'], 'text': ('Hauptforderung: ' if item['kind'] == 'principal' else 'Kosten: ') + item['description'], 'amount': str(Decimal(item['amount_minor']) / 100)})

    def accrue(until):
        nonlocal interest_due, cursor
        if until <= cursor:
            return
        interest_due += sum((interest(open_amount[item['id']], item, cursor, until) for item in items), Decimal(0))
        cursor = until

    for payment in sorted(payments, key=lambda value: value['paid_on']):
        paid_on = date.fromisoformat(payment['paid_on'])
        if paid_on > as_of:
            continue
        accrue(paid_on)
        rest = Decimal(payment['amount_minor']) / 100
        credited = []
        # § 367 Abs. 1 BGB: costs, then interest, then the principal (oldest due first, § 366 Abs. 2 BGB).
        for item in sorted(costs, key=lambda value: value['booked_on']):
            part = min(rest, open_amount[item['id']])
            if part > 0:
                open_amount[item['id']] -= part; rest -= part; credited.append(f'Kosten {euro(part)}')
        part = min(rest, interest_due)
        if part > 0:
            interest_due -= part; rest -= part; credited.append(f'Zinsen {euro(part, ROUND_HALF_UP)}')
        for item in sorted(principal, key=lambda value: value['booked_on']):
            part = min(rest, open_amount[item['id']])
            if part > 0:
                open_amount[item['id']] -= part; rest -= part; credited.append(f'Hauptforderung {euro(part)}')
        entries.append({'day': payment['paid_on'], 'text': 'Zahlung' + (f' ({payment["note"]})' if payment['note'] else '') + ' – verrechnet: ' + (', '.join(credited) or '—') + (f'; Überzahlung {euro(rest)}' if rest > 0 else ''), 'amount': str(-(Decimal(payment['amount_minor']) / 100))})
    accrue(as_of + timedelta(days=1))
    entries.sort(key=lambda value: value['day'])
    owed_principal = sum((open_amount[item['id']] for item in principal), Decimal(0))
    owed_costs = sum((open_amount[item['id']] for item in costs), Decimal(0))
    daily = sum((interest(open_amount[item['id']], item, as_of + timedelta(days=1), as_of + timedelta(days=2)) for item in items), Decimal(0))
    round_ = lambda value: str(value.quantize(CENT, ROUND_HALF_UP))
    return {'as_of': as_of.isoformat(), 'entries': [{**entry, 'amount': round_(Decimal(entry['amount']))} for entry in entries],
            'principal': round_(owed_principal), 'costs': round_(owed_costs), 'interest': round_(interest_due),
            'total': round_(owed_principal + owed_costs + interest_due), 'daily_interest': round_(daily),
            'rate_table_until': known_until().isoformat(), 'rate_warning': as_of > known_until(),
            'base_rate_now': str(base_rate(min(as_of, known_until())))}


def positive_amount(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,9}(?:\.\d{1,2})?', value) or Decimal(value) <= 0:
        raise ValueError('positive decimal amount required')
    return value


class Item(BaseModel):
    model_config = {'extra': 'forbid'}
    kind: Literal['principal', 'cost']
    description: str = Field(min_length=2, max_length=200)
    amount: str
    booked_on: date
    interest_mode: Literal['none', 'consumer', 'business', 'fixed'] = 'none'
    interest_rate: str | None = None
    interest_from: date | None = None

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        return positive_amount(value)

    @model_validator(mode='after')
    def interest_complete(self):
        if self.interest_mode != 'none' and not self.interest_from:
            raise ValueError('interest_from_required')
        if self.interest_mode == 'fixed':
            if not self.interest_rate or not Decimal(0) < Decimal(self.interest_rate) <= Decimal(30):
                raise ValueError('fixed_rate_required')
        else:
            self.interest_rate = None
        return self


class PaymentIn(BaseModel):
    model_config = {'extra': 'forbid'}
    paid_on: date
    amount: str
    note: str = Field(default='', max_length=200)

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        return positive_amount(value)


def migrate(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS claim_items(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,case_id TEXT NOT NULL,kind TEXT NOT NULL,description TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,booked_on TEXT NOT NULL,interest_mode TEXT NOT NULL,interest_rate TEXT,interest_from TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS claim_payments(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,case_id TEXT NOT NULL,paid_on TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
    ''')


def report_pdf(case, data, items):
    """Forderungsaufstellung as a proper table document (annex for enforcement): claims, account history, totals."""
    import io
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    money = lambda value: euro(Decimal(value))
    when = lambda value: date.fromisoformat(value).strftime('%d.%m.%Y')
    modes = {'consumer': '5 %-Punkte über Basiszins (§ 288 Abs. 1 BGB)', 'business': '9 %-Punkte über Basiszins (§ 288 Abs. 2 BGB)'}
    base = ParagraphStyle('base', fontName='Helvetica', fontSize=9.5, leading=12.5, textColor=colors.HexColor('#1f2d26'))
    small = ParagraphStyle('small', parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor('#5d6b60'))
    bold = ParagraphStyle('bold', parent=base, fontName='Helvetica-Bold')
    right = ParagraphStyle('right', parent=base, alignment=TA_RIGHT)
    right_bold = ParagraphStyle('right_bold', parent=bold, alignment=TA_RIGHT)
    title = ParagraphStyle('title', parent=base, fontName='Helvetica-Bold', fontSize=16, leading=20, spaceAfter=4)
    heading = ParagraphStyle('heading', parent=base, fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=12, spaceAfter=6)
    cell = lambda text, style=base: Paragraph(escape(str(text)), style)
    width = A4[0] - 45 * mm
    grid = lambda header_rows=1: [('LINEBELOW', (0, 0), (-1, header_rows - 1), 0.8, colors.HexColor('#2f5d4d')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('LINEBELOW', (0, header_rows), (-1, -1), 0.3, colors.HexColor('#d6ded2')), ('TOPPADDING', (0, 0), (-1, -1), 4),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]

    story = [Paragraph('Forderungsaufstellung', title),
             cell(f'Akte {case["reference"]} – {case["title"]}'), cell(f'Stand: {when(data["as_of"])}', small), Spacer(1, 6)]

    rows = [[cell('Art', bold), cell('Bezeichnung', bold), cell('Fällig am', bold), cell('Betrag', right_bold), cell('Verzinsung', bold)]]
    for item in items:
        if item['interest_mode'] == 'none':
            rate = 'unverzinslich'
        else:
            rate = (modes.get(item['interest_mode']) or f'{str(item["interest_rate"]).replace(".", ",")} % p. a.') + f' ab {when(item["interest_from"])}'
        rows.append([cell('Hauptforderung' if item['kind'] == 'principal' else 'Kosten'), cell(item['description']), cell(when(item['booked_on'])),
                     cell(money(Decimal(item['amount_minor']) / 100), right), cell(rate, small)])
    claims_table = Table(rows, colWidths=[28 * mm, None, 22 * mm, 26 * mm, 52 * mm], repeatRows=1)
    claims_table.setStyle(TableStyle(grid()))
    story += [Paragraph('1. Forderungen', heading), claims_table]

    rows = [[cell('Datum', bold), cell('Vorgang', bold), cell('Betrag', right_bold)]]
    for entry in data['entries']:
        text, _, credited = entry['text'].partition(' – verrechnet: ')
        label = [cell(text)] + ([cell('verrechnet nach § 367 BGB: ' + credited, small)] if credited else [])
        rows.append([cell(when(entry['day'])), label, cell(money(entry['amount']), right)])
    history = Table(rows, colWidths=[22 * mm, None, 30 * mm], repeatRows=1)
    history.setStyle(TableStyle(grid()))
    story += [Paragraph('2. Kontoverlauf', heading), history]

    next_day = when((date.fromisoformat(data['as_of']) + timedelta(days=1)).isoformat())
    rows = [[cell('Offene Hauptforderung'), cell(money(data['principal']), right)],
            [cell(f'Rückständige Zinsen bis {when(data["as_of"])}'), cell(money(data['interest']), right)],
            [cell('Offene Kosten'), cell(money(data['costs']), right)],
            [cell('Gesamtforderung', bold), cell(money(data['total']), right_bold)],
            [cell(f'zuzüglich weiterer Zinsen ab {next_day} je Tag', small), cell(money(data['daily_interest']), ParagraphStyle('rs', parent=small, alignment=TA_RIGHT))]]
    totals = Table(rows, colWidths=[None, 34 * mm], hAlign='RIGHT')
    totals.setStyle(TableStyle([('LINEABOVE', (0, 3), (-1, 3), 0.8, colors.HexColor('#1f2d26')), ('LINEBELOW', (0, 3), (-1, 3), 0.8, colors.HexColor('#1f2d26')),
                                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#f3f7f4')), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]))
    story += [KeepTogether([Paragraph('3. Zusammenfassung', heading), totals]), Spacer(1, 12),
              cell('Zahlungen sind nach § 367 Abs. 1 BGB zuerst auf die Kosten, dann auf die Zinsen und zuletzt auf die Hauptforderung verrechnet. '
                   'Zinsen taggenau (Tage/365), ohne Zinseszins (§ 289 BGB); Basiszinssatz nach § 247 BGB laut Deutscher Bundesbank.', small)]

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(colors.HexColor('#5d6b60'))
        canvas.drawString(25 * mm, 12 * mm, f'Forderungsaufstellung {case["reference"]} · Stand {when(data["as_of"])}')
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f'Seite {doc.page}')
        canvas.restoreState()

    output = io.BytesIO()
    SimpleDocTemplate(output, pagesize=A4, leftMargin=25 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=20 * mm,
                      title=f'Forderungsaufstellung {case["reference"]}', author='').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def router(db, require_user, now, record_activity, compose_pdf):
    r = APIRouter()
    refresh_in_background()

    def owned(c, case_id, user):
        row = c.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (case_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Case not found')
        return row

    def load(c, case_id, as_of):
        items = [dict(row) for row in c.execute('SELECT * FROM claim_items WHERE case_id=? ORDER BY booked_on,created_at', (case_id,))]
        payments = [dict(row) for row in c.execute('SELECT * FROM claim_payments WHERE case_id=? ORDER BY paid_on,created_at', (case_id,))]
        return items, payments, statement(items, payments, as_of)

    @r.get('/api/cases/{case_id}/claim')
    def account(case_id: str, as_of: date | None = None, user: dict = Depends(require_user)):
        refresh_in_background()   # at most one Bundesbank request per day, never blocks the answer
        with db() as c:
            owned(c, case_id, user)
            items, payments, data = load(c, case_id, as_of or date.today())
        return {'items': items, 'payments': payments, 'statement': data}

    @r.post('/api/cases/{case_id}/claim/items', status_code=201)
    def add_item(case_id: str, payload: Item, user: dict = Depends(require_user)):
        with db() as c:
            owned(c, case_id, user)
            c.execute('INSERT INTO claim_items VALUES(?,?,?,?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), user['id'], case_id, payload.kind, payload.description.strip(), int(Decimal(payload.amount) * 100),
                      payload.booked_on.isoformat(), payload.interest_mode, payload.interest_rate, payload.interest_from.isoformat() if payload.interest_from else None, now()))
            record_activity(c, case_id, 'claim_item_added', f'{payload.description.strip()}: {payload.amount} EUR')
        return account(case_id, None, user)

    @r.post('/api/cases/{case_id}/claim/payments', status_code=201)
    def add_payment(case_id: str, payload: PaymentIn, user: dict = Depends(require_user)):
        with db() as c:
            owned(c, case_id, user)
            c.execute('INSERT INTO claim_payments VALUES(?,?,?,?,?,?,?)', (str(uuid.uuid4()), user['id'], case_id, payload.paid_on.isoformat(), int(Decimal(payload.amount) * 100), payload.note.strip(), now()))
            record_activity(c, case_id, 'claim_payment', f'{payload.amount} EUR am {payload.paid_on.isoformat()}')
        return account(case_id, None, user)

    @r.delete('/api/cases/{case_id}/claim/{kind}/{entry_id}', status_code=204)
    def remove(case_id: str, kind: Literal['items', 'payments'], entry_id: str, user: dict = Depends(require_user)):
        with db() as c:
            owned(c, case_id, user)
            table = 'claim_items' if kind == 'items' else 'claim_payments'
            if not c.execute(f'DELETE FROM {table} WHERE id=? AND case_id=?', (entry_id, case_id)).rowcount:
                raise HTTPException(404, 'Not found')
            record_activity(c, case_id, 'claim_entry_removed', table)
        return Response(status_code=204)

    @r.get('/api/cases/{case_id}/claim/report.pdf')
    def report(case_id: str, as_of: date | None = None, user: dict = Depends(require_user)):
        with db() as c:
            case = owned(c, case_id, user)
            items, _, data = load(c, case_id, as_of or date.today())
        return Response(report_pdf(case, data, items), media_type='application/pdf',
                        headers={'Cache-Control': 'no-store', 'Content-Disposition': f'inline; filename="Forderungsaufstellung-{case["reference"]}.pdf"'})

    return r
