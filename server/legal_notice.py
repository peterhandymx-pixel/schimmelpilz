"""Public operator particulars for the Impressum and privacy notice, taken from the operator's .env (never invented)."""
import os

from fastapi import APIRouter

from . import billing
from .research import AI_PROVIDER

FIELDS=('NAME','LEGAL_FORM','REPRESENTATIVE','ADDRESS','EMAIL','PHONE','REGISTER','TAX_ID','CONTENT_RESPONSIBLE','HOSTING','MAIL_PROVIDER')
REQUIRED=('name','address','email')


def particulars():
    values={field.lower():os.getenv('OPERATOR_'+field,'').strip()[:500] for field in FIELDS}
    # One .env line per field: address lines are separated by semicolons.
    values['address']=[line.strip() for line in values['address'].split(';') if line.strip()]
    return values


def router():
    r=APIRouter()

    @r.get('/api/public/operator')
    def operator():
        values=particulars()
        return {**values,'complete':all(values[key] for key in REQUIRED),'ai_provider':AI_PROVIDER,'payments':None if billing.demo_mode() else 'clip' if any(billing.links_ready().values()) else None}
    return r
