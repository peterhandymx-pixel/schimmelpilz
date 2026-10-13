"""Bounded 1.0 value-fee lookup, not a fee entitlement or transition-rule engine."""
import hashlib
import json
import re
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

VERSION='2025-bgbl-109'
CHECKED='2026-10-13'
VALUES=[500,1000,1500,2000,3000,4000,5000,6000,7000,8000,9000,10000,13000,16000,19000,22000,25000,30000,35000,40000,45000,50000,65000,80000,95000,110000,125000,140000,155000,170000,185000,200000,230000,260000,290000,320000,350000,380000,410000,440000,470000,500000]
RVG=['51.50','93.00','134.50','176.00','235.50','295.00','354.50','414.00','473.50','533.00','592.50','652.00','707.00','762.00','817.00','872.00','927.00','1013.00','1099.00','1185.00','1271.00','1357.00','1456.50','1556.00','1655.50','1755.00','1854.50','1954.00','2053.50','2153.00','2252.50','2352.00','2492.00','2632.00','2772.00','2912.00','3052.00','3192.00','3332.00','3472.00','3612.00','3752.00']
COURT=['40.00','61.00','82.00','103.00','125.50','148.00','170.50','193.00','215.50','238.00','260.50','283.00','313.50','344.00','374.50','405.00','435.50','476.00','516.50','557.00','597.50','638.00','778.00','918.00','1058.00','1198.00','1338.00','1478.00','1618.00','1758.00','1898.00','2038.00','2248.00','2458.00','2668.00','2878.00','3088.00','3298.00','3508.00','3718.00','3928.00','4138.00']
SOURCES={
    'rvg':{'table':'https://www.gesetze-im-internet.de/rvg/anlage_2.html','rule':'https://www.gesetze-im-internet.de/rvg/__13.html','transition':'https://www.gesetze-im-internet.de/rvg/__60.html','citation':'RVG Anlage 2 / § 13 Abs. 1; BGBl. 2025 I Nr. 109 S. 30'},
    'gkg':{'table':'https://www.gesetze-im-internet.de/gkg_2004/anlage_2.html','rule':'https://www.gesetze-im-internet.de/gkg_2004/__34.html','transition':'https://www.gesetze-im-internet.de/gkg_2004/__71.html','citation':'GKG Anlage 2 / § 34 Abs. 1; BGBl. 2025 I Nr. 109 S. 11'},
    'famgkg':{'table':'https://www.gesetze-im-internet.de/famgkg/anlage_2.html','rule':'https://www.gesetze-im-internet.de/famgkg/__28.html','transition':'https://www.gesetze-im-internet.de/famgkg/__63.html','citation':'FamGKG Anlage 2 / § 28 Abs. 1; BGBl. 2025 I Nr. 109'},
}


class FeeBasis(BaseModel):
    model_config={'extra':'forbid'}
    statute: Literal['rvg','gkg','famgkg']
    version: Literal['2025-bgbl-109'] = VERSION
    value: str
    applicability_confirmed: bool
    applicability_note: str = Field(min_length=10,max_length=1000)

    @field_validator('value')
    @classmethod
    def value_valid(cls,value):
        if not isinstance(value,str) or not re.fullmatch(r'\d{1,6}(?:\.\d{1,2})?',value) or not Decimal(0)<Decimal(value)<=Decimal(500000):
            raise ValueError('Value must be a positive decimal string up to 500000 EUR')
        return value

    @field_validator('applicability_confirmed')
    @classmethod
    def confirmed(cls,value):
        if not value:
            raise ValueError('Explicit applicability review required')
        return value

    @field_validator('applicability_note')
    @classmethod
    def note_valid(cls,value):
        if len(value.strip())<10:
            raise ValueError('Describe applicability and transition review')
        return value.strip()


def lookup(payload):
    amounts=RVG if payload.statute=='rvg' else COURT
    index=next(i for i,value in enumerate(VALUES) if Decimal(payload.value)<=value)
    source=SOURCES[payload.statute]
    digest=hashlib.sha256(json.dumps(list(zip(VALUES,amounts)),separators=(',',':')).encode()).hexdigest()
    return {'engine':'value-fee-table-v1','statute':payload.statute,'version':VERSION,'value':payload.value,'bracket':str(VALUES[index]),'base_fee':amounts[index],'currency':'EUR','source':source,'source_checked_on':CHECKED,'table_sha256':digest,'applicability':'user_declared','applicability_note':payload.applicability_note,'scope':'1.0 value fee only; no fee event, multiplier, special rule, credit or tax entitlement assessment'}


def router(require_user):
    routes=APIRouter()
    @routes.post('/api/fee-tables/calculate')
    def calculate(payload:FeeBasis,user:dict=Depends(require_user)):
        return lookup(payload)
    return routes
