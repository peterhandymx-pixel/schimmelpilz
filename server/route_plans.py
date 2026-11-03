"""Source-backed, bounded procedural working papers. No binding court selection."""
import json
import re
from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from .letterheads import compose_pdf
from .word_export import compose_docx
from .exports import DOCX
from .dates import display_date

CHECKED='2026-10-13'
RULES={
 'civil':[('GVG § 23','https://www.gesetze-im-internet.de/gvg/__23.html'),('GVG § 71','https://www.gesetze-im-internet.de/gvg/__71.html'),('ZPO §§ 13, 17','https://www.gesetze-im-internet.de/zpo/__13.html'),('ZPO § 17','https://www.gesetze-im-internet.de/zpo/__17.html'),('ZPO § 78','https://www.gesetze-im-internet.de/zpo/__78.html'),('ZPO § 253','https://www.gesetze-im-internet.de/zpo/__253.html')],
 'tenancy':[('GVG § 23 Nr. 2 a','https://www.gesetze-im-internet.de/gvg/__23.html'),('ZPO § 29a','https://www.gesetze-im-internet.de/zpo/__29a.html'),('ZPO § 253','https://www.gesetze-im-internet.de/zpo/__253.html')],
 'employment':[('ArbGG § 2 Abs. 1 Nr. 3','https://www.gesetze-im-internet.de/arbgg/__2.html')],
 'administrative':[('VwGO § 40','https://www.gesetze-im-internet.de/vwgo/__40.html')],
 'social':[('SGG § 51','https://www.gesetze-im-internet.de/sgg/__51.html')],
 'other':[],
}


class PlanInput(BaseModel):
    model_config={'extra':'forbid'}
    language: Literal['de','en']='de'
    category: Literal['civil','tenancy','employment','administrative','social','other']='civil'
    goal: str=Field(min_length=10,max_length=2000)
    claim_value: str|None=None
    filing_date: date|None=None
    opponent_kind: Literal['person','organisation']='person'
    opponent_place: str=Field(default='',max_length=300)
    property_place: str=Field(default='',max_length=300)
    cross_border: bool=False
    special_jurisdiction: bool=True
    chosen_body: str=Field(default='',max_length=300)
    evidence: str=Field(default='',max_length=3000)
    review_note: str=Field(default='',max_length=3000)
    expected_version: int=Field(default=0,ge=0)

    @field_validator('claim_value')
    @classmethod
    def value_valid(cls,value):
        if value is not None and (not isinstance(value,str) or not re.fullmatch(r'\d{1,10}(?:\.\d{1,2})?',value) or Decimal(value)>1000000000):
            raise ValueError('Invalid value')
        return value

    @field_validator('goal')
    @classmethod
    def goal_valid(cls,value):
        if len(value.strip())<10:
            raise ValueError('Describe the desired result')
        return value.strip()


def prepare(payload,jurisdiction):
    de=payload.language=='de'
    def choose(german,english):return german if de else english
    missing=[]
    court=choose('Noch gesondert zu bestimmen','Requires separate determination')
    venue=choose('Örtliche Zuständigkeit offen','Territorial venue unresolved')
    representation=choose('Vertretung / Form gesondert prüfen','Review representation / form separately')
    sources=[]
    if jurisdiction!='DE' or payload.cross_border:
        missing.append(choose('Internationalen Rechtsweg, Gerichtsstand und anwendbare Instrumente anhand eigener Quellen prüfen. Keine deutsche Wertgrenze anwenden.','Review international jurisdiction, venue and applicable instruments using dedicated sources. Do not apply the German value threshold.'))
    else:
        sources=[{'label':label,'url':url,'checked_on':CHECKED} for label,url in RULES[payload.category]]
        if payload.category=='civil':
            if payload.special_jurisdiction:
                missing.append(choose('Sonderzuständigkeiten noch nicht ausgeschlossen: insbesondere GVG § 71 Abs. 2 (z. B. Heilbehandlung, Veröffentlichungen, Vergabe) und GVG § 23 Nr. 2 prüfen.','Special jurisdiction is not excluded: check GVG § 71(2), including medical treatment, publications and procurement, and GVG § 23(2).'))
            if not payload.filing_date or payload.filing_date<date(2026,1,1):
                missing.append(choose('Für vor 2026 begonnene Verfahren oder unbekannten Beginn: historische Fassung und Übergangsrecht prüfen. Dieser Rechner ordnet solche Verfahren nicht nach der 10.000-EUR-Grenze ein.','For proceedings started before 2026 or unknown start: review historical law and transition rules. This tool does not classify those proceedings using the EUR 10,000 threshold.'))
            if payload.claim_value is None:
                missing.append(choose('Zuständigkeitsstreitwert ermitteln und dokumentieren.','Determine and record the jurisdictional dispute value.'))
            if not missing:
                regional=Decimal(payload.claim_value)>10000
                court='Landgericht' if regional else 'Amtsgericht'
                representation=choose('Vor dem Landgericht grundsätzlich anwaltliche Vertretung (§ 78 ZPO).','Representation by a lawyer generally required before the Landgericht (§ 78 ZPO).') if regional else choose('Kein allgemeiner Anwaltszwang aus § 78 Abs. 1 ZPO vor dem Amtsgericht; besondere Verfahren gesondert prüfen.','No general lawyer requirement under § 78(1) ZPO before the Amtsgericht; review special proceedings separately.')
            venue=choose('Ausgangspunkt: Wohnsitz der beklagten Person (§ 13 ZPO)' if payload.opponent_kind=='person' else 'Ausgangspunkt: Sitz der beklagten Organisation (§ 17 ZPO)','Starting point: defendant residence (§ 13 ZPO)' if payload.opponent_kind=='person' else 'Starting point: defendant organisation seat (§ 17 ZPO)')
            if payload.opponent_place:
                venue+=' · '+payload.opponent_place
            else:
                missing.append(choose('Vollständige Zustellanschrift der Gegenseite fehlt.','Complete service address of the defendant is missing.'))
            missing.append(choose('Besondere / ausschließliche Gerichtsstände, Gerichtsstandsvereinbarungen, Landesrecht und das konkrete Gericht im Verzeichnis prüfen.','Review special/exclusive venues, venue agreements, state law and the specific court in the directory.'))
        elif payload.category=='tenancy':
            court=choose('Amtsgericht für Ansprüche aus Wohnraummiete / Bestand des Mietverhältnisses (§ 23 Nr. 2 a GVG)','Amtsgericht for residential tenancy claims / existence of the tenancy (§ 23 no. 2(a) GVG)')
            venue=choose('Regelmäßig Bezirk der Mieträume (§ 29a ZPO), Ausnahmen nach Abs. 2 prüfen.','Generally the district of the rented premises (§ 29a ZPO); check paragraph 2 exceptions.')
            if payload.property_place:venue+=' · '+payload.property_place
            else:missing.append(choose('Anschrift der Mieträume fehlt.','Address of the rented premises is missing.'))
            missing.append(choose('Wohnraummiete und Abgrenzung zu Gewerberaum bestätigen; Ausnahmen, historische Fassung und konkretes Gericht prüfen.','Confirm residential tenancy versus commercial premises; review exceptions, historical version and the specific court.'))
        elif payload.category=='employment':
            court=choose('Arbeitsgericht als möglicher Rechtsweg bei Arbeitnehmer-/Arbeitgeberstreit aus dem Arbeitsverhältnis (§ 2 ArbGG)','Arbeitsgericht as a possible route for employee/employer disputes arising from employment (§ 2 ArbGG)')
            missing.append(choose('Arbeitnehmerstatus, Streitgegenstand, örtliches Gericht, Vertretung und besondere Fristen gesondert prüfen.','Separately review employee status, dispute, venue, representation and special time limits.'))
        elif payload.category=='administrative':
            court=choose('Verwaltungsrechtsweg als Möglichkeit nach § 40 VwGO; ausdrückliche Sonderzuweisungen ausschließen.','Administrative court route may apply under § 40 VwGO; exclude explicit assignments to another court system.')
            missing.append(choose('Bescheid, Rechtsbehelfsbelehrung, Landesrecht, Vorverfahren, Klageart und sachliche/örtliche Zuständigkeit prüfen.','Review decision, remedy notice, state law, preliminary procedure, claim type and subject-matter/territorial jurisdiction.'))
        elif payload.category=='social':
            court=choose('Sozialgerichtsbarkeit als Möglichkeit für die in § 51 SGG genannten Angelegenheiten.','Social court jurisdiction may apply to matters enumerated in § 51 SGG.')
            missing.append(choose('Leistungsart, Bescheid, Rechtsbehelfsbelehrung, Vorverfahren und konkretes Sozialgericht prüfen.','Review benefit type, decision, remedy notice, preliminary procedure and the specific social court.'))
        else:
            missing.append(choose('Rechtsgebiet und spezialgesetzliche Zuständigkeit zunächst recherchieren.','Research the legal area and specialised jurisdiction first.'))
    routes=[{'title':choose('Außergerichtliche Klärung','Out-of-court clarification'),'goal':choose('Erläuterung, Unterlagen oder einvernehmliche Lösung anfordern.','Request clarification, evidence or an agreed resolution.'),'next':choose('Sachverhalt, Ziel und Belege in ein überprüfbares Anschreiben übernehmen. Fristen laufen dadurch nicht automatisch anders.','Prepare a reviewable letter with facts, objective and evidence. This does not automatically change time limits.')},
            {'title':choose('Gerichtlichen / behördlichen Schritt vorbereiten','Prepare a court / authority step'),'goal':payload.goal,'next':choose('Zuständigkeit, zulässigen Antrag, Beweismittel, Form, Vertretung, Fristen und Kosten vor Verwendung gesondert prüfen.','Separately review jurisdiction, admissible relief, evidence, form, representation, time limits and costs before use.')}]
    return {'engine':'route-working-paper-v1','jurisdiction':jurisdiction,'language':payload.language,'court_candidate':court,'venue':venue,'representation':representation,'missing':missing,'sources':sources,'routes':routes,'source_checked_on':CHECKED,'legal_approval':False,'court_directory':'https://www.justiz.de/service/verzeichnisse/index.php','filing_notice':choose('Eine veröffentlichte E-Mail-Adresse ist keine Bestätigung eines zulässigen Einreichungswegs. Es wird nichts eingereicht.','A published email address does not confirm a permitted filing channel. Nothing is filed.')}


def body(plan,reference):
    data,result=plan['input'],plan['result'];de=data['language']=='de'
    parts=['Schimmelpilz · '+('Zuständigkeit & Verfahrenswege' if de else 'Jurisdiction & procedural routes'),reference+' · v'+str(plan['version']),('Arbeitsblatt, keine abschließende Zuständigkeitsprüfung.' if de else 'Working paper, not a final jurisdiction assessment.'),data['goal'],result['court_candidate'],result['venue'],result['representation']]
    if data['chosen_body']:parts.append(('Von Ihnen eingetragene Stelle, nicht verifiziert: ' if de else 'Body entered by you, not verified: ')+data['chosen_body'])
    parts.extend(result['missing'])
    for route in result['routes']:parts.extend([route['title'],route['goal'],route['next']])
    parts.extend([('Belege' if de else 'Evidence'),data['evidence'],('Eigener Prüfvermerk' if de else 'Own review note'),data['review_note'],result['filing_notice'],('Quellenstand ' if de else 'Sources checked ')+display_date(result['source_checked_on'],de)])
    parts.extend(source['label']+' · '+source['url'] for source in result['sources'])
    parts.append(result['court_directory'])
    return '\n\n'.join(parts)


def migrate(connection):
    connection.executescript('''CREATE TABLE IF NOT EXISTS route_plans(case_id TEXT PRIMARY KEY REFERENCES cases(id),user_id TEXT NOT NULL REFERENCES users(id),version INTEGER NOT NULL,input TEXT NOT NULL,result TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS route_plan_versions(case_id TEXT NOT NULL REFERENCES cases(id),version INTEGER NOT NULL,input TEXT NOT NULL,result TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(case_id,version));''')


def router(db,require_user,now,record_activity):
    routes=APIRouter()
    def owned(connection,case_id,user_id):
        row=connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?',(case_id,user_id)).fetchone()
        if not row:raise HTTPException(404,'Case not found')
        return row
    def public(row):
        if not row:return None
        return {'case_id':row['case_id'],'version':row['version'],'input':json.loads(row['input']),'result':json.loads(row['result']),'updated_at':row['updated_at']}
    @routes.get('/api/cases/{case_id}/route-plan')
    def read(case_id:str,user:dict=Depends(require_user)):
        with db() as connection:
            owned(connection,case_id,user['id']);return public(connection.execute('SELECT * FROM route_plans WHERE case_id=?',(case_id,)).fetchone())
    @routes.post('/api/cases/{case_id}/route-plan/preview')
    def preview(case_id:str,payload:PlanInput,user:dict=Depends(require_user)):
        with db() as connection:case=owned(connection,case_id,user['id'])
        return prepare(payload,json.loads(case['details']).get('jurisdiction','DE'))
    @routes.put('/api/cases/{case_id}/route-plan')
    def save(case_id:str,payload:PlanInput,user:dict=Depends(require_user)):
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE');case=owned(connection,case_id,user['id'])
            previous=connection.execute('SELECT * FROM route_plans WHERE case_id=?',(case_id,)).fetchone()
            if payload.expected_version!=(previous['version'] if previous else 0):raise HTTPException(409,'Route plan changed')
            version=(previous['version'] if previous else 0)+1;timestamp=now()
            inputs=payload.model_dump_json(exclude={'expected_version'});result=json.dumps(prepare(payload,json.loads(case['details']).get('jurisdiction','DE')),ensure_ascii=False)
            connection.execute('INSERT INTO route_plans VALUES(?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET version=excluded.version,input=excluded.input,result=excluded.result,updated_at=excluded.updated_at',(case_id,user['id'],version,inputs,result,timestamp))
            connection.execute('INSERT INTO route_plan_versions VALUES(?,?,?,?,?)',(case_id,version,inputs,result,timestamp));record_activity(connection,case_id,'route_plan_saved')
            return public(connection.execute('SELECT * FROM route_plans WHERE case_id=?',(case_id,)).fetchone())
    @routes.get('/api/cases/{case_id}/route-plan/versions')
    def versions(case_id:str,user:dict=Depends(require_user)):
        with db() as connection:
            owned(connection,case_id,user['id']);return [public(row) for row in connection.execute('SELECT * FROM route_plan_versions WHERE case_id=? ORDER BY version DESC',(case_id,))]
    @routes.get('/api/cases/{case_id}/route-plan/report.{fmt}')
    def report(case_id:str,fmt:Literal['pdf','docx'],version:int|None=None,user:dict=Depends(require_user)):
        with db() as connection:
            case=owned(connection,case_id,user['id'])
            row=connection.execute('SELECT * FROM route_plan_versions WHERE case_id=? AND version=?',(case_id,version)).fetchone() if version is not None else connection.execute('SELECT * FROM route_plans WHERE case_id=?',(case_id,)).fetchone()
            if not row:raise HTTPException(404,'Plan not found')
        layout={'left_mm':25,'right_mm':25,'top_mm':25,'bottom_mm':25,'font_size':11};text=body(public(row),case['reference'])
        if fmt=='pdf':return Response(compose_pdf(text,None,layout),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="Schimmelpilz-Verfahrensplan-v{row["version"]}.pdf"'})
        return Response(compose_docx(text,None,layout,case['reference'],row['version']),media_type=DOCX,headers={'Content-Disposition':f'attachment; filename="Schimmelpilz-Verfahrensplan-v{row["version"]}.docx"'})
    return routes
