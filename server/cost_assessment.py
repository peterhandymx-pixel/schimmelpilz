"""Kostenfestsetzungsantrag (§§ 103, 104 ZPO) as an editable draft: fixed wording and RVG/GKG arithmetic, no AI.

Lawyer fees from the RVG table (fee_tables), with optional credit of a pre-trial business fee (Vorbem. 3 Abs. 4 VV RVG,
§ 15a Abs. 2 RVG: half, at most 0.75), the postage flat rate (VV 7002) and VAT unless the client can deduct input tax
(§ 104 Abs. 2 Satz 3 ZPO). Court fees as actually paid. Interest at 5 points above the base rate from receipt (§ 104 Abs. 1 Satz 2 ZPO).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .cost_risk import CENT, INSTANCES, VAT, base_fees, cents, euro


class ExtraCost(BaseModel):
    model_config = {'extra': 'forbid'}
    label: str = Field(min_length=2, max_length=200)
    amount: Decimal = Field(gt=0, le=1000000, max_digits=10, decimal_places=2)


class AssessmentInput(BaseModel):
    model_config = {'extra': 'forbid'}
    value: Decimal = Field(gt=0, le=500000, max_digits=9, decimal_places=2)
    instance: Literal['civil_first', 'civil_appeal'] = 'civil_first'
    hearing: bool = True
    settlement: bool = False
    vat_deductible: bool = False
    business_fee_rate: Decimal = Field(default=Decimal('0'), ge=0, le=Decimal('2.5'), max_digits=3, decimal_places=1)
    court_fees_paid: Decimal = Field(default=Decimal('0'), ge=0, le=1000000, max_digits=10, decimal_places=2)
    extra_costs: list[ExtraCost] = Field(default_factory=list, max_length=10)
    client_role: Literal['plaintiff', 'defendant'] = 'plaintiff'
    title_kind: Literal['Urteil', 'Beschluss', 'Vergleich', 'Versäumnisurteil', 'Anerkenntnisurteil'] = 'Urteil'
    title_date: date | None = None
    cost_quota: int = Field(default=100, ge=1, le=100)


def calculate(payload: AssessmentInput):
    spec = INSTANCES[payload.instance]
    rvg, court_base, _ = base_fees(payload.value)
    lines = []
    procedure_rate = Decimal(spec['procedure'][0])
    lines.append({'label': f'{spec["procedure"][0].replace(".", ",")} Verfahrensgebühr, Nr. {spec["procedure"][1][3:]} VV RVG', 'amount': cents(rvg * procedure_rate)})
    if payload.business_fee_rate > 0 and payload.instance == 'civil_first':
        credit_rate = min(payload.business_fee_rate / 2, Decimal('0.75'))
        lines.append({'label': f'abzüglich anzurechnender Geschäftsgebühr {str(credit_rate).replace(".", ",")} (Vorbem. 3 Abs. 4 VV RVG, § 15a Abs. 2 RVG)', 'amount': -cents(rvg * credit_rate)})
    if payload.hearing:
        lines.append({'label': f'{spec["hearing"][0].replace(".", ",")} Terminsgebühr, Nr. {spec["hearing"][1][3:]} VV RVG', 'amount': cents(rvg * Decimal(spec['hearing'][0]))})
    if payload.settlement:
        lines.append({'label': f'{spec["settlement"][0].replace(".", ",")} Einigungsgebühr, Nr. {spec["settlement"][1][3:]} VV RVG', 'amount': cents(rvg * Decimal(spec['settlement'][0]))})
    fees = sum(line['amount'] for line in lines)
    lines.append({'label': 'Post- und Telekommunikationspauschale, Nr. 7002 VV RVG', 'amount': min(cents(fees * Decimal('0.2')), Decimal('20.00'))})
    net = sum(line['amount'] for line in lines)
    tax = Decimal('0.00') if payload.vat_deductible else cents(net * VAT)
    if not payload.vat_deductible:
        lines.append({'label': '19 % Umsatzsteuer, Nr. 7008 VV RVG', 'amount': tax})
    lawyer_total = net + tax
    other = [{'label': 'Verauslagte Gerichtskosten', 'amount': cents(payload.court_fees_paid)}] if payload.court_fees_paid > 0 else []
    other += [{'label': item.label, 'amount': cents(item.amount)} for item in payload.extra_costs]
    total = lawyer_total + sum(item['amount'] for item in other)
    return {'value_bracket_fee': rvg, 'lawyer_lines': lines, 'lawyer_total': lawyer_total, 'other': other, 'total': total,
            'court_fee_hint': cents(court_base * Decimal(spec['court_settled' if payload.settlement else 'court'][0]))}


def body(case: dict, user: dict, payload: AssessmentInput, result: dict) -> str:
    details = case.get('details') or {}
    client = details.get('client_name') or '[Mandant]'
    opponent = details.get('opponent_name') or '[Gegner]'
    plaintiff, defendant = (client, opponent) if payload.client_role == 'plaintiff' else (opponent, client)
    applicant_role = 'Kläger/in' if payload.client_role == 'plaintiff' else 'Beklagte/n'
    opponent_role = 'Beklagte/n' if payload.client_role == 'plaintiff' else 'Kläger/in'
    court = details.get('court') or '[Gericht]'
    court_reference = details.get('court_reference') or '[Az. des Gerichts]'
    genitive = {'Urteil': 'Urteils', 'Versäumnisurteil': 'Versäumnisurteils', 'Anerkenntnisurteil': 'Anerkenntnisurteils', 'Beschluss': 'Beschlusses', 'Vergleich': 'Vergleichs'}
    title = f'{genitive[payload.title_kind]} vom {payload.title_date.strftime("%d.%m.%Y") if payload.title_date else "[Datum]"}'
    row = lambda item: f'{item["label"]}: {euro(item["amount"]).replace("-", "– ")}'
    parts = [court.replace(', ', '\n'), '', f'Az.: {court_reference}', f'Unser Zeichen: {case.get("reference", "")}', '',
             'KOSTENFESTSETZUNGSANTRAG', '', 'In dem Rechtsstreit', '', f'{plaintiff}', '– Kläger/in –', '', 'gegen', '', f'{defendant}', '– Beklagte/r –', '',
             f'beantrage ich namens und in Vollmacht der/des {applicant_role},',
             f'die von der/dem {opponent_role} an die/den {applicant_role} zu erstattenden Kosten auf Grund des {title} nach der folgenden Berechnung festzusetzen '
             'und auszusprechen, dass der festgesetzte Betrag ab Eingang dieses Antrags mit fünf Prozentpunkten über dem Basiszinssatz zu verzinsen ist (§ 104 Abs. 1 Satz 2 ZPO).']
    if payload.cost_quota < 100:
        parts += ['', f'Nach der Kostenentscheidung trägt die/der {opponent_role} {payload.cost_quota} % der Kosten des Rechtsstreits. '
                      'Es wird beantragt, die Kosten nach § 106 ZPO auszugleichen; die Gegenseite möge ihre Kostenberechnung einreichen.']
    parts += ['', 'Kostenberechnung', '', f'Gegenstandswert: {euro(payload.value)}', '']
    parts += [row(line) for line in result['lawyer_lines']]
    parts += [f'Summe Rechtsanwaltsvergütung: {euro(result["lawyer_total"])}', '']
    if result['other']:
        parts += [row(item) for item in result['other']] + ['']
    parts += [f'Gesamtbetrag: {euro(result["total"])}', '']
    if payload.vat_deductible:
        parts.append('Die Umsatzsteuer wird nicht geltend gemacht, da die/der ' + applicant_role + ' zum Vorsteuerabzug berechtigt ist.')
    else:
        parts.append('Die/Der ' + applicant_role + ' ist nicht zum Vorsteuerabzug berechtigt (§ 104 Abs. 2 Satz 3 ZPO).')
    if result['other'] and payload.court_fees_paid > 0:
        parts.append('Die Gerichtskosten wurden von der/dem ' + applicant_role + ' eingezahlt; wir bitten, die Zahlung anhand der Gerichtsakte festzustellen.')
    parts += ['', 'Die Kosten sind entstanden; die Auslagen werden anwaltlich versichert (§ 104 Abs. 2 Satz 1 und 2 ZPO).', '',
              'Es wird gebeten, eine Ausfertigung des Kostenfestsetzungsbeschlusses zu erteilen.', '', '', user.get('full_name') or '[Name]', 'Rechtsanwältin / Rechtsanwalt']
    return '\n'.join(parts)


def router(require_user, get_case):
    routes = APIRouter()

    @routes.post('/api/cases/{case_id}/cost-assessment')
    def assessment(case_id: str, payload: AssessmentInput, user: dict = Depends(require_user)):
        case = get_case(case_id, user['id'])
        try:
            result = calculate(payload)
        except ValueError:
            raise HTTPException(422, 'value_out_of_range') from None
        text = body(case, user, payload, result)
        recipient = (case.get('details') or {}).get('court') or ''
        return {'body': text, 'recipient': recipient, 'total': str(result['total']), 'lawyer_total': str(result['lawyer_total']),
                'court_fee_hint': str(result['court_fee_hint']),
                'lines': [{'label': line['label'], 'amount': str(line['amount'])} for line in result['lawyer_lines'] + result['other']]}

    return routes
