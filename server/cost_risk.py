"""Litigation cost risk (Prozesskostenrisiko) for German civil and labour courts – plain table arithmetic, no AI.

Fees from the tables in fee_tables (RVG / GKG, BGBl. 2025 I Nr. 109), values up to 500,000 EUR.
Civil court, first instance: lawyer 1.3 VV 3100 + 1.2 VV 3104 (+ 1.0 VV 1003 settlement), court 3.0 KV 1210 (1.0 KV 1211 on settlement).
Civil appeal: lawyer 1.6 VV 3200 + 1.2 VV 3202 (+ 1.3 VV 1004), court 4.0 KV 1220 (2.0 KV 1222 on settlement).
Labour court, first instance: same lawyer fees, court 2.0 KV 8210 (no court fee on settlement, Vorbem. 8 KV),
and no reimbursement of the other side's lawyer (§ 12a Abs. 1 ArbGG).
Each lawyer: postage/telecom flat rate 20 % of the fees, at most 20 EUR (VV 7002), plus 19 % VAT (VV 7008).
Allocation: loss = everything; win = nothing (except own lawyer in labour court); quota per § 92 ZPO;
settlement: costs set against each other (each pays own lawyer, court fee halved, § 98 ZPO).
Not covered: Mehrvergleich, Beweisaufnahme costs (witnesses, experts), travel, Verkehrsanwalt, PKH, Mahnverfahren credit,
fee agreements, values over 500,000 EUR, and anything other than the standard scenario.
"""
import io
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .fee_tables import COURT, RVG, VALUES

CENT = Decimal('0.01')
VAT = Decimal('0.19')
INSTANCES = {
    'civil_first': {'label': 'Zivilgericht, 1. Instanz', 'procedure': ('1.3', 'VV 3100'), 'hearing': ('1.2', 'VV 3104'), 'settlement': ('1.0', 'VV 1003'),
                    'court': ('3.0', 'KV 1210'), 'court_settled': ('1.0', 'KV 1211'), 'reimburse_lawyer': True},
    'civil_appeal': {'label': 'Berufung', 'procedure': ('1.6', 'VV 3200'), 'hearing': ('1.2', 'VV 3202'), 'settlement': ('1.3', 'VV 1004'),
                     'court': ('4.0', 'KV 1220'), 'court_settled': ('2.0', 'KV 1222'), 'reimburse_lawyer': True},
    'labour_first': {'label': 'Arbeitsgericht, 1. Instanz', 'procedure': ('1.3', 'VV 3100'), 'hearing': ('1.2', 'VV 3104'), 'settlement': ('1.0', 'VV 1003'),
                     'court': ('2.0', 'KV 8210'), 'court_settled': ('0', 'Vorbem. 8 KV'), 'reimburse_lawyer': False},
}


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def base_fees(value: Decimal):
    if not Decimal(0) < value <= Decimal(500000):
        raise ValueError('value_out_of_range')
    index = next(i for i, limit in enumerate(VALUES) if value <= limit)
    return Decimal(RVG[index]), Decimal(COURT[index]), VALUES[index]


def lawyer(base: Decimal, spec: dict, hearing: bool, settled: bool, vat: bool):
    lines = [(f'Verfahrensgebühr {spec["procedure"][1]} ({spec["procedure"][0].replace(".", ",")})', cents(base * Decimal(spec['procedure'][0])))]
    if hearing:
        lines.append((f'Terminsgebühr {spec["hearing"][1]} ({spec["hearing"][0].replace(".", ",")})', cents(base * Decimal(spec['hearing'][0]))))
    if settled:
        lines.append((f'Einigungsgebühr {spec["settlement"][1]} ({spec["settlement"][0].replace(".", ",")})', cents(base * Decimal(spec['settlement'][0]))))
    fees = sum(amount for _, amount in lines)
    lines.append(('Post- und Telekommunikationspauschale VV 7002', min(cents(fees * Decimal('0.2')), Decimal('20.00'))))
    net = sum(amount for _, amount in lines)
    tax = cents(net * VAT) if vat else Decimal('0.00')
    if vat:
        lines.append(('19 % Umsatzsteuer VV 7008', tax))
    return {'lines': [{'label': label, 'amount': str(amount)} for label, amount in lines], 'net': net, 'total': net + tax}


def calculate(value: Decimal, instance: str, hearing: bool = True, own_vat_deductible: bool = False, opponent_vat_deductible: bool = False, win_percent: int = 50):
    spec = INSTANCES[instance]
    rvg, court_base, bracket = base_fees(value)
    court_rate, court_code = spec['court']
    settled_rate, settled_code = spec['court_settled']
    court = cents(court_base * Decimal(court_rate))
    court_settled = cents(court_base * Decimal(settled_rate))
    own = lawyer(rvg, spec, hearing, False, not own_vat_deductible)
    other = lawyer(rvg, spec, hearing, False, not opponent_vat_deductible)
    own_settled = lawyer(rvg, spec, hearing, True, not own_vat_deductible)
    other_settled = lawyer(rvg, spec, hearing, True, not opponent_vat_deductible)
    reimburse = spec['reimburse_lawyer']
    quota = Decimal(100 - win_percent) / 100

    if reimburse:
        loss = court + own['total'] + other['total']
        win = Decimal('0.00')
        # § 92 ZPO: the client bears the share it loses of all costs (court + both lawyers).
        share = cents((court + own['total'] + other['total']) * quota)
    else:
        loss = court + own['total']
        win = own['total']
        share = cents(court * quota) + own['total']
    settlement = cents(court_settled / 2) + own_settled['total']
    scenarios = [
        {'id': 'loss', 'label': 'Vollständiges Unterliegen', 'amount': str(loss)},
        {'id': 'quota', 'label': f'Teilweises Obsiegen ({win_percent} %) nach § 92 ZPO', 'amount': str(share)},
        {'id': 'win', 'label': 'Vollständiges Obsiegen', 'amount': str(win)},
        {'id': 'settlement', 'label': 'Vergleich, Kosten gegeneinander aufgehoben', 'amount': str(settlement)},
    ]
    return {
        'value': str(value), 'bracket': str(bracket), 'instance': instance, 'instance_label': spec['label'], 'hearing': hearing, 'win_percent': win_percent,
        'base_fee_rvg': str(rvg), 'base_fee_court': str(court_base),
        'court': {'label': f'Gerichtsgebühr {court_code} ({court_rate.replace(".", ",")})', 'amount': str(court),
                  'settled_label': f'bei Vergleich {settled_code} ({settled_rate.replace(".", ",")})', 'settled_amount': str(court_settled)},
        'own_lawyer': {**own, 'net': str(own['net']), 'total': str(own['total'])},
        'other_lawyer': {**other, 'net': str(other['net']), 'total': str(other['total'])},
        'own_lawyer_settled_total': str(own_settled['total']), 'other_lawyer_settled_total': str(other_settled['total']),
        'advance': str(court) if instance != 'labour_first' else '0.00',
        'reimburse_lawyer': reimburse, 'scenarios': scenarios,
        'notes': ([] if reimburse else ['Arbeitsgericht 1. Instanz: Jede Seite trägt ihre Anwaltskosten selbst, auch bei Obsiegen (§ 12a Abs. 1 ArbGG). Gerichtskosten werden erst am Ende fällig (§ 6 Abs. 4 GKG).'])
        + ([] if not own_vat_deductible else ['Eigene Anwaltskosten ohne Umsatzsteuer gerechnet (Mandant vorsteuerabzugsberechtigt).'])
        + ['Gebühren nach RVG/GKG in der Fassung des BGBl. 2025 I Nr. 109. Nicht enthalten: Auslagen für Zeugen und Sachverständige, Reisekosten, Mehrvergleich, abweichende Vergütungsvereinbarung.'],
    }


class RiskInput(BaseModel):
    model_config = {'extra': 'forbid'}
    value: Decimal = Field(gt=0, le=500000, max_digits=9, decimal_places=2)
    instance: Literal['civil_first', 'civil_appeal', 'labour_first'] = 'civil_first'
    hearing: bool = True
    own_vat_deductible: bool = False
    opponent_vat_deductible: bool = False
    win_percent: int = Field(default=50, ge=0, le=100)
    client_name: str = Field(default='', max_length=200)
    reference: str = Field(default='', max_length=100)
    matter: str = Field(default='', max_length=300)


def euro(value):
    text = f'{Decimal(value):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{text} €'


def report_pdf(data: dict, payload: RiskInput) -> bytes:
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from .dates import display_date
    from datetime import date

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=9.5, leading=12.5, textColor=colors.HexColor('#1f2d26'))
    small = ParagraphStyle('small', parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor('#5d6b60'))
    bold = ParagraphStyle('bold', parent=base, fontName='Helvetica-Bold')
    right = ParagraphStyle('right', parent=base, alignment=TA_RIGHT)
    right_bold = ParagraphStyle('right_bold', parent=bold, alignment=TA_RIGHT)
    title = ParagraphStyle('title', parent=base, fontName='Helvetica-Bold', fontSize=16, leading=20, spaceAfter=4)
    heading = ParagraphStyle('heading', parent=base, fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=12, spaceAfter=6)
    cell = lambda text, style=base: Paragraph(escape(str(text)), style)
    style = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#d6ded2')),
             ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]

    def table(rows, bold_last=True):
        result = Table(rows, colWidths=[None, 34 * mm])
        result.setStyle(TableStyle(style + ([('LINEABOVE', (0, -1), (-1, -1), 0.8, colors.HexColor('#1f2d26')), ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f3f7f4'))] if bold_last else [])))
        return result

    head = [Paragraph('Prozesskostenrisiko', title)]
    meta = ' · '.join(filter(None, [payload.reference and f'Akte {payload.reference}', payload.client_name and f'für {payload.client_name}', payload.matter]))
    if meta:
        head.append(cell(meta))
    head += [cell(f'{data["instance_label"]} · Streitwert {euro(data["value"])} · Stand {display_date(date.today().isoformat())}', small), Spacer(1, 6)]

    scenario_rows = [[cell('Ausgang des Verfahrens', bold), cell('Ihr Kostenrisiko', right_bold)]]
    scenario_rows += [[cell(item['label']), cell(euro(item['amount']), right)] for item in data['scenarios']]
    scenario_table = Table(scenario_rows, colWidths=[None, 34 * mm])
    scenario_table.setStyle(TableStyle(style + [('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#2f5d4d')),
                                                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fbefe9'))]))
    story = head + [Paragraph('1. Überblick', heading), scenario_table]
    if data['advance'] != '0.00':
        story.append(Spacer(1, 4)); story.append(cell(f'Bei Einreichung der Klage ist ein Gerichtskostenvorschuss von {euro(data["advance"])} zu zahlen (§ 12 GKG).', small))

    def lawyer_rows(entry, label):
        rows = [[cell(line['label']), cell(euro(line['amount']), right)] for line in entry['lines']]
        rows.append([cell(label, bold), cell(euro(entry['total']), right_bold)])
        return rows

    story += [KeepTogether([Paragraph('2. Eigene Anwaltskosten', heading), table(lawyer_rows(data['own_lawyer'], 'Summe eigene Anwaltskosten'))]),
              KeepTogether([Paragraph('3. Anwaltskosten der Gegenseite', heading), table(lawyer_rows(data['other_lawyer'], 'Summe Anwaltskosten Gegenseite'))]),
              KeepTogether([Paragraph('4. Gerichtskosten', heading), table([[cell(data['court']['label']), cell(euro(data['court']['amount']), right)],
                                                                        [cell(data['court']['settled_label'], small), cell(euro(data['court']['settled_amount']), right)]], bold_last=False)]),
              Paragraph('5. Hinweise', heading)]
    for note in data['notes'] + ['Die Berechnung ist eine Schätzung auf Grundlage des angegebenen Streitwerts. Der tatsächliche Wert wird vom Gericht festgesetzt; Beweisaufnahmen und weitere Instanzen erhöhen die Kosten.']:
        story.append(cell('• ' + note, small))

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(colors.HexColor('#5d6b60'))
        canvas.drawString(20 * mm, 12 * mm, 'Prozesskostenrisiko · unverbindliche Berechnung nach RVG/GKG')
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f'Seite {doc.page}')
        canvas.restoreState()

    output = io.BytesIO()
    SimpleDocTemplate(output, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                      title='Prozesskostenrisiko', author='').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def run(payload: RiskInput):
    try:
        return calculate(payload.value, payload.instance, payload.hearing, payload.own_vat_deductible, payload.opponent_vat_deductible, payload.win_percent)
    except ValueError:
        raise HTTPException(422, 'value_out_of_range') from None


def router(require_user):
    routes = APIRouter()

    @routes.post('/api/cost-risk/calculate')
    def calculate_risk(payload: RiskInput, user: dict = Depends(require_user)):
        return run(payload)

    @routes.post('/api/cost-risk/report.pdf')
    def risk_report(payload: RiskInput, user: dict = Depends(require_user)):
        return Response(report_pdf(run(payload), payload), media_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="Prozesskostenrisiko.pdf"'})

    return routes
