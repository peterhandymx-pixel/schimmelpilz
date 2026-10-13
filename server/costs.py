"""Private invoice arithmetic. Inputs are manual; no statutory entitlement inference."""
import io
import json
import re
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from .fee_tables import FeeBasis, lookup
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

CENT = Decimal('0.01')


def number(value, places=2, signed=False, maximum='1000000000'):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,10}(?:\.\d{1,' + str(places) + r'})?', value):
        raise ValueError('Use a decimal string without thousands separators')
    amount = Decimal(value)
    if (not signed and amount < 0) or abs(amount) > Decimal(maximum):
        raise ValueError('Amount outside allowed range')
    return value


class Line(BaseModel):
    model_config = {'extra': 'forbid'}
    description: str = Field(min_length=1, max_length=300)
    quantity: str = '1'
    unit_net: str
    tax_rate: str = '0'
    billed_net: str | None = None
    evidence: str = Field(default='', max_length=500)
    fee_basis: FeeBasis | None = None

    @model_validator(mode='after')
    def verify_table_amount(self):
        if self.fee_basis and Decimal(self.unit_net) != Decimal(lookup(self.fee_basis)['base_fee']):
            raise ValueError('Table fee amount mismatch')
        return self

    @field_validator('description')
    @classmethod
    def description_nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Description required')
        return value

    @field_validator('quantity')
    @classmethod
    def quantity_valid(cls, value):
        return number(value, 4, maximum='1000000')

    @field_validator('unit_net')
    @classmethod
    def unit_valid(cls, value):
        return number(value, 4, signed=True)

    @field_validator('tax_rate')
    @classmethod
    def rate_valid(cls, value):
        return number(value, 4, maximum='100')

    @field_validator('billed_net')
    @classmethod
    def billed_valid(cls, value):
        return None if value is None else number(value, signed=True)


class Invoice(BaseModel):
    model_config = {'extra': 'forbid'}
    title: str = Field(min_length=1, max_length=160)
    kind: Literal['invoice', 'lawyer', 'court', 'operating'] = 'invoice'
    issuer: str = Field(default='', max_length=160)
    invoice_number: str = Field(default='', max_length=100)
    invoice_date: date | None = None
    document_id: uuid.UUID | None = None
    basis: str = Field(default='', max_length=3000)
    notes: str = Field(default='', max_length=4000)
    currency: Literal['EUR', 'USD', 'MXN'] = 'EUR'
    credit_gross: str = '0'
    billed_total: str
    lines: list[Line] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def table_currency(self):
        if self.currency!='EUR' and any(line.fee_basis for line in self.lines):
            raise ValueError('German fee tables require EUR')
        return self

    @field_validator('title')
    @classmethod
    def title_nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Title required')
        return value

    @field_validator('credit_gross')
    @classmethod
    def credit_valid(cls, value):
        return number(value)

    @field_validator('billed_total')
    @classmethod
    def total_valid(cls, value):
        return number(value, signed=True)


class SaveReview(Invoice):
    case_id: uuid.UUID


class UpdateReview(SaveReview):
    expected_version: int = Field(ge=1)


def money(value):
    rounded = value.quantize(CENT, rounding=ROUND_HALF_UP)
    return format(abs(rounded) if rounded == 0 else rounded, '.2f')


def calculate(invoice):
    rows, groups = [], {}
    for line in invoice.lines:
        net = Decimal(money(Decimal(line.quantity) * Decimal(line.unit_net)))
        rate = Decimal(line.tax_rate)
        groups[rate] = groups.get(rate, Decimal(0)) + net
        billed = Decimal(line.billed_net) if line.billed_net is not None else None
        rows.append({'net': money(net), 'difference': money(billed - net) if billed is not None else None, 'fee_source': lookup(line.fee_basis) if line.fee_basis else None})
    taxes = [{'rate': format(rate, 'f'), 'net': money(net), 'tax': money(net * rate / 100)} for rate, net in sorted(groups.items())]
    net = sum((Decimal(row['net']) for row in rows), Decimal(0))
    tax = sum((Decimal(group['tax']) for group in taxes), Decimal(0))
    gross = net + tax
    payable = gross - Decimal(invoice.credit_gross)
    difference = Decimal(invoice.billed_total) - payable
    return {'engine': 'invoice-decimal-v1', 'rounding': 'line net: half-up to cents; tax: half-up per rate group; credits: gross',
            'lines': rows, 'tax_groups': taxes, 'net': money(net), 'tax': money(tax), 'gross': money(gross),
            'payable': money(payable), 'difference': money(difference),
            'has_difference': difference != 0 or any(row['difference'] not in (None, '0.00') for row in rows),
            'legal_assessment': 'not_performed'}


def migrate(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS cost_reviews (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            case_id TEXT NOT NULL REFERENCES cases(id), document_id TEXT REFERENCES documents(id),
            version INTEGER NOT NULL, invoice TEXT NOT NULL, result TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS costs_owner_case ON cost_reviews(user_id,case_id);
        CREATE TABLE IF NOT EXISTS cost_review_versions (
            review_id TEXT NOT NULL REFERENCES cost_reviews(id), version INTEGER NOT NULL,
            invoice TEXT NOT NULL, result TEXT NOT NULL, saved_at TEXT NOT NULL,
            PRIMARY KEY(review_id,version)
        );
    ''')


def router(db, require_user, now, record_activity):
    routes = APIRouter()

    def owned(connection, review_id, user_id):
        row = connection.execute('SELECT * FROM cost_reviews WHERE id=? AND user_id=?', (review_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Cost review not found')
        return row

    def validate_case(connection, payload, user_id):
        case_id = str(payload.case_id)
        case = connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (case_id, user_id)).fetchone()
        if not case:
            raise HTTPException(404, 'Case not found')
        if any(line.fee_basis for line in payload.lines) and (payload.currency != 'EUR' or json.loads(case['details']).get('jurisdiction','DE') != 'DE'):
            raise HTTPException(422, 'German fee tables require an EUR case with DE jurisdiction')
        if payload.document_id and not connection.execute('SELECT 1 FROM documents WHERE id=? AND case_id=?', (str(payload.document_id), case_id)).fetchone():
            raise HTTPException(404, 'Case document not found')

    def public(connection, row):
        case = connection.execute('SELECT reference,title FROM cases WHERE id=?', (row['case_id'],)).fetchone()
        document = connection.execute('SELECT original_name FROM documents WHERE id=?', (row['document_id'],)).fetchone() if row['document_id'] else None
        return {'id': row['id'], 'case_id': row['case_id'], 'case_reference': case['reference'], 'case_title': case['title'],
                'document_name': document['original_name'] if document else None, 'version': row['version'],
                'invoice': json.loads(row['invoice']), 'result': json.loads(row['result']), 'created_at': row['created_at'], 'updated_at': row['updated_at']}

    @routes.post('/api/cost-reviews/calculate')
    def preview(payload: Invoice, user: dict = Depends(require_user)):
        return calculate(payload)

    @routes.get('/api/cost-reviews')
    def list_reviews(case_id: uuid.UUID | None = None, user: dict = Depends(require_user)):
        with db() as connection:
            if case_id and not connection.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?', (str(case_id), user['id'])).fetchone():
                raise HTTPException(404, 'Case not found')
            rows = connection.execute('SELECT * FROM cost_reviews WHERE user_id=?' + (' AND case_id=?' if case_id else '') + ' ORDER BY updated_at DESC,id', (user['id'], str(case_id)) if case_id else (user['id'],)).fetchall()
            return [public(connection, row) for row in rows]

    def save(payload, user, review_id=None):
        invoice = Invoice.model_validate(payload.model_dump(exclude={'case_id', 'expected_version'}))
        result = calculate(invoice)
        invoice_json = invoice.model_dump_json()
        result_json = json.dumps(result)
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            old = owned(connection, review_id, user['id']) if review_id else None
            if old and old['version'] != payload.expected_version:
                raise HTTPException(409, 'Cost review version changed')
            validate_case(connection, payload, user['id'])
            if old and old['case_id'] != str(payload.case_id):
                raise HTTPException(422, 'Saved review cannot change case')
            timestamp, version = now(), old['version'] + 1 if old else 1
            review_id = review_id or str(uuid.uuid4())
            if old:
                connection.execute('UPDATE cost_reviews SET document_id=?,version=?,invoice=?,result=?,updated_at=? WHERE id=?', (str(payload.document_id) if payload.document_id else None, version, invoice_json, result_json, timestamp, review_id))
            else:
                connection.execute('INSERT INTO cost_reviews VALUES(?,?,?,?,?,?,?,?,?)', (review_id, user['id'], str(payload.case_id), str(payload.document_id) if payload.document_id else None, version, invoice_json, result_json, timestamp, timestamp))
            connection.execute('INSERT INTO cost_review_versions VALUES(?,?,?,?,?)', (review_id, version, invoice_json, result_json, timestamp))
            record_activity(connection, str(payload.case_id), 'cost_review_saved', invoice.title)
            return public(connection, owned(connection, review_id, user['id']))

    @routes.post('/api/cost-reviews', status_code=201)
    def create(payload: SaveReview, user: dict = Depends(require_user)):
        return save(payload, user)

    @routes.put('/api/cost-reviews/{review_id}')
    def update(review_id: str, payload: UpdateReview, user: dict = Depends(require_user)):
        return save(payload, user, review_id)

    @routes.get('/api/cost-reviews/{review_id}/versions')
    def versions(review_id: str, user: dict = Depends(require_user)):
        with db() as connection:
            owned(connection, review_id, user['id'])
            return [{'version': row['version'], 'invoice': json.loads(row['invoice']), 'result': json.loads(row['result']), 'saved_at': row['saved_at']} for row in connection.execute('SELECT * FROM cost_review_versions WHERE review_id=? ORDER BY version DESC', (review_id,))]

    @routes.get('/api/cost-reviews/{review_id}/report.pdf')
    def report(review_id: str, lang: Literal['de', 'en'] = 'de', version: int | None = None, user: dict = Depends(require_user)):
        with db() as connection:
            item = public(connection, owned(connection, review_id, user['id']))
            if version is not None:
                saved = connection.execute('SELECT * FROM cost_review_versions WHERE review_id=? AND version=?', (review_id, version)).fetchone()
                if not saved:
                    raise HTTPException(404, 'Version not found')
                item.update(version=version, invoice=json.loads(saved['invoice']), result=json.loads(saved['result']), updated_at=saved['saved_at'])
        inv, result, de = item['invoice'], item['result'], lang == 'de'
        styles, output = getSampleStyleSheet(), io.BytesIO()
        story = []
        def paragraph(value, style='BodyText'):
            story.append(Paragraph(escape(str(value)).replace('\n', '<br/>'), styles[style]))
            story.append(Spacer(1, 6))
        paragraph('Schimmelpilz · ' + ('Kostenprüfung' if de else 'Cost review'), 'Title')
        paragraph(inv['title'], 'Heading2')
        paragraph(f"{item['case_reference']} · {item['case_title']} · Version {item['version']} · {item['updated_at']}")
        kinds = {'invoice': 'Rechnung', 'lawyer': 'Anwaltsrechnung', 'court': 'Gerichtskosten', 'operating': 'Betriebskosten'} if de else {'invoice': 'Invoice', 'lawyer': 'Lawyer invoice', 'court': 'Court costs', 'operating': 'Operating costs'}
        paragraph(f"{inv['issuer']} · {inv['invoice_number']} · {inv['invoice_date'] or '-'} · {kinds[inv['kind']]}")
        paragraph(('Rechenprüfung anhand manueller Eingaben. Keine rechtliche Freigabe.' if de else 'Arithmetic check using manual inputs. No legal approval.'))
        for idx, (line, checked) in enumerate(zip(inv['lines'], result['lines']), 1):
            paragraph(f"{idx}. {line['description']}: {line['quantity']} × {line['unit_net']} = {checked['net']} {inv['currency']}; {line['tax_rate']}%", 'Heading3')
            paragraph(f"{'Rechnungsnetto / Differenz' if de else 'Billed net / difference'}: {line['billed_net'] or '-'} / {checked['difference'] or '-'}; {'Beleg' if de else 'Evidence'}: {line['evidence'] or '-'}")
            source=checked.get('fee_source')
            if source:
                paragraph(f"{source['source']['citation']} · {source['version']} · 1.0: {source['base_fee']} EUR · {'Wertstufe' if de else 'Value bracket'}: {source['bracket']} EUR · {'Quellen geprüft' if de else 'Sources checked'}: {source['source_checked_on']}")
                paragraph(source['source']['table']+'\n'+source['source']['transition']+'\n'+source['applicability_note']+'\nSHA-256: '+source['table_sha256'])
        for group in result['tax_groups']:
            paragraph(f"{'Steuer auf netto' if de else 'Tax on net'} {group['net']} {inv['currency']} × {group['rate']}% = {group['tax']} {inv['currency']}")
        for label, value in [(('Netto' if de else 'Net'), result['net']), (('Steuer' if de else 'Tax'), result['tax']), (('Brutto' if de else 'Gross'), result['gross']), (('Abzüge brutto' if de else 'Gross credits'), inv['credit_gross']), (('Errechnet zahlbar' if de else 'Calculated payable'), result['payable']), (('Rechnung zahlbar' if de else 'Billed payable'), inv['billed_total']), (('Differenz: Rechnung minus errechnet' if de else 'Difference: billed minus calculated'), result['difference'])]:
            paragraph(f'{label}: {value} {inv["currency"]}')
        paragraph('Rundung: Positionsnetto kaufmännisch auf Cent; Steuer je Steuersatzgruppe auf Cent; Abzüge brutto.' if de else 'Rounding: line net half-up to cents; tax half-up per rate group; credits gross.')
        paragraph(('Grundlage / Tabellenstand / offene Rechtsfragen' if de else 'Basis / table version / unresolved legal issues'), 'Heading2')
        paragraph(inv['basis'] or ('Nicht erfasst' if de else 'Not recorded'))
        paragraph(inv['notes'] or '-')
        if item['document_name']:
            paragraph(('Verknüpftes Dokument: ' if de else 'Linked document: ') + item['document_name'])
        SimpleDocTemplate(output, title=inv['title']).build(story)
        return Response(output.getvalue(), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="cost-review-v{item["version"]}.pdf"'})

    return routes
