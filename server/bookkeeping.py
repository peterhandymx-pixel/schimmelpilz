"""Office bookkeeping: office, trust (Anderkonto) and cash accounts, client money per case, fee income linked to invoices,
VAT pre-return figures (cash basis, § 20 UStG) and a DATEV-style CSV export.

Client money must be kept apart and passed on without delay (§ 43a Abs. 5 BRAO, § 4 BORA): trust bookings always belong
to a case, a case's trust balance can never go below zero, and money held longer than 14 days is flagged.
"""
import csv
import io
import json
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator

CENT = Decimal('0.01')
TRUST_DAYS = 14
CATEGORIES = {
    'fee_income': 'Honorareingang', 'other_income': 'Sonstige Einnahme', 'expense': 'Ausgabe', 'private': 'Privatentnahme / -einlage',
    'transfer': 'Umbuchung zwischen Konten', 'trust_in': 'Fremdgeldeingang', 'trust_out': 'Fremdgeld weitergeleitet', 'trust_to_fees': 'Fremdgeld mit Honorar verrechnet',
}
OFFICE_CATEGORIES = {'fee_income', 'other_income', 'expense', 'private', 'transfer'}
TRUST_CATEGORIES = {'trust_in', 'trust_out', 'trust_to_fees', 'transfer'}
# Default account numbers (SKR04); every office can change them for the export.
DEFAULT_DATEV = {'bank': '1800', 'trust': '1810', 'cash': '1600', 'revenue_19': '4400', 'revenue_7': '4300', 'revenue_0': '4200',
                 'expense': '6300', 'private': '2100', 'client_money': '3500', 'other_income': '4830'}


def minor(text):
    return int((Decimal(text) * 100).to_integral_value(ROUND_HALF_UP))


class Booking(BaseModel):
    model_config = {'extra': 'forbid'}
    account_id: str
    day: date
    direction: Literal['in', 'out']
    amount: str
    category: Literal['fee_income', 'other_income', 'expense', 'private', 'transfer', 'trust_in', 'trust_out', 'trust_to_fees']
    case_id: uuid.UUID | None = None
    invoice_id: str | None = None
    counter_account_id: str | None = None      # target of a transfer
    counterparty: str = Field(default='', max_length=200)
    text: str = Field(min_length=2, max_length=300)
    vat_rate: Literal['19', '7', '0'] = '0'

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r'\d{1,9}(?:\.\d{1,2})?', value) or Decimal(value) <= 0:
            raise ValueError('positive decimal amount required')
        return value

    @model_validator(mode='after')
    def consistent(self):
        directions = {'fee_income': 'in', 'other_income': 'in', 'expense': 'out', 'trust_in': 'in', 'trust_out': 'out', 'trust_to_fees': 'out'}
        if self.category in directions and directions[self.category] != self.direction:
            raise ValueError('direction_does_not_match_category')
        if self.category.startswith('trust') and not self.case_id:
            raise ValueError('client_money_needs_case')
        if self.category == 'trust_to_fees' and not self.invoice_id:
            raise ValueError('settlement_needs_invoice')
        if self.category == 'transfer' and not self.counter_account_id:
            raise ValueError('transfer_needs_target')
        return self


class Reverse(BaseModel):
    model_config = {'extra': 'forbid'}
    reason: str = Field(min_length=5, max_length=300)


class DatevSettings(BaseModel):
    model_config = {'extra': 'forbid'}
    accounts: dict[str, str]

    @field_validator('accounts')
    @classmethod
    def numbers(cls, value):
        if set(value) - set(DEFAULT_DATEV) or any(not re.fullmatch(r'\d{3,8}', number) for number in value.values()):
            raise ValueError('account numbers: 3–8 digits')
        return value


def migrate(c):
    c.executescript('''
        CREATE TABLE IF NOT EXISTS ledger_accounts(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger_entries(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,account_id TEXT NOT NULL,case_id TEXT,invoice_id TEXT,
            day TEXT NOT NULL,amount_minor INTEGER NOT NULL,category TEXT NOT NULL,counterparty TEXT NOT NULL DEFAULT '',text TEXT NOT NULL,
            vat_rate TEXT NOT NULL DEFAULT '0',vat_minor INTEGER NOT NULL DEFAULT 0,pair_id TEXT,reversed_by TEXT,reverses TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger_settings(user_id TEXT PRIMARY KEY,datev TEXT NOT NULL);
    ''')


def accounts(c, user_id, now):
    rows = c.execute('SELECT * FROM ledger_accounts WHERE user_id=? ORDER BY created_at', (user_id,)).fetchall()
    if not rows:
        for name, kind in (('Geschäftskonto', 'office'), ('Fremdgeld-Anderkonto', 'trust'), ('Kasse', 'cash')):
            c.execute('INSERT INTO ledger_accounts VALUES(?,?,?,?,?)', (str(uuid.uuid4()), user_id, name, kind, now()))
        rows = c.execute('SELECT * FROM ledger_accounts WHERE user_id=? ORDER BY created_at', (user_id,)).fetchall()
    return [dict(row) for row in rows]


def insert(c, user_id, account_id, day, amount_minor, category, text, now, case_id=None, invoice_id=None, counterparty='', vat_rate='0', vat_minor=0, pair_id=None, reverses=None):
    entry_id = str(uuid.uuid4())
    c.execute('INSERT INTO ledger_entries(id,user_id,account_id,case_id,invoice_id,day,amount_minor,category,counterparty,text,vat_rate,vat_minor,pair_id,reverses,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (entry_id, user_id, account_id, case_id, invoice_id, day, amount_minor, category, counterparty, text, vat_rate, vat_minor, pair_id, reverses, now()))
    return entry_id


def trust_balance(c, user_id, case_id):
    return c.execute("SELECT COALESCE(SUM(amount_minor),0) FROM ledger_entries e JOIN ledger_accounts a ON a.id=e.account_id WHERE e.user_id=? AND e.case_id=? AND a.kind='trust'", (user_id, case_id)).fetchone()[0]


def invoice_vat_share(c, invoice_id, amount_minor):
    """VAT contained in a payment on an invoice, in proportion to the invoice's gross amount (cash basis)."""
    row = c.execute('SELECT result FROM invoices WHERE id=?', (invoice_id,)).fetchone()
    result = json.loads(row['result'])
    gross = Decimal(result['gross'])
    if gross <= 0:
        return result['vat_rate'], 0
    return result['vat_rate'], int((Decimal(amount_minor) * Decimal(result['vat']) / gross).to_integral_value(ROUND_HALF_UP))


def pay_invoice(c, user_id, invoice_id, day, amount_minor, note, now):
    """Record a payment on an invoice and update its status (shared with the billing module)."""
    row = c.execute('SELECT * FROM invoices WHERE id=? AND user_id=?', (invoice_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, 'Invoice not found')
    if row['status'] == 'cancelled':
        raise HTTPException(409, 'invoice_cancelled')
    c.execute('INSERT INTO invoice_payments VALUES(?,?,?,?,?,?)', (str(uuid.uuid4()), invoice_id, day, amount_minor, note, now()))
    paid = c.execute('SELECT SUM(amount_minor) FROM invoice_payments WHERE invoice_id=?', (invoice_id,)).fetchone()[0]
    c.execute('UPDATE invoices SET status=? WHERE id=?', ('paid' if paid >= row['payable_minor'] else 'open', invoice_id))
    return row


def book_fee(c, user_id, invoice_id, day, amount_minor, now, account_id=None, text=''):
    """Fee income on the office account for a payment on an invoice."""
    office = account_id or next(a['id'] for a in accounts(c, user_id, now) if a['kind'] == 'office')
    row = c.execute('SELECT number,case_id,recipient FROM invoices WHERE id=?', (invoice_id,)).fetchone()
    rate, vat = invoice_vat_share(c, invoice_id, amount_minor)
    return insert(c, user_id, office, day, amount_minor, 'fee_income', text or f'Zahlung auf Rechnung {row["number"]}', now, row['case_id'], invoice_id, row['recipient'].split('\n')[0], rate, vat)


def router(db, require_user, now, record_activity):
    r = APIRouter()

    def account(c, user, account_id):
        found = next((a for a in accounts(c, user['id'], now) if a['id'] == account_id), None)
        if not found:
            raise HTTPException(404, 'Account not found')
        return found

    def entry_view(row, names, cases):
        return {**dict(row), 'account_name': names.get(row['account_id'], ''), 'category_name': CATEGORIES[row['category']], 'case_reference': cases.get(row['case_id'], '')}

    @r.get('/api/ledger')
    def overview(year: int | None = None, user: dict = Depends(require_user)):
        with db() as c:
            accs = accounts(c, user['id'], now)
            names = {a['id']: a['name'] for a in accs}
            cases = {row['id']: row['reference'] for row in c.execute('SELECT id,reference FROM cases WHERE user_id=?', (user['id'],))}
            balances = {row['account_id']: row['total'] for row in c.execute('SELECT account_id,SUM(amount_minor) AS total FROM ledger_entries WHERE user_id=? GROUP BY account_id', (user['id'],))}
            sql, args = 'SELECT * FROM ledger_entries WHERE user_id=?', [user['id']]
            if year:
                sql += ' AND day LIKE ?'
                args.append(f'{year}-%')
            entries = [entry_view(row, names, cases) for row in c.execute(sql + ' ORDER BY day DESC, created_at DESC LIMIT 1000', args)]
            # Client money per case, with the date of the oldest money still held.
            trust = []
            for row in c.execute("SELECT e.case_id,SUM(e.amount_minor) AS balance,MIN(CASE WHEN e.amount_minor>0 THEN e.day END) AS first_in,MAX(e.day) AS last_day FROM ledger_entries e JOIN ledger_accounts a ON a.id=e.account_id WHERE e.user_id=? AND a.kind='trust' AND e.case_id IS NOT NULL GROUP BY e.case_id", (user['id'],)):
                if row['balance']:
                    held_since = c.execute("SELECT MAX(e.day) FROM ledger_entries e JOIN ledger_accounts a ON a.id=e.account_id WHERE e.user_id=? AND e.case_id=? AND a.kind='trust' AND e.amount_minor>0", (user['id'], row['case_id'])).fetchone()[0]
                    days = (date.today() - date.fromisoformat(held_since)).days if held_since else 0
                    trust.append({'case_id': row['case_id'], 'case_reference': cases.get(row['case_id'], ''), 'balance_minor': row['balance'], 'held_since': held_since, 'days': days, 'overdue': days > TRUST_DAYS})
            open_invoices = [dict(row) for row in c.execute("SELECT i.id,i.number,i.payable_minor-COALESCE((SELECT SUM(amount_minor) FROM invoice_payments p WHERE p.invoice_id=i.id),0) AS open_minor,i.case_id FROM invoices i WHERE i.user_id=? AND i.status='open'", (user['id'],)) if row['open_minor'] > 0]
        return {'accounts': [{**a, 'balance_minor': balances.get(a['id'], 0)} for a in accs], 'entries': entries, 'trust': trust, 'trust_limit_days': TRUST_DAYS,
                'open_invoices': open_invoices, 'categories': CATEGORIES}

    @r.post('/api/ledger/entries', status_code=201)
    def book(payload: Booking, user: dict = Depends(require_user)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            source = account(c, user, payload.account_id)
            if source['kind'] == 'trust' and payload.category not in TRUST_CATEGORIES:
                raise HTTPException(422, 'office_booking_on_trust_account')
            if source['kind'] != 'trust' and payload.category.startswith('trust'):
                raise HTTPException(422, 'client_money_only_on_trust_account')
            case_id = str(payload.case_id) if payload.case_id else None
            if case_id and not c.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?', (case_id, user['id'])).fetchone():
                raise HTTPException(404, 'Case not found')
            amount = minor(payload.amount)
            signed = amount if payload.direction == 'in' else -amount
            day = payload.day.isoformat()
            if source['kind'] == 'trust' and signed < 0 and trust_balance(c, user['id'], case_id) + signed < 0:
                raise HTTPException(409, 'client_money_insufficient')
            if payload.category == 'transfer':
                target = account(c, user, payload.counter_account_id)
                if target['id'] == source['id'] or (target['kind'] == 'trust') != (source['kind'] == 'trust') and not case_id:
                    raise HTTPException(422, 'invalid_transfer')
                pair = str(uuid.uuid4())
                first = insert(c, user['id'], source['id'], day, signed, 'transfer', payload.text, now, case_id, None, payload.counterparty, pair_id=pair)
                insert(c, user['id'], target['id'], day, -signed, 'transfer', payload.text, now, case_id, None, payload.counterparty, pair_id=pair)
                return {'id': first}
            if payload.category == 'trust_to_fees':
                # Client money settled against an invoice: out of the trust account, in on the office account as fee income.
                invoice = c.execute('SELECT case_id FROM invoices WHERE id=? AND user_id=?', (payload.invoice_id, user['id'])).fetchone()
                if not invoice or invoice['case_id'] != case_id:
                    raise HTTPException(422, 'invoice_of_other_case')
                pay_invoice(c, user['id'], payload.invoice_id, day, amount, 'Verrechnung mit Fremdgeld', now)
                pair = str(uuid.uuid4())
                first = insert(c, user['id'], source['id'], day, -amount, 'trust_to_fees', payload.text, now, case_id, payload.invoice_id, payload.counterparty, pair_id=pair)
                fee = book_fee(c, user['id'], payload.invoice_id, day, amount, now, text=payload.text)
                c.execute('UPDATE ledger_entries SET pair_id=? WHERE id=?', (pair, fee))
                record_activity(c, case_id, 'trust_settled', payload.text)
                return {'id': first}
            if payload.category == 'fee_income' and payload.invoice_id:
                invoice = pay_invoice(c, user['id'], payload.invoice_id, day, amount, payload.text, now)
                entry = book_fee(c, user['id'], payload.invoice_id, day, amount, now, source['id'], payload.text)
                record_activity(c, invoice['case_id'], 'invoice_payment', payload.text)
                return {'id': entry}
            vat = int((Decimal(amount) * Decimal(payload.vat_rate) / (100 + Decimal(payload.vat_rate))).to_integral_value(ROUND_HALF_UP)) if payload.category in {'fee_income', 'other_income', 'expense'} else 0
            entry = insert(c, user['id'], source['id'], day, signed, payload.category, payload.text, now, case_id, None, payload.counterparty, payload.vat_rate, vat if signed > 0 else -vat)
            if case_id:
                record_activity(c, case_id, 'ledger_' + payload.category, payload.text)
            return {'id': entry}

    @r.post('/api/ledger/entries/{entry_id}/reverse')
    def reverse(entry_id: str, payload: Reverse, user: dict = Depends(require_user)):
        # Bookings are never edited or deleted: a reversal books the opposite amount (with its pair, if any).
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM ledger_entries WHERE id=? AND user_id=?', (entry_id, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, 'Not found')
            group = c.execute('SELECT * FROM ledger_entries WHERE pair_id=?', (row['pair_id'],)).fetchall() if row['pair_id'] else [row]
            if any(item['reversed_by'] or item['reverses'] for item in group):
                raise HTTPException(409, 'already_reversed')
            today = date.today().isoformat()
            for item in group:
                back = insert(c, user['id'], item['account_id'], today, -item['amount_minor'], item['category'], f'Storno: {item["text"]} ({payload.reason.strip()})', now,
                              item['case_id'], item['invoice_id'], item['counterparty'], item['vat_rate'], -item['vat_minor'], reverses=item['id'])
                c.execute('UPDATE ledger_entries SET reversed_by=? WHERE id=?', (back, item['id']))
                if item['category'] == 'fee_income' and item['invoice_id']:
                    pay_invoice(c, user['id'], item['invoice_id'], today, -item['amount_minor'], 'Storno Zahlung', now)
        return {'reversed': True}

    @r.get('/api/ledger/vat')
    def vat_return(year: int, period: str = Query(pattern=r'^(0[1-9]|1[0-2]|Q[1-4])$'), user: dict = Depends(require_user)):
        months = [int(period)] if not period.startswith('Q') else [3 * (int(period[1]) - 1) + m for m in (1, 2, 3)]
        with db() as c:
            rows = [dict(row) for row in c.execute("SELECT * FROM ledger_entries WHERE user_id=? AND day LIKE ? AND category IN ('fee_income','other_income','expense')", (user['id'], f'{year}-%'))]
        rows = [row for row in rows if int(row['day'][5:7]) in months]
        income = [row for row in rows if row['category'] != 'expense']
        # Net income per rate (reversals included with their negative amounts).
        sales19 = sum(row['amount_minor'] - row['vat_minor'] for row in income if row['vat_rate'] == '19')
        sales7 = sum(row['amount_minor'] - row['vat_minor'] for row in income if row['vat_rate'] == '7')
        output_vat = sum(row['vat_minor'] for row in income)
        input_vat = -sum(row['vat_minor'] for row in rows if row['category'] == 'expense')
        return {'year': year, 'period': period, 'kz81_minor': sales19, 'kz86_minor': sales7, 'output_vat_minor': output_vat, 'kz66_minor': input_vat,
                'kz83_minor': output_vat - input_vat, 'basis': 'Ist-Versteuerung (§ 20 UStG): Einnahmen und Ausgaben im Zahlungszeitraum'}

    @r.get('/api/ledger/datev-settings')
    def datev_settings(user: dict = Depends(require_user)):
        with db() as c:
            row = c.execute('SELECT datev FROM ledger_settings WHERE user_id=?', (user['id'],)).fetchone()
        return {**DEFAULT_DATEV, **(json.loads(row['datev']) if row else {})}

    @r.put('/api/ledger/datev-settings')
    def save_datev(payload: DatevSettings, user: dict = Depends(require_user)):
        with db() as c:
            c.execute('INSERT INTO ledger_settings VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET datev=excluded.datev', (user['id'], json.dumps(payload.accounts)))
        return datev_settings(user)

    @r.get('/api/ledger/datev.csv')
    def datev(year: int, user: dict = Depends(require_user)):
        numbers = datev_settings(user)
        out = io.StringIO()
        writer = csv.writer(out, delimiter=';')
        writer.writerow(['Umsatz (ohne Soll/Haben-Kz)', 'Soll/Haben-Kennzeichen', 'Konto', 'Gegenkonto (ohne BU-Schlüssel)', 'BU-Schlüssel', 'Belegdatum', 'Belegfeld 1', 'Buchungstext'])
        bu = {('in', '19'): '3', ('in', '7'): '2', ('out', '19'): '9', ('out', '7'): '8'}
        with db() as c:
            kinds = {a['id']: a['kind'] for a in accounts(c, user['id'], now)}
            cases = {row['id']: row['reference'] for row in c.execute('SELECT id,reference FROM cases WHERE user_id=?', (user['id'],))}
            invoices = {row['id']: row['number'] for row in c.execute('SELECT id,number FROM invoices WHERE user_id=?', (user['id'],))}
            for row in c.execute('SELECT * FROM ledger_entries WHERE user_id=? AND day LIKE ? ORDER BY day,created_at', (user['id'], f'{year}-%')).fetchall():
                kind = kinds.get(row['account_id'], 'office')
                money_account = numbers['trust' if kind == 'trust' else 'cash' if kind == 'cash' else 'bank']
                counter = {'fee_income': numbers['revenue_' + row['vat_rate']], 'other_income': numbers['other_income'], 'expense': numbers['expense'], 'private': numbers['private'],
                           'trust_in': numbers['client_money'], 'trust_out': numbers['client_money'], 'trust_to_fees': numbers['client_money'], 'transfer': numbers['bank']}[row['category']]
                if row['category'] == 'transfer' and row['amount_minor'] < 0:
                    continue    # a transfer is exported once, from its receiving side
                direction = 'in' if row['amount_minor'] > 0 else 'out'
                key = bu.get((direction, row['vat_rate']), '') if row['category'] in {'fee_income', 'other_income', 'expense'} else ''
                amount = f'{abs(row["amount_minor"]) / 100:.2f}'.replace('.', ',')
                document = invoices.get(row['invoice_id']) or cases.get(row['case_id']) or ''
                writer.writerow([amount, 'S' if direction == 'in' else 'H', money_account, counter, key, date.fromisoformat(row['day']).strftime('%d%m'), document, row['text'][:60]])
        return Response('﻿' + out.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="DATEV-Buchungen-{year}.csv"'})

    @r.get('/api/ledger/statistics')
    def statistics(year: int, user: dict = Depends(require_user)):
        with db() as c:
            fees = {row['month']: row['total'] for row in c.execute("SELECT substr(day,6,2) AS month,SUM(amount_minor-vat_minor) AS total FROM ledger_entries WHERE user_id=? AND category='fee_income' AND day LIKE ? GROUP BY month", (user['id'], f'{year}-%'))}
            open_items = c.execute("SELECT COUNT(*),COALESCE(SUM(i.payable_minor-COALESCE((SELECT SUM(amount_minor) FROM invoice_payments p WHERE p.invoice_id=i.id),0)),0) FROM invoices i WHERE i.user_id=? AND i.status='open'", (user['id'],)).fetchone()
            overdue = c.execute("SELECT COUNT(*) FROM invoices WHERE user_id=? AND status='open' AND issued_on<?", (user['id'], (date.today() - timedelta(days=30)).isoformat())).fetchone()[0]
            cases = [json.loads(row['details']) | {'archived': bool(row['archived_at'])} for row in c.execute('SELECT details,archived_at FROM cases WHERE user_id=?', (user['id'],))]
        by_status, by_area = {}, {}
        for item in cases:
            status = 'archived' if item['archived'] else item.get('status', 'active')
            by_status[status] = by_status.get(status, 0) + 1
            if not item['archived']:
                area = item.get('legal_area', 'general')
                by_area[area] = by_area.get(area, 0) + 1
        return {'year': year, 'fees_by_month': [{'month': f'{m:02d}', 'net_minor': fees.get(f'{m:02d}', 0)} for m in range(1, 13)],
                'fees_total_minor': sum(fees.values()), 'open_count': open_items[0], 'open_minor': open_items[1], 'overdue_count': overdue,
                'cases_by_status': by_status, 'cases_by_area': by_area}

    return r
