"""Build the data of the public demo (schimmelpilz.online/app/): a synthetic law firm with invented cases.

Runs the real API against a throw-away data folder, fills it through the normal endpoints and records every response
the interface reads into landing/src/demo/fixtures.json. No real client data is involved; all names are invented.

    .venv/Scripts/python.exe demo/build_demo.py
"""
import base64
import io
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(tempfile.mkdtemp(prefix='schimmelpilz-demo-'))
os.environ.update({'DATA_DIR': str(DATA), 'REMINDERS': 'off', 'AI_PROVIDER': 'none', 'GEMINI_API_KEY': '', 'GROQ_API_KEY': ''})
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from server import app as api, pdf_fonts  # noqa: E402

TODAY = date.today()
day = lambda offset: (TODAY + timedelta(days=offset)).isoformat()
OUT = ROOT / 'landing' / 'src' / 'demo' / 'fixtures.json'


def letter_pdf(lines):
    """A simple one-page letter with an embedded font, so the document viewer and full-text search have real text."""
    pdf_fonts.register()
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=A4)
    page.setFont(pdf_fonts.BODY, 10.5)
    y = 800
    for line in lines:
        page.drawString(70, y, line)
        y -= 16
    page.save()
    return output.getvalue()


def main():
    client = TestClient(api.app)
    client.headers.update({'X-Schimmelpilz-Request': '1'})
    account = {'email': 'demo@schimmelpilz.online', 'password': 'Demo-Kanzlei-nur-Beispieldaten-2026!', 'audience': 'law_firm', 'full_name': 'Erika Muster',
               'organisation': 'Kanzlei Muster (Demo)', 'street': 'Beispielstraße 1', 'postal_code': '50667', 'city': 'Köln', 'country': 'Deutschland'}
    client.__enter__()
    assert client.post('/api/auth/register', json=account).status_code in (200, 201)

    def post(path, payload, status=(200, 201)):
        response = client.post(path, json=payload)
        assert response.status_code in status, (path, response.status_code, response.text[:300])
        return response.json() if response.content else None

    def case(title, description, **details):
        return post('/api/cases', {'title': title, 'description': description, 'details': {'audience': 'law_firm', **details}})

    def task(case_id, title, offset, kind='task', time=None, note=''):
        post(f'/api/cases/{case_id}/tasks', {'title': title, 'note': note, 'due_on': day(offset), 'priority': 'high' if kind in ('deadline', 'notfrist') else 'normal', 'kind': kind, 'due_time': time})

    def document(case_id, name, lines):
        response = client.post(f'/api/cases/{case_id}/documents', files={'file': (name, letter_pdf(lines), 'application/pdf')})
        assert response.status_code == 201, response.text

    def draft(case_id, kind, body, recipient=''):
        return post(f'/api/cases/{case_id}/drafts', {'kind': kind, 'body': body, 'recipient': recipient, 'language': 'de'})

    def note(case_id, kind, person, offset_days, minutes, text):
        post(f'/api/cases/{case_id}/notes', {'kind': kind, 'person': person, 'happened_at': f'{day(offset_days)}T10:15', 'minutes': minutes, 'note': text})

    # ---------- 1 Kündigungsschutz ----------
    weber = case('Kündigungsschutz Weber', 'Ordentliche Kündigung nach 6 Jahren Betriebszugehörigkeit, Betriebsrat angehört. Mandantin bestreitet die Sozialauswahl.',
                 legal_area='employment', client_name='Anna Weber', client_role='claimant', client_address='Lindenallee 12, 50968 Köln', client_email='anna.weber@example.invalid',
                 opponent_name='Rheinland Logistik GmbH', opponent_address='Hafenstraße 10, 50735 Köln', court='Arbeitsgericht Köln, Pohligstraße 9, 50969 Köln',
                 court_reference='3 Ca 4711/26', dispute_value=9000, objective='Feststellung, dass das Arbeitsverhältnis fortbesteht; hilfsweise Abfindung.')
    document(weber['id'], 'Kuendigung_Rheinland_Logistik.pdf', ['Rheinland Logistik GmbH · Hafenstraße 10 · 50735 Köln', '', 'Frau Anna Weber', 'Lindenallee 12', '50968 Köln', '',
             f'Köln, {date.fromisoformat(day(-12)).strftime("%d.%m.%Y")}', '', 'Kündigung Ihres Arbeitsverhältnisses', '',
             'Sehr geehrte Frau Weber,', 'hiermit kündigen wir das mit Ihnen bestehende Arbeitsverhältnis ordentlich', 'und fristgerecht zum nächstmöglichen Zeitpunkt.',
             'Der Betriebsrat wurde angehört.', '', 'Mit freundlichen Grüßen', 'Geschäftsführung'])
    document(weber['id'], 'Arbeitsvertrag_2020.pdf', ['Arbeitsvertrag', '', 'zwischen Rheinland Logistik GmbH und Anna Weber', '§ 1 Beginn: 01.03.2020', '§ 2 Tätigkeit: Disponentin',
             '§ 3 Vergütung: 3.000,00 EUR brutto monatlich', '§ 9 Kündigungsfristen: gesetzlich'])
    task(weber['id'], 'Klagefrist § 4 KSchG', 9, 'notfrist')
    task(weber['id'], 'Gütetermin Arbeitsgericht Köln, Saal 112', 23, 'appointment', '10:30')
    task(weber['id'], 'Sozialdaten der Vergleichsgruppe anfordern', 3)
    note(weber['id'], 'call_in', 'Anna Weber', -2, 15, 'Mandantin schildert: drei jüngere Kollegen ohne Unterhaltspflichten wurden nicht gekündigt. Sie schickt Gehaltsabrechnungen und Kündigungsschreiben.')
    note(weber['id'], 'meeting', 'Anna Weber', -1, 45, 'Erstgespräch: Vollmacht unterschrieben, Kostenrisiko erläutert (§ 12a ArbGG), Rechtsschutz liegt vor.')
    draft(weber['id'], 'claim', f'''Arbeitsgericht Köln
Pohligstraße 9
50969 Köln

KLAGE

der Frau Anna Weber, Lindenallee 12, 50968 Köln
– Klägerin –

gegen

die Rheinland Logistik GmbH, vertreten durch die Geschäftsführung, Hafenstraße 10, 50735 Köln
– Beklagte –

wegen Kündigungsschutz

Namens und in Vollmacht der Klägerin erhebe ich Klage und beantrage:

1. Es wird festgestellt, dass das Arbeitsverhältnis der Parteien durch die Kündigung der Beklagten vom {date.fromisoformat(day(-12)).strftime("%d.%m.%Y")} nicht aufgelöst worden ist.

2. Die Beklagte wird verurteilt, die Klägerin bis zum rechtskräftigen Abschluss des Verfahrens als Disponentin weiterzubeschäftigen.

Begründung:

I. Sachverhalt
Die Klägerin ist seit dem 01.03.2020 bei der Beklagten als Disponentin beschäftigt (Anlage K 1). Mit Schreiben vom {date.fromisoformat(day(-12)).strftime("%d.%m.%Y")} kündigte die Beklagte ordentlich (Anlage K 2).

II. Rechtliche Würdigung
Die Kündigung ist sozial ungerechtfertigt (§ 1 Abs. 3 KSchG). Die Sozialauswahl ist fehlerhaft; vergleichbare Arbeitnehmer mit geringerer Schutzbedürftigkeit wurden nicht gekündigt.

Die Klagefrist des § 4 Satz 1 KSchG ist gewahrt.

Anlagen:
K 1 Arbeitsvertrag
K 2 Kündigungsschreiben

Erika Muster
Rechtsanwältin''', 'Arbeitsgericht Köln')

    # ---------- 2 Werklohn ----------
    schulz = case('Werklohn Schulz ./. Müller Bau', 'Mandant hat Fliesenarbeiten ausgeführt; Auftraggeber zahlt die Schlussrechnung nicht und rügt angebliche Mängel.',
                  legal_area='contract', client_name='Bernd Schulz Fliesen e. K.', client_role='claimant', client_address='Gartenweg 3, 51063 Köln',
                  opponent_name='Müller Bau GmbH', opponent_address='Industriestraße 5, 50735 Köln', court='Landgericht Köln, Luxemburger Straße 101, 50939 Köln',
                  dispute_value=12500, objective='Zahlung der Schlussrechnung über 12.500,00 EUR nebst Zinsen.')
    mail = EmailMessage()
    mail['From'] = 'Müller Bau GmbH <info@mueller-bau.example>'; mail['To'] = 'kanzlei@example.invalid'
    mail['Subject'] = 'Ihr Schreiben vom ' + date.fromisoformat(day(-20)).strftime('%d.%m.%Y'); mail['Date'] = 'Mon, 9 Nov 2026 09:15:00 +0100'
    mail.set_content('Sehr geehrte Frau Muster,\n\nwir weisen die Forderung zurück. Die Fliesen im Obergeschoss sind uneben verlegt.\nWir behalten 4.000,00 EUR ein, bis die Mängel beseitigt sind.\n\nMit freundlichen Grüßen\nMüller Bau GmbH')
    mail.add_attachment(letter_pdf(['Mängelliste', '', '1. Fliesen OG Bad: Höhenversatz bis 3 mm', '2. Fugenbild Flur ungleichmäßig']), maintype='application', subtype='pdf', filename='Maengelliste.pdf')
    assert client.post(f"/api/cases/{schulz['id']}/documents", files={'file': ('Antwort_Mueller_Bau.eml', mail.as_bytes(), 'message/rfc822')}).status_code == 201
    document(schulz['id'], 'Schlussrechnung_4471.pdf', ['Bernd Schulz Fliesen e. K.', '', 'Schlussrechnung Nr. 4471', 'Bauvorhaben Mehrfamilienhaus Am Rhein 7',
             'Fliesenarbeiten gemäß Auftrag', 'Gesamtbetrag: 12.500,00 EUR', 'Zahlbar innerhalb von 14 Tagen.'])
    task(schulz['id'], 'Stellungnahme zu den Mängelrügen', 4, 'deadline')
    task(schulz['id'], 'Wiedervorlage: Zahlungseingang Müller Bau', 12, 'resubmission')
    note(schulz['id'], 'call_out', 'Bernd Schulz', -3, 10, 'Mandant bestätigt: Abnahme erfolgte am Bauende ohne Vorbehalt, Fotos vorhanden. Mängelrüge kam erst nach Rechnung.')
    for item in ({'kind': 'principal', 'description': 'Schlussrechnung Nr. 4471', 'amount': '12500.00', 'booked_on': day(-60), 'interest_mode': 'business', 'interest_from': day(-30)},
                 {'kind': 'cost', 'description': 'Vorgerichtliche Mahnkosten', 'amount': '40.00', 'booked_on': day(-25)}):
        post(f"/api/cases/{schulz['id']}/claim/items", item)
    post(f"/api/cases/{schulz['id']}/claim/payments", {'paid_on': day(-10), 'amount': '2000.00', 'note': 'Teilzahlung Müller Bau'})

    # ---------- 3 Mietminderung ----------
    becker = case('Mietminderung Becker', 'Schimmel im Schlafzimmer seit Januar; Vermieterin reagiert nicht. Mandant mindert die Miete um 15 %.',
                  legal_area='tenancy', client_name='Jonas Becker', client_role='respondent', client_address='Domstraße 3, 50668 Köln',
                  opponent_name='Hausverwaltung Domblick GmbH', court='Amtsgericht Köln, Luxemburger Straße 101, 50939 Köln', dispute_value=2400)
    document(becker['id'], 'Maengelanzeige_Schimmel.pdf', ['Jonas Becker · Domstraße 3 · 50668 Köln', '', 'Hausverwaltung Domblick GmbH', '', 'Mängelanzeige',
             'Im Schlafzimmer hat sich an der Außenwand großflächig Schimmel gebildet.', 'Ich bitte um Beseitigung bis zum Monatsende.'])
    task(becker['id'], 'Ortstermin mit Sachverständigem', 6, 'appointment', '14:00')
    note(becker['id'], 'call_in', 'Jonas Becker', -4, 8, 'Mandant sendet Fotos über den Upload-Link. Feuchtigkeitsmessung durch Sachverständigen gewünscht.')
    post(f"/api/cases/{becker['id']}/upload-links", {'days': 14, 'max_files': 20, 'message': 'Bitte Fotos vom Schimmel, Mietvertrag und Ihre Mängelanzeige hochladen.'})

    # ---------- 4 Schwerbehinderung ----------
    yilmaz = case('GdB-Widerspruch Yilmaz', 'Versorgungsamt hat GdB 40 festgestellt; Mandant begehrt GdB 50 wegen Wirbelsäulen- und Herzleiden.',
                  legal_area='social', client_name='Mehmet Yilmaz', client_role='applicant', opponent_name='Kreis Köln – Versorgungsamt', opponent_reference='12-345/26',
                  court='Sozialgericht Köln, An den Dominikanern 2, 50668 Köln', objective='Feststellung eines GdB von 50.')
    task(yilmaz['id'], 'Widerspruchsfrist § 84 SGG', 15, 'notfrist')
    task(yilmaz['id'], 'Befundberichte der Ärzte anfordern', 5)
    draft(yilmaz['id'], 'objection', '''Kreis Köln – Versorgungsamt
Az. 12-345/26

WIDERSPRUCH

gegen den Bescheid vom [Datum]

Namens und in Vollmacht des Herrn Mehmet Yilmaz lege ich gegen den Bescheid Widerspruch ein und beantrage, einen Grad der Behinderung von 50 festzustellen.

Begründung folgt nach Akteneinsicht. Ich beantrage Akteneinsicht und bitte um Übersendung der Verwaltungsakte (§ 25 SGB X).

Erika Muster
Rechtsanwältin''', 'Kreis Köln – Versorgungsamt')

    # ---------- 5 Altakte (archived, retention) ----------
    old = case('Nachbarstreit Hoffmann (Altakte)', 'Abgeschlossenes Mandat aus 2018: Überhang von Ästen, Vergleich geschlossen.', legal_area='general', client_name='Gerda Hoffmann')
    client.put(f"/api/cases/{old['id']}/archive", json={'archived': True, 'expected_version': 0})
    client.put(f"/api/retention/{old['id']}", json={'ended_on': '2018-09-30'})

    # ---------- contacts, invoices, time ----------
    for contact in ({'name': 'Anna Weber', 'kind': 'client', 'address': 'Lindenallee 12, 50968 Köln', 'case_links': [{'case_id': weber['id'], 'role': 'client'}]},
                    {'name': 'Rheinland Logistik GmbH', 'kind': 'opponent', 'address': 'Hafenstraße 10, 50735 Köln', 'case_links': [{'case_id': weber['id'], 'role': 'opponent'}]},
                    {'name': 'Arbeitsgericht Köln', 'kind': 'court', 'address': 'Pohligstraße 9, 50969 Köln', 'case_links': [{'case_id': weber['id'], 'role': 'court'}]},
                    {'name': 'Müller Bau GmbH', 'kind': 'opponent', 'address': 'Industriestraße 5, 50735 Köln', 'case_links': [{'case_id': schulz['id'], 'role': 'opponent'}]}):
        post('/api/contacts', contact)
    recipient = 'Bernd Schulz Fliesen e. K.\nGartenweg 3\n51063 Köln'
    overdue = post('/api/invoices', {'case_id': schulz['id'], 'recipient': recipient, 'issued_on': day(-45), 'value': '12500', 'fees': [{'code': '2300', 'rate': '1.3'}]})
    post(f"/api/invoices/{overdue['id']}/reminders", {'pay_within_days': 14, 'bank': 'Demo-Bank, IBAN DE00 0000 0000 0000 0000 00'})
    paid = post('/api/invoices', {'case_id': weber['id'], 'recipient': 'Anna Weber\nLindenallee 12\n50968 Köln', 'issued_on': day(-20), 'kind': 'advance', 'advance_net': '500'})
    post(f"/api/invoices/{paid['id']}/payments", {'paid_on': day(-8), 'amount': '595.00'})
    for offset, minutes, activity in ((-5, 45, 'Erstgespräch Mandantin'), (-3, 30, 'Durchsicht Arbeitsvertrag und Kündigung'), (-1, 90, 'Entwurf Kündigungsschutzklage')):
        post(f"/api/cases/{weber['id']}/time-entries", {'day': day(offset), 'minutes': minutes, 'activity': activity, 'hourly_rate': '250.00'})

    # ---------- record everything the interface reads ----------
    fixtures = {}

    def record(path, binary=False):
        response = client.get(path)
        if response.status_code >= 400:
            fixtures['GET ' + path] = {'status': response.status_code, 'json': safe_json(response)}
            return None
        kind = response.headers.get('content-type', '').split(';')[0]
        if binary or not kind.endswith('json'):
            fixtures['GET ' + path] = {'status': response.status_code, 'type': kind, 'b64': base64.b64encode(response.content).decode(),
                                       'disposition': response.headers.get('content-disposition', '')}
            return None
        data = response.json()
        fixtures['GET ' + path] = {'status': response.status_code, 'json': data}
        return data

    def safe_json(response):
        try:
            return response.json()
        except ValueError:
            return None

    for path in ('/api/auth/me', '/api/public/operator', '/api/public/pricing', '/api/research/status', '/api/legal/status', '/api/team', '/api/billing',
                 '/api/reminders/settings', '/api/snippets', '/api/contacts', '/api/inbox', '/api/inbox/mailbox', '/api/invoices/catalogue', '/api/ledger',
                 '/api/ledger/datev-settings', f'/api/ledger/statistics?year={TODAY.year}', '/api/retention', '/api/forms', '/api/dictations?status=all',
                 '/api/dictations?status=open', '/api/dictations?status=active', '/api/auth/capabilities', '/api/cost-reviews', '/api/letter-assistant/kinds', '/api/auth/letterheads', '/api/invoices',
                 '/api/retention/protocol.pdf'):
        record(path)
    for status in ('open', 'all', 'paid', 'cancelled', 'dunning'):
        record(f'/api/invoices?status={status}')
    cases = record('/api/cases')
    cases = cases.get('items', cases) if isinstance(cases, dict) else cases
    for item in cases:
        cid = item['id']
        full = record(f'/api/cases/{cid}')
        for suffix in ('notes', 'upload-links', 'time-entries', 'legal-sources', 'court-suggestion', 'research', 'route-plan', 'route-plan/versions', f'claim?as_of={TODAY.isoformat()}'):
            record(f'/api/cases/{cid}/{suffix}')
        record(f'/api/cost-reviews?case_id={cid}')
        record(f'/api/invoices?case_id={cid}')
        for doc in full.get('documents', []):
            record(f"/api/cases/{cid}/documents/{doc['id']}/download", binary=True)
            record(f"/api/cases/{cid}/documents/{doc['id']}/text")
        for entry in full.get('drafts', []):
            record(f"/api/cases/{cid}/drafts/{entry['id']}/review")
            record(f"/api/cases/{cid}/drafts/{entry['id']}/pdf", binary=True)
            record(f"/api/cases/{cid}/drafts/{entry['id']}/bea.pdf", binary=True)
        if not item.get('archived_at'):
            for kind in ('vollmacht', 'mandatsbestaetigung', 'kostenhinweis', 'datenschutz', 'schweigepflicht'):
                record(f'/api/cases/{cid}/forms/{kind}.pdf', binary=True)
    for entry in record('/api/invoices?status=all')['invoices']:
        record(f"/api/invoices/{entry['id']}/pdf", binary=True)
        for reminder in entry.get('reminders', []):
            record(f"/api/invoices/{entry['id']}/reminders/{reminder['level']}/pdf", binary=True)
    record(f'/api/tasks/deadline-book.pdf?start={TODAY.replace(day=1).isoformat()}&end={(TODAY.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)}', binary=True)
    record('/api/tasks/calendar.ics?lang=de&alarm_days=1', binary=True)

    from server.fee_tables import COURT, RVG, VALUES
    payload = {'recorded_on': TODAY.isoformat(), 'tables': {'values': VALUES, 'rvg': RVG, 'court': COURT}, 'fixtures': fixtures}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(fixtures)} Antworten aufgezeichnet, {OUT.stat().st_size / 1e6:.1f} MB -> {OUT.relative_to(ROOT)}')
    client.__exit__(None, None, None)


if __name__ == '__main__':
    main()
