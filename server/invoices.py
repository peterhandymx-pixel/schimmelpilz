"""Law-office invoicing: RVG invoices per case, advance invoices (§ 9 RVG), time-based invoices, payments and open items.

Fees come from the RVG table in fee_tables (BGBl. 2025 I Nr. 109). The office chooses the fee events and rates; the
module does the arithmetic, the credit of the business fee (Vorbem. 3 Abs. 4 VV RVG), the expense flat rate and VAT.
"""
import csv
import io
import json
import re
import uuid
from datetime import date, datetime, UTC
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator

from .fee_tables import RVG, VALUES
from . import bookkeeping

CENT = Decimal('0.01')
MIN_FEE = Decimal('15.00')            # § 13 Abs. 2 RVG
FLAT_RATE_CAP = Decimal('20.00')      # Nr. 7002 VV RVG: 20 % of the fees, at most 20 EUR

# Fee events offered for RVG invoices: number in the VV, name, default rate and permitted range.
FEES = {
    '2300': ('Geschäftsgebühr', '1.3', '0.5', '2.5'),
    '3100': ('Verfahrensgebühr', '1.3', '1.3', '1.3'),
    '3101': ('Verfahrensgebühr bei vorzeitiger Beendigung', '0.8', '0.8', '0.8'),
    '3104': ('Terminsgebühr', '1.2', '1.2', '1.2'),
    '1000': ('Einigungsgebühr', '1.5', '1.5', '1.5'),
    '1003': ('Einigungsgebühr (Verfahren anhängig)', '1.0', '1.0', '1.0'),
    '1008': ('Erhöhung bei mehreren Auftraggebern', '0.3', '0.3', '2.0'),
    '3200': ('Verfahrensgebühr Berufung', '1.6', '1.6', '1.6'),
    '3202': ('Terminsgebühr Berufung', '1.2', '1.2', '1.2'),
    '3305': ('Verfahrensgebühr Mahnverfahren', '1.0', '1.0', '1.0'),
    '3308': ('Verfahrensgebühr Vollstreckungsbescheid', '0.5', '0.5', '0.5'),
    '3309': ('Verfahrensgebühr Zwangsvollstreckung', '0.3', '0.3', '0.3'),
    '3310': ('Terminsgebühr Zwangsvollstreckung', '0.3', '0.3', '0.3'),
}
EXPENSES = {'7000': 'Dokumentenpauschale', '7003': 'Fahrtkosten eigenes Kfz', '7004': 'Fahrtkosten andere Verkehrsmittel',
            '7005': 'Tage- und Abwesenheitsgeld', '7006': 'Sonstige Auslagen einer Geschäftsreise', 'other': 'Sonstige Auslagen'}
KIND_NAMES = {'rvg': 'Rechnung', 'advance': 'Vorschussrechnung', 'time': 'Rechnung (Zeitaufwand)'}


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def euro(value):
    return f'{money(value):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') + ' EUR'


def decimal_text(value, maximum):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,10}(?:\.\d{1,2})?', value) or Decimal(value) > Decimal(maximum):
        raise ValueError('Use a decimal string without thousands separators')
    return value


def base_fee(value):
    """1.0 fee from the RVG table for an object value."""
    amount = Decimal(value)
    if amount <= 0 or amount > VALUES[-1]:
        raise HTTPException(422, 'value_outside_table')
    return Decimal(RVG[next(index for index, limit in enumerate(VALUES) if amount <= limit)])


class FeeLine(BaseModel):
    model_config = {'extra': 'forbid'}
    code: Literal['2300', '3100', '3101', '3104', '1000', '1003', '1008', '3200', '3202', '3305', '3308', '3309', '3310']
    rate: str
    value: str | None = None      # Gegenstandswert of this event; defaults to the invoice value

    @field_validator('rate')
    @classmethod
    def rate_valid(cls, value):
        return decimal_text(value, '3')

    @field_validator('value')
    @classmethod
    def value_valid(cls, value):
        return value if value is None else decimal_text(value, '500000')

    @model_validator(mode='after')
    def rate_in_range(self):
        _, _, low, high = FEES[self.code]
        if not Decimal(low) <= Decimal(self.rate) <= Decimal(high):
            raise ValueError(f'rate_outside_range_{self.code}')
        return self


class Credit(BaseModel):
    model_config = {'extra': 'forbid'}
    rate: str           # rate of the business fee (Nr. 2300) that was charged before
    value: str          # value of the matter carried into the proceedings

    @field_validator('rate')
    @classmethod
    def rate_valid(cls, value):
        return decimal_text(value, '2.5')

    @field_validator('value')
    @classmethod
    def value_valid(cls, value):
        return decimal_text(value, '500000')


class Expense(BaseModel):
    model_config = {'extra': 'forbid'}
    code: Literal['7000', '7003', '7004', '7005', '7006', 'other']
    description: str = Field(default='', max_length=200)
    amount: str

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        return decimal_text(value, '100000')


class InvoiceInput(BaseModel):
    model_config = {'extra': 'forbid'}
    case_id: uuid.UUID
    kind: Literal['rvg', 'advance', 'time'] = 'rvg'
    recipient: str = Field(min_length=3, max_length=500)
    issued_on: date
    period: str = Field(default='', max_length=100)
    issuer_tax_id: str = Field(default='', max_length=40)
    value: str | None = None
    fees: list[FeeLine] = Field(default_factory=list, max_length=20)
    credit: Credit | None = None
    flat_rate: bool = True
    expenses: list[Expense] = Field(default_factory=list, max_length=20)
    advance_net: str | None = None
    vat_rate: Literal['19', '7', '0'] = '19'
    deduct_advances: bool = True
    note: str = Field(default='', max_length=1000)

    @field_validator('value', 'advance_net')
    @classmethod
    def optional_amount(cls, value):
        return value if value is None else decimal_text(value, '500000')

    @model_validator(mode='after')
    def complete(self):
        if self.kind == 'rvg' and (not self.value or not self.fees):
            raise ValueError('rvg_needs_value_and_fees')
        if self.kind == 'advance' and not self.advance_net:
            raise ValueError('advance_needs_amount')
        return self


class Payment(BaseModel):
    model_config = {'extra': 'forbid'}
    paid_on: date
    amount: str
    note: str = Field(default='', max_length=300)

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        return decimal_text(value, '10000000')


class Cancel(BaseModel):
    model_config = {'extra': 'forbid'}
    reason: str = Field(min_length=5, max_length=500)


class TimeEntry(BaseModel):
    model_config = {'extra': 'forbid'}
    day: date
    minutes: int = Field(ge=1, le=24 * 60)
    activity: str = Field(min_length=3, max_length=300)
    hourly_rate: str

    @field_validator('hourly_rate')
    @classmethod
    def rate_valid(cls, value):
        return decimal_text(value, '2000')


def calculate(payload, time_rows=(), advances=()):
    """Lines, totals and the amount payable. All amounts as decimal strings."""
    lines, fees_total = [], Decimal(0)
    if payload.kind == 'rvg':
        for fee in payload.fees:
            name = FEES[fee.code][0]
            value = fee.value or payload.value
            amount = max(money(Decimal(fee.rate) * base_fee(value)), MIN_FEE)
            fees_total += amount
            # The value is printed once at the top; only a different value is repeated on the line.
            lines.append({'code': fee.code, 'text': f'{fee.rate.replace(".", ",")} {name} Nr. {fee.code} VV RVG', 'detail': f'Wert {euro(value)}' if fee.value and Decimal(fee.value) != Decimal(payload.value) else '', 'amount': str(amount), 'taxable': True})
        if payload.credit:
            # Vorbem. 3 Abs. 4 VV RVG: half of the business fee, at most 0.75, from the value carried over.
            rate = min(Decimal(payload.credit.rate) / 2, Decimal('0.75'))
            amount = -money(rate * base_fee(payload.credit.value))
            lines.append({'code': 'Vorbem. 3 Abs. 4', 'text': f'Anrechnung {str(rate).replace(".", ",")} Geschäftsgebühr, Vorbem. 3 Abs. 4 VV', 'detail': f'Wert {euro(payload.credit.value)}' if Decimal(payload.credit.value) != Decimal(payload.value) else '', 'amount': str(amount), 'taxable': True})
        if payload.flat_rate and fees_total > 0:
            # The flat rate is taken from the fees before any credit; the cap is reached at 100 EUR of fees.
            lines.append({'code': '7002', 'text': 'Post- und Telekommunikationspauschale Nr. 7002 VV RVG', 'detail': '', 'amount': str(min(money(fees_total * Decimal('0.2')), FLAT_RATE_CAP)), 'taxable': True})
        for expense in payload.expenses:
            label = expense.description or EXPENSES[expense.code]
            lines.append({'code': expense.code, 'text': label + (f' Nr. {expense.code} VV RVG' if expense.code != 'other' else ''), 'detail': '', 'amount': str(money(expense.amount)), 'taxable': True})
    elif payload.kind == 'advance':
        lines.append({'code': '§ 9 RVG', 'text': 'Vorschuss auf die voraussichtliche Vergütung (§ 9 RVG)', 'detail': '', 'amount': str(money(payload.advance_net)), 'taxable': True})
    else:
        for row in time_rows:
            amount = money(Decimal(row['hourly_rate']) * row['minutes'] / 60)
            lines.append({'code': 'Zeit', 'text': f'{date.fromisoformat(row["day"]).strftime("%d.%m.%Y")}: {row["activity"]}', 'detail': f'{row["minutes"]} Min. à {euro(row["hourly_rate"])}/Std.', 'amount': str(amount), 'taxable': True})
        if not lines:
            raise HTTPException(422, 'no_unbilled_time')
    net = sum((Decimal(line['amount']) for line in lines), Decimal(0))
    vat = money(net * Decimal(payload.vat_rate) / 100)
    gross = net + vat
    credited = [{'number': row['number'], 'amount': str(money(row['paid']))} for row in advances] if payload.kind != 'advance' and payload.deduct_advances else []
    deducted = sum((Decimal(item['amount']) for item in credited), Decimal(0))
    return {'lines': lines, 'net': str(money(net)), 'vat_rate': payload.vat_rate, 'vat': str(vat), 'gross': str(money(gross)),
            'advances': credited, 'payable': str(money(gross - deducted))}


def migrate(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,case_id TEXT NOT NULL,number TEXT NOT NULL,kind TEXT NOT NULL,
            issued_on TEXT NOT NULL,recipient TEXT NOT NULL,input TEXT NOT NULL,result TEXT NOT NULL,payable_minor INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',cancel_reason TEXT,credited_by TEXT,created_at TEXT NOT NULL,UNIQUE(user_id,number));
        CREATE TABLE IF NOT EXISTS invoice_payments(id TEXT PRIMARY KEY,invoice_id TEXT NOT NULL REFERENCES invoices(id),paid_on TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS time_entries(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,case_id TEXT NOT NULL,day TEXT NOT NULL,minutes INTEGER NOT NULL,
            activity TEXT NOT NULL,hourly_rate TEXT NOT NULL,invoice_id TEXT,recorded_by TEXT,created_at TEXT NOT NULL);
    ''')


def invoice_text(row, user, case):
    """The invoice as text for the letter-paper PDF (§ 10 RVG, § 14 UStG particulars)."""
    data, result = json.loads(row['input']), json.loads(row['result'])
    issuer = ', '.join(part for part in (user['organisation'] or user['full_name'], user['street'], f"{user['postal_code']} {user['city']}") if part.strip())
    out = [issuer, '', row['recipient'], '', f"{date.fromisoformat(row['issued_on']).strftime('%d.%m.%Y')}",
           f"{KIND_NAMES[row['kind']]} Nr. {row['number']}" + (' – STORNIERT' if row['status'] == 'cancelled' else ''),
           f"Ihre Angelegenheit: {case['title']} (unser Zeichen {case['reference']})"]
    if data.get('period'):
        out.append(f"Leistungszeitraum: {data['period']}")
    if data.get('value') and row['kind'] == 'rvg':
        out.append(f"Gegenstandswert: {euro(data['value'])}")
    out.append('')
    for line in result['lines']:
        out.append(f"{line['text']}{' (' + line['detail'] + ')' if line['detail'] else ''}: {euro(line['amount'])}")
    out += ['', f"Summe netto: {euro(result['net'])}", f"Umsatzsteuer {result['vat_rate']} % Nr. 7008 VV RVG: {euro(result['vat'])}", f"Gesamtbetrag: {euro(result['gross'])}"]
    for item in result['advances']:
        out.append(f"abzüglich gezahlter Vorschuss (Rechnung Nr. {item['number']}): {euro(item['amount'])}")
    out += [f"Zu zahlen: {euro(result['payable'])}", '']
    if data.get('issuer_tax_id'):
        out.append(f"Steuernummer / USt-IdNr.: {data['issuer_tax_id']}")
    if data.get('note'):
        out += ['', data['note']]
    if row['status'] == 'cancelled':
        out += ['', f"Diese Rechnung wurde storniert: {row['cancel_reason']}"]
    out += ['', '', '____________________', user['full_name'], '(Unterschrift, § 10 Abs. 1 RVG)']
    return '\n'.join(out)


def router(db, require_user, now, record_activity, compose_pdf, letterhead):
    r = APIRouter()

    def owned_case(c, case_id, user):
        row = c.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (str(case_id), user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Case not found')
        return row

    def owned_invoice(c, invoice_id, user):
        row = c.execute('SELECT * FROM invoices WHERE id=? AND user_id=?', (invoice_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Invoice not found')
        return row

    def open_advances(c, user, case_id):
        # Paid advance invoices of the case that no final invoice has credited yet.
        return [dict(row) for row in c.execute(
            "SELECT i.id,i.number,COALESCE((SELECT SUM(amount_minor) FROM invoice_payments p WHERE p.invoice_id=i.id),0)/100.0 AS paid FROM invoices i "
            "WHERE i.user_id=? AND i.case_id=? AND i.kind='advance' AND i.status!='cancelled' AND i.credited_by IS NULL", (user['id'], str(case_id))) if row['paid'] > 0]

    def public(c, row):
        paid = c.execute('SELECT COALESCE(SUM(amount_minor),0) FROM invoice_payments WHERE invoice_id=?', (row['id'],)).fetchone()[0]
        case = c.execute('SELECT reference,title FROM cases WHERE id=?', (row['case_id'],)).fetchone()
        return {**{k: row[k] for k in ('id', 'case_id', 'number', 'kind', 'issued_on', 'recipient', 'status', 'cancel_reason', 'created_at')},
                'input': json.loads(row['input']), 'result': json.loads(row['result']), 'payable_minor': row['payable_minor'], 'paid_minor': paid,
                'open_minor': 0 if row['status'] == 'cancelled' else max(row['payable_minor'] - paid, 0),
                'case_reference': case['reference'] if case else '', 'case_title': case['title'] if case else '',
                'payments': [dict(p) for p in c.execute('SELECT paid_on,amount_minor,note FROM invoice_payments WHERE invoice_id=? ORDER BY paid_on', (row['id'],))]}

    @r.get('/api/invoices/catalogue')
    def catalogue(user: dict = Depends(require_user)):
        return {'fees': [{'code': code, 'name': name, 'rate': rate, 'min': low, 'max': high} for code, (name, rate, low, high) in FEES.items()],
                'expenses': [{'code': code, 'name': name} for code, name in EXPENSES.items()]}

    @r.post('/api/invoices/calculate')
    def preview(payload: InvoiceInput, user: dict = Depends(require_user)):
        with db() as c:
            owned_case(c, payload.case_id, user)
            rows = c.execute('SELECT * FROM time_entries WHERE case_id=? AND user_id=? AND invoice_id IS NULL ORDER BY day', (str(payload.case_id), user['id'])).fetchall() if payload.kind == 'time' else ()
            return calculate(payload, rows, open_advances(c, user, payload.case_id))

    @r.post('/api/invoices', status_code=201)
    def create(payload: InvoiceInput, user: dict = Depends(require_user)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            owned_case(c, payload.case_id, user)
            rows = c.execute('SELECT * FROM time_entries WHERE case_id=? AND user_id=? AND invoice_id IS NULL ORDER BY day', (str(payload.case_id), user['id'])).fetchall() if payload.kind == 'time' else ()
            advances = open_advances(c, user, payload.case_id)
            result = calculate(payload, rows, advances)
            year = payload.issued_on.year
            count = c.execute("SELECT COUNT(*) FROM invoices WHERE user_id=? AND number LIKE ?", (user['id'], f'{year}-%')).fetchone()[0]
            number = f'{year}-{count + 1:04d}'
            invoice_id = str(uuid.uuid4())
            c.execute('INSERT INTO invoices(id,user_id,case_id,number,kind,issued_on,recipient,input,result,payable_minor,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (invoice_id, user['id'], str(payload.case_id), number, payload.kind, payload.issued_on.isoformat(), payload.recipient.strip(),
                       payload.model_dump_json(), json.dumps(result), int(Decimal(result['payable']) * 100), now()))
            if result['advances']:
                c.executemany('UPDATE invoices SET credited_by=? WHERE id=?', [(invoice_id, item['id']) for item in advances])
            if rows:
                c.executemany('UPDATE time_entries SET invoice_id=? WHERE id=?', [(invoice_id, row['id']) for row in rows])
            record_activity(c, str(payload.case_id), 'invoice_created', f'{KIND_NAMES[payload.kind]} {number}')
            return public(c, owned_invoice(c, invoice_id, user))

    @r.get('/api/invoices')
    def listing(case_id: uuid.UUID | None = None, status: Literal['all', 'open', 'paid', 'cancelled'] = 'all', user: dict = Depends(require_user)):
        with db() as c:
            sql, args = 'SELECT * FROM invoices WHERE user_id=?', [user['id']]
            if case_id:
                sql += ' AND case_id=?'
                args.append(str(case_id))
            items = [public(c, row) for row in c.execute(sql + ' ORDER BY issued_on DESC, number DESC', args)]
        if status == 'open':
            items = [item for item in items if item['status'] != 'cancelled' and item['open_minor'] > 0]
        elif status != 'all':
            items = [item for item in items if item['status'] == status]
        return {'invoices': items, 'open_total_minor': sum(item['open_minor'] for item in items if item['status'] != 'cancelled')}

    @r.post('/api/invoices/{invoice_id}/payments', status_code=201)
    def pay(invoice_id: str, payload: Payment, user: dict = Depends(require_user)):
        with db() as c:
            row = owned_invoice(c, invoice_id, user)
            if row['status'] == 'cancelled':
                raise HTTPException(409, 'invoice_cancelled')
            amount = int(Decimal(payload.amount) * 100)
            if amount <= 0:
                raise HTTPException(422, 'amount_required')
            # The payment also lands in the books as fee income on the office account.
            bookkeeping.pay_invoice(c, user['id'], invoice_id, payload.paid_on.isoformat(), amount, payload.note.strip(), now)
            bookkeeping.book_fee(c, user['id'], invoice_id, payload.paid_on.isoformat(), amount, now)
            record_activity(c, row['case_id'], 'invoice_payment', f'{row["number"]}: {euro(payload.amount)}')
            return public(c, owned_invoice(c, invoice_id, user))

    @r.post('/api/invoices/{invoice_id}/cancel')
    def cancel(invoice_id: str, payload: Cancel, user: dict = Depends(require_user)):
        # The number stays used; a cancelled invoice is kept for the books. Advances it had credited become available again.
        with db() as c:
            row = owned_invoice(c, invoice_id, user)
            if row['status'] == 'cancelled':
                raise HTTPException(409, 'already_cancelled')
            c.execute("UPDATE invoices SET status='cancelled',cancel_reason=? WHERE id=?", (payload.reason.strip(), invoice_id))
            c.execute('UPDATE invoices SET credited_by=NULL WHERE credited_by=?', (invoice_id,))
            c.execute('UPDATE time_entries SET invoice_id=NULL WHERE invoice_id=?', (invoice_id,))
            record_activity(c, row['case_id'], 'invoice_cancelled', f'{row["number"]}: {payload.reason.strip()}')
            return public(c, owned_invoice(c, invoice_id, user))

    @r.get('/api/invoices/{invoice_id}/pdf')
    def pdf(invoice_id: str, user: dict = Depends(require_user)):
        with db() as c:
            row = owned_invoice(c, invoice_id, user)
            case = c.execute('SELECT * FROM cases WHERE id=?', (row['case_id'],)).fetchone()
            owner = c.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
        template, layout = letterhead(owner)
        content = compose_pdf(invoice_text(row, owner, case), template, layout)
        return Response(content, media_type='application/pdf', headers={'Cache-Control': 'no-store', 'Content-Disposition': f'inline; filename="Rechnung-{row["number"]}.pdf"'})

    @r.get('/api/invoices.csv')
    def export(user: dict = Depends(require_user)):
        out = io.StringIO()
        writer = csv.writer(out, delimiter=';')
        writer.writerow(['Rechnungsnr.', 'Datum', 'Art', 'Aktenzeichen', 'Empfänger', 'Netto', 'USt', 'Brutto', 'Zu zahlen', 'Bezahlt', 'Offen', 'Status'])
        de = lambda minor: f'{minor / 100:.2f}'.replace('.', ',')
        with db() as c:
            for row in c.execute('SELECT * FROM invoices WHERE user_id=? ORDER BY number', (user['id'],)).fetchall():
                item = public(c, row)
                result = item['result']
                writer.writerow([item['number'], item['issued_on'], KIND_NAMES[item['kind']], item['case_reference'], item['recipient'].split('\n')[0],
                                 result['net'].replace('.', ','), result['vat'].replace('.', ','), result['gross'].replace('.', ','),
                                 de(item['payable_minor']), de(item['paid_minor']), de(item['open_minor']), {'open': 'offen', 'paid': 'bezahlt', 'cancelled': 'storniert'}[item['status']]])
        return Response('﻿' + out.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="Schimmelpilz-Rechnungen.csv"'})

    # ---------- time recording ----------
    @r.get('/api/cases/{case_id}/time-entries')
    def times(case_id: str, user: dict = Depends(require_user)):
        with db() as c:
            owned_case(c, case_id, user)
            return [dict(row) for row in c.execute('SELECT t.*,i.number AS invoice_number FROM time_entries t LEFT JOIN invoices i ON i.id=t.invoice_id WHERE t.case_id=? AND t.user_id=? ORDER BY t.day DESC,t.created_at DESC', (case_id, user['id']))]

    @r.post('/api/cases/{case_id}/time-entries', status_code=201)
    def add_time(case_id: str, payload: TimeEntry, user: dict = Depends(require_user)):
        with db() as c:
            owned_case(c, case_id, user)
            c.execute('INSERT INTO time_entries VALUES(?,?,?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), user['id'], case_id, payload.day.isoformat(), payload.minutes, payload.activity.strip(), payload.hourly_rate, None, user.get('actor_id', user['id']), now()))
            record_activity(c, case_id, 'time_recorded', f'{payload.minutes} Min.: {payload.activity.strip()}')
        return times(case_id, user)

    @r.delete('/api/cases/{case_id}/time-entries/{entry_id}', status_code=204)
    def remove_time(case_id: str, entry_id: str, user: dict = Depends(require_user)):
        with db() as c:
            owned_case(c, case_id, user)
            row = c.execute('SELECT invoice_id FROM time_entries WHERE id=? AND case_id=?', (entry_id, case_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Not found')
            if row['invoice_id']:
                raise HTTPException(409, 'already_invoiced')
            c.execute('DELETE FROM time_entries WHERE id=?', (entry_id,))
        return Response(status_code=204)

    return r
