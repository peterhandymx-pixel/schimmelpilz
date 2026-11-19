"""Standard client forms filled from the case and the firm profile: power of attorney, privacy notice, fee notice,
engagement confirmation, release from confidentiality. Fixed wording, no AI. Missing data stays as [placeholder].
The PDF is placed on the firm's active letterhead when one is set up.
"""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .dates import display_date

FORMS = {
    'vollmacht': 'Vollmacht',
    'mandatsbestaetigung': 'Mandatsbestätigung',
    'kostenhinweis': 'Hinweis zur Vergütung (§ 49b Abs. 5 BRAO)',
    'datenschutz': 'Datenschutzhinweise für Mandanten (Art. 13 DSGVO)',
    'schweigepflicht': 'Entbindung von der Schweigepflicht',
}
NBSP = '\u00a0'
# Non-breaking spaces keep the two signature fields apart; ordinary spaces collapse in the PDF.
SIGN = '\n\n\n' + '_' * 30 + NBSP * 6 + '_' * 30 + '\nOrt, Datum' + NBSP * 35 + 'Unterschrift'


def value(text, placeholder):
    text = (text or '').strip()
    return text if text else f'[{placeholder}]'


def firm(user):
    lines = [user.get('organisation') or user.get('full_name'), user.get('street'), ' '.join(filter(None, [user.get('postal_code'), user.get('city')]))]
    return '\n'.join(line for line in lines if line) or '[Kanzlei, Anschrift]'


def firm_one_line(user):
    return firm(user).replace('\n', ', ')


def body(kind, case, user, today=None):
    details = case.get('details') or {}
    today = today or date.today()
    client = value(details.get('client_name'), 'Name des Mandanten')
    client_address = value(details.get('client_address'), 'Anschrift des Mandanten')
    opponent = value(details.get('opponent_name'), 'Gegner')
    matter = f'{client} ./. {opponent}' if details.get('opponent_name') else value(case.get('title'), 'Angelegenheit')
    lawyer = value(user.get('full_name'), 'Rechtsanwalt/Rechtsanwältin')
    office = firm_one_line(user)
    reference = case.get('reference') or '[Aktenzeichen]'
    header = f'Unser Zeichen: {reference}\n{display_date(today.isoformat())}\n\n'

    if kind == 'vollmacht':
        return ('VOLLMACHT\n\n'
                f'Hiermit wird {lawyer}, {office},\n\n'
                f'in Sachen {matter}\nwegen {value(case.get("title"), "Gegenstand")}\n\n'
                'Vollmacht erteilt\n\n'
                '1. zur Prozessführung (u. a. nach §§ 81 ff. ZPO) einschließlich der Befugnis zur Erhebung und Zurücknahme von Widerklagen;\n'
                '2. zur Antragstellung in Scheidungs- und Scheidungsfolgesachen, zum Abschluss von Vereinbarungen über Scheidungsfolgen sowie zur Stellung von Anträgen auf Erteilung von Renten- und sonstigen Versorgungsauskünften;\n'
                '3. zur Vertretung und Verteidigung in Strafsachen und Bußgeldsachen (§§ 302, 374 StPO) einschließlich der Vorverfahren sowie (für den Fall der Abwesenheit) zur Vertretung nach § 411 Abs. 2 StPO, mit ausdrücklicher Ermächtigung auch nach §§ 233 Abs. 1, 234 StPO, zur Stellung von Straf- und anderen nach der StPO zulässigen Anträgen;\n'
                '4. zur Vertretung in sonstigen Verfahren und bei außergerichtlichen Verhandlungen aller Art, insbesondere vor Behörden, Sozialleistungsträgern und Versicherungen;\n'
                '5. zur Begründung und Aufhebung von Vertragsverhältnissen und zur Abgabe und Entgegennahme von einseitigen Willenserklärungen (z. B. Kündigungen) im Zusammenhang mit der oben genannten Angelegenheit.\n\n'
                'Die Vollmacht gilt für alle Instanzen und erstreckt sich auch auf Neben- und Folgeverfahren aller Art (z. B. Arrest und einstweilige Verfügung, Kostenfestsetzungs-, Zwangsvollstreckungs-, Interventions-, Zwangsversteigerungs-, Zwangsverwaltungs- und Hinterlegungsverfahren sowie Insolvenzverfahren). '
                'Sie umfasst insbesondere die Befugnis, Zustellungen zu bewirken und entgegenzunehmen, die Vollmacht ganz oder teilweise auf andere zu übertragen (Untervollmacht), Rechtsmittel einzulegen, zurückzunehmen oder auf sie zu verzichten, den Rechtsstreit oder außergerichtliche Verhandlungen durch Vergleich, Verzicht oder Anerkenntnis zu erledigen, '
                'Geld, Wertsachen und Urkunden, insbesondere auch den Streitgegenstand und die von dem Gegner, von der Justizkasse oder von sonstigen Stellen zu erstattenden Beträge entgegenzunehmen sowie Akteneinsicht zu nehmen.\n\n'
                f'Vollmachtgeber/in:\n{client}\n{client_address}' + SIGN)

    if kind == 'mandatsbestaetigung':
        return (f'{client}\n{client_address}\n\n' + header +
                f'Mandatsbestätigung – {matter}\n\n'
                f'Sehr geehrte Damen und Herren,\n\n'
                f'vielen Dank für Ihr Vertrauen. Hiermit bestätigen wir die Übernahme des Mandats in der Angelegenheit „{value(case.get("title"), "Angelegenheit")}“ unter unserem Zeichen {reference}.\n\n'
                f'Auftrag: {value(details.get("objective"), "Umfang des Auftrags")}\n\n'
                'Bitte senden Sie uns die beigefügte Vollmacht unterschrieben zurück und reichen Sie uns alle Unterlagen ein, die mit der Angelegenheit zusammenhängen (Schreiben, Verträge, Bescheide, Rechnungen, Fotos). '
                'Fristgebundene Schreiben leiten Sie uns bitte sofort nach Erhalt weiter und notieren Sie das Eingangsdatum.\n\n'
                + (f'Ihre Rechtsschutzversicherung ({details.get("insurer_name")}) werden wir um Deckungszusage bitten. Selbstbeteiligung und nicht gedeckte Kosten tragen Sie selbst.\n\n' if details.get('insurer_name') else '')
                + 'Unsere Vergütung richtet sich nach dem Rechtsanwaltsvergütungsgesetz (RVG), soweit nichts anderes vereinbart ist. Hinweise zur Vergütung und zum Datenschutz erhalten Sie gesondert.\n\n'
                f'Mit freundlichen Grüßen\n\n{lawyer}')

    if kind == 'kostenhinweis':
        employment = details.get('legal_area') == 'employment'
        return ('HINWEIS ZUR VERGÜTUNG\n\n'
                f'Mandant/in: {client}\nAngelegenheit: {matter}\nUnser Zeichen: {reference}\n\n'
                'Ich wurde vor Übernahme des Auftrags darauf hingewiesen, dass sich die zu erhebenden Gebühren nach dem Gegenstandswert richten (§ 49b Abs. 5 BRAO). '
                'Die Höhe der Gebühren ergibt sich aus dem Rechtsanwaltsvergütungsgesetz (RVG) und dessen Gebührentabelle; mit steigendem Gegenstandswert steigen die Gebühren.\n\n'
                + ('Mir ist außerdem bekannt, dass im Urteilsverfahren des ersten Rechtszugs vor dem Arbeitsgericht kein Anspruch der obsiegenden Partei auf Erstattung der Kosten für die Hinzuziehung eines Prozessbevollmächtigten besteht (§ 12a Abs. 1 Satz 1 ArbGG). '
                   'Ich trage die Kosten meiner Anwältin / meines Anwalts in dieser Instanz daher auch dann selbst, wenn ich den Prozess gewinne.\n\n' if employment else '')
                + 'Soweit eine Rechtsschutzversicherung besteht, berührt dies meine Zahlungspflicht gegenüber der Kanzlei nicht; nicht gedeckte Beträge und eine Selbstbeteiligung trage ich selbst.\n\n'
                f'Vorläufiger Gegenstandswert: {format_value(details.get("dispute_value"))}' + SIGN)

    if kind == 'datenschutz':
        return ('DATENSCHUTZHINWEISE FÜR MANDANTEN\nInformationen nach Art. 13 DSGVO\n\n'
                f'1. Verantwortlicher\n{office}' + (f', Telefon {user.get("phone")}' if user.get('phone') else '') + (f', E-Mail {user.get("email")}' if user.get('email') else '') + '\n\n'
                '2. Zwecke und Rechtsgrundlagen\nWir verarbeiten Ihre personenbezogenen Daten, um Sie rechtlich zu beraten und zu vertreten, mit Ihnen zu korrespondieren, Fristen zu überwachen und unsere Tätigkeit abzurechnen. '
                'Rechtsgrundlagen sind Art. 6 Abs. 1 lit. b DSGVO (Mandatsvertrag), Art. 6 Abs. 1 lit. c DSGVO (gesetzliche Pflichten, z. B. Aufbewahrung, Geldwäschegesetz) und Art. 6 Abs. 1 lit. f DSGVO (Geltendmachung von Ansprüchen). '
                'Gesundheitsdaten und andere besondere Kategorien verarbeiten wir nur, soweit dies zur Geltendmachung, Ausübung oder Verteidigung von Rechtsansprüchen erforderlich ist (Art. 9 Abs. 2 lit. f DSGVO).\n\n'
                '3. Empfänger\nIhre Daten erhalten nur Stellen, an die sie zur Bearbeitung des Mandats übermittelt werden müssen: Gerichte, Behörden, Gegner und deren Bevollmächtigte, Rechtsschutzversicherungen sowie unsere Dienstleister (z. B. IT, Abrechnung), die zur Verschwiegenheit verpflichtet sind (§ 43e BRAO).\n\n'
                '4. Speicherdauer\nHandakten bewahren wir sechs Jahre nach Ablauf des Kalenderjahres auf, in dem der Auftrag beendet wurde (§ 50 Abs. 1 BRAO). Buchungsbelege und Rechnungen bewahren wir nach den steuer- und handelsrechtlichen Vorschriften bis zu zehn Jahre auf (§ 147 AO, § 257 HGB).\n\n'
                '5. Ihre Rechte\nSie haben das Recht auf Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung der Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) und Widerspruch (Art. 21 DSGVO). '
                'Die anwaltliche Verschwiegenheitspflicht kann Auskunfts- und Löschungsrechten Dritter entgegenstehen. Sie können sich bei einer Datenschutz-Aufsichtsbehörde beschweren (Art. 77 DSGVO).\n\n'
                '6. Pflicht zur Bereitstellung\nOhne die für die Mandatsbearbeitung erforderlichen Daten können wir das Mandat nicht übernehmen. Eine automatisierte Entscheidungsfindung findet nicht statt.\n\n'
                f'Kenntnis genommen:\n{client}' + SIGN)

    if kind == 'schweigepflicht':
        return ('ENTBINDUNG VON DER SCHWEIGEPFLICHT\n\n'
                f'Ich, {client}, {client_address},\n\n'
                'entbinde hiermit\n\n[Name und Anschrift der Ärztin / des Arztes, der Klinik, der Behörde oder Versicherung]\n\n'
                f'gegenüber {lawyer}, {office},\n\n'
                f'von der Schweigepflicht in der Angelegenheit {matter} (Zeichen {reference}). '
                'Die Entbindung umfasst die Erteilung von Auskünften sowie die Übersendung von Befunden, Berichten, Gutachten und Behandlungsunterlagen in Kopie, soweit diese für die Bearbeitung der Angelegenheit erforderlich sind.\n\n'
                'Zeitraum der Unterlagen: [von … bis …]\n\n'
                'Die Erklärung kann ich jederzeit mit Wirkung für die Zukunft widerrufen.' + SIGN)
    raise KeyError(kind)


def format_value(raw):
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return '[wird nach Prüfung mitgeteilt]'
    return f'{number:,.2f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def router(db, require_user, get_case, letterhead_pdf):
    routes = APIRouter()

    @routes.get('/api/forms')
    def list_forms(user: dict = Depends(require_user)):
        return [{'id': key, 'title': title} for key, title in FORMS.items()]

    @routes.get('/api/cases/{case_id}/forms/{kind}.pdf')
    def form_pdf(case_id: str, kind: str, user: dict = Depends(require_user)):
        if kind not in FORMS:
            raise HTTPException(404, 'Unknown form')
        case = get_case(case_id, user['id'])
        text = body(kind, case, user)
        letterhead_id, layout = None, {'top_mm': 20, 'bottom_mm': 20, 'left_mm': 25, 'right_mm': 20, 'font_size': 10.5}
        with db() as connection:
            row = connection.execute('SELECT letterhead_id FROM users WHERE id=?', (user['id'],)).fetchone()
            if row and row['letterhead_id']:
                letterhead = connection.execute('SELECT layout FROM letterheads WHERE id=? AND user_id=?', (row['letterhead_id'], user['id'])).fetchone()
                if letterhead:
                    letterhead_id, layout = row['letterhead_id'], {**json.loads(letterhead['layout'] or '{}')}
                    layout.setdefault('font_size', 10.5)
        if not letterhead_id and kind != 'mandatsbestaetigung':
            text = firm(user) + '\n\n' + text
        elif not letterhead_id:
            text = firm_one_line(user) + '\n\n' + text
        response = letterhead_pdf(text, letterhead_id, layout, user['id'])
        filename = f'{FORMS[kind].split(" (")[0]} {case["reference"]}'.replace('/', '-')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename.encode("ascii", "replace").decode()}.pdf"; filename*=UTF-8\'\'{quote(filename)}.pdf'
        return response

    return routes


def quote(text):
    from urllib.parse import quote as url_quote
    return url_quote(text)
