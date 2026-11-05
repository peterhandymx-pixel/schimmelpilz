"""Guided help for a received letter: read the key data, ask a few questions, give a dated next step.

Rule-based and deterministic on purpose: every result names the statute it rests on, and the person confirms the data
before anything is calculated. Deadlines use the calculation aid in deadlines.py (nationwide holidays only, so a regional
holiday can only make the real deadline later, never earlier). This is orientation, not legal advice.
"""
import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import deadlines

MONTHS = {'januar': 1, 'jan': 1, 'februar': 2, 'feb': 2, 'maerz': 3, 'mrz': 3, 'mar': 3, 'april': 4, 'apr': 4, 'mai': 5,
          'juni': 6, 'jun': 6, 'juli': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
          'oktober': 10, 'okt': 10, 'november': 11, 'nov': 11, 'dezember': 12, 'dez': 12}
NUMBERS = {'einer': 1, 'einem': 1, 'eines': 1, 'ein': 1, 'zwei': 2, 'drei': 3, 'vier': 4, 'fuenf': 5, 'sechs': 6, 'sieben': 7, 'acht': 8,
           'zehn': 10, 'vierzehn': 14, 'einundzwanzig': 21, 'dreissig': 30}
SENDER_HINTS = r'(gmbh|mbh|\bag\b|\bkg\b|e\. ?v\.|amtsgericht|landgericht|arbeitsgericht|sozialgericht|verwaltungsgericht|finanzamt|jobcenter|' \
               r'agentur fuer arbeit|familienkasse|inkasso|stadt |landratsamt|rechtsanwa|kanzlei|versicherung|bank|hausverwaltung|' \
               r'staatsanwaltschaft|polizei|bussgeldstelle|zentrale bussgeldstelle|krankenkasse|rentenversicherung|\bbehoerde)'


def fold(text):
    """Lower case without umlauts, so OCR output and typed text match the same patterns."""
    text = (text or '').lower()
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(a, b)
    return text


def has(text, *patterns):
    return all(re.search(pattern, text) for pattern in patterns)


def any_of(text, *patterns):
    return any(re.search(pattern, text) for pattern in patterns)


# ---------------------------------------------------------------- reading the letter

def make_date(day, month, year):
    year = int(year)
    year += 2000 if year < 100 else 0
    try:
        return date(year, int(month), int(day))
    except ValueError:
        return None


DATE_NUMERIC = re.compile(r'(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4}|\d{2})(?!\d)')
DATE_WORDS = re.compile(r'(?<!\d)(\d{1,2})\.?\s+(' + '|'.join(sorted(MONTHS, key=len, reverse=True)) + r')\.?\s+(\d{4})')


def dates_in(folded):
    """[(position, date)] for every plausible date in the text."""
    found = []
    for match in DATE_NUMERIC.finditer(folded):
        value = make_date(*match.groups())
        if value:
            found.append((match.start(), match.end(), value))
    for match in DATE_WORDS.finditer(folded):
        value = make_date(match.group(1), MONTHS[match.group(2)], match.group(3))
        if value:
            found.append((match.start(), match.end(), value))
    return sorted(found, key=lambda item: item[0])


def parse_amount(raw):
    raw = raw.replace(' ', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    elif raw.count('.') == 1 and len(raw.split('.')[1]) == 2:
        pass
    else:
        raw = raw.replace('.', '')
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


AMOUNT = re.compile(r'(?:(?:eur|€)\s?(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?))|(?:(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)\s?(?:€|eur\b|euro\b))')
# Words that mark the sum actually demanded. Without them the largest amount wins, which is wrong for
# letters like "Miete 900 EUR, gezahlt 700 EUR, bitte überweisen Sie den Restbetrag von 200 EUR".
TOTAL_WORDS = (r'(gesamtbetrag|gesamtforderung|gesamtsumme|offener betrag|offenen betrag|offene forderung|noch offen|zu zahlen|zahlbetrag|nachzahlung|'
               r'restbetrag|restforderung|differenzbetrag|fehlbetrag|rueckstand|ueberweisen sie|begleichen sie|zahlen sie|summe|insgesamt|gesamt)')
REFERENCE = re.compile(r'(?:aktenzeichen|geschaeftszeichen|gesch\.?-?zeichen|unser zeichen|ihr zeichen|\baz\b\.?|kunden-?nummer|kunden-?nr\.?|'
                       r'rechnungs-?nummer|rechnungs-?nr\.?|vorgangs-?nummer|vorgangs-?nr\.?|vertrags-?nummer|vertrags-?nr\.?|steuernummer|'
                       r'bg-?nummer|versicherungs-?nummer|schaden-?nummer|forderungs-?nummer)\s*[:.]?\s*([a-z0-9][a-z0-9 /\-.]{2,40})')


def original_slice(text, folded, start, end):
    """Maps a span of the folded text back to the original spelling (folding only ever lengthens umlauts)."""
    # Rebuild an index from folded positions to original positions.
    mapping, position = [], 0
    for index, character in enumerate(text):
        width = len(fold(character))
        mapping.extend([index] * width)
        position += width
    mapping.append(len(text))
    if end > len(mapping) - 1:
        end = len(mapping) - 1
    return text[mapping[start]:mapping[end]]


def read_sender(lines):
    """Return line above the address window (Name · Straße · PLZ Ort) or the first line that looks like an organisation."""
    for line in lines[:15]:
        parts = [part.strip() for part in re.split(r'\s*[·•|]\s*|,\s+|\s[–-]\s|\s{3,}', line) if part.strip()]
        if len(parts) >= 2 and re.search(r'\b\d{5}\b', line):
            return parts[0], ', '.join(parts[1:])
    for index, line in enumerate(lines[:20]):
        if re.search(SENDER_HINTS, fold(line)):
            address = []
            for follow in lines[index + 1:index + 3]:
                if re.search(r'\d', follow) and len(follow) < 70:
                    address.append(follow)
            return line, ', '.join(address)
    return (lines[0], '') if lines else ('', '')


# The party that wants something, when the letter comes from someone else (court, collection agency, lawyer).
CREDITOR = [
    r'antragsteller(?:in)?\s*:?\s*(?:ist\s+)?(?:die\s+|der\s+)?([^\n,]{3,80}?)(?:\s+macht|\s+hat|\s+verlangt|,|\n|$)',
    r'(?:klaeger(?:in)?|glaeubiger(?:in)?)\s*:\s*([^\n,]{3,80})',
    r'(?:im auftrag|namens und im auftrag|in vollmacht)\s+(?:unserer|unseres|der|des|ihrer|ihres)\s+(?:mandantin|mandanten|auftraggeberin|auftraggebers|glaeubigerin|glaeubigers)\s*,?\s*(?:der\s+|die\s+|des\s+)?(?!fordern|machen|zeigen|teilen|bitten|verlangen)([^\s,][^\n,]{2,79}?)(?:,|\n|\s+fordern|\s+machen|\s+zeigen|\s+teilen|$)',
]


def read_fields(text):
    text =(text or '').replace('\r', '')
    folded = fold(text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    sender, sender_address = read_sender(lines)
    found = dates_in(folded)
    letter_date = None
    for start, _end, value in found:
        before = folded[max(0, start - 40):start]
        if re.search(r'(datum|vom|den|,)\s*$', before) or re.search(r'\b(datum)\b', before):
            letter_date = value
            break
    if not letter_date and found:
        head = len('\n'.join(lines[:25]))
        early = [value for start, _end, value in found if start <= head]
        letter_date = early[0] if early else found[0][2]
    letter_deadline = None
    for start, _end, value in found:
        before = folded[max(0, start - 45):start]
        if re.search(r'(bis zum|bis spaetestens|spaetestens (bis|am|zum)|bis einschliesslich|bis)\s*(zum\s*)?$', before) and (not letter_date or value > letter_date):
            letter_deadline = value
            break
    period = None
    match = re.search(r'(?:innerhalb|binnen)\s+(?:von\s+)?(\d+|' + '|'.join(NUMBERS) + r')\s+(tagen|tag|wochen|woche|monaten|monats|monat)', folded)
    if match:
        amount = int(match.group(1)) if match.group(1).isdigit() else NUMBERS[match.group(1)]
        unit = 'days' if match.group(2).startswith('tag') else 'weeks' if match.group(2).startswith('woche') else 'months'
        period = {'amount': amount, 'unit': unit, 'text': original_slice(text, folded, match.start(), match.end())}
    reference = ''
    match = REFERENCE.search(folded)
    if match:
        reference = original_slice(text, folded, match.start(1), match.end(1)).split('\n')[0].strip(' .,:;')
        reference = re.split(r'\s{2,}|\s(?:datum|vom|tel|telefon)\b', reference, flags=re.I)[0].strip(' .,:;')
    amounts = []
    for match in AMOUNT.finditer(folded):
        value = parse_amount(match.group(1) or match.group(2))
        if value:
            amounts.append((match.start(), value))
    amount = None
    for start, value in amounts:
        if re.search(TOTAL_WORDS + r'[^\n]{0,40}$', folded[max(0, start - 60):start]):
            amount = value
    if amount is None and amounts:
        amount = max(value for _start, value in amounts)
    creditor = ''
    for pattern in CREDITOR:
        match = re.search(pattern, folded)
        if match:
            creditor = original_slice(text, folded, match.start(1), match.end(1)).strip(' .,:;')
            break
    court = ''
    match = re.search(r'\b(amtsgericht|landgericht|arbeitsgericht|sozialgericht|verwaltungsgericht|finanzgericht|oberlandesgericht)\s+([a-z][a-z\-]+(?:\s(?:am|an der|im|in der)\s[a-z][a-z\-]+)?)', folded)
    if match:
        court = original_slice(text, folded, match.start(), match.end()).strip()
    return {
        'sender': sender[:160], 'sender_address': sender_address[:300], 'letter_date': letter_date.isoformat() if letter_date else None,
        'reference': reference[:100], 'amount': amount, 'creditor': creditor[:160], 'court': court[:160],
        'letter_deadline': letter_deadline.isoformat() if letter_deadline else None, 'period': period,
    }


# ---------------------------------------------------------------- what kind of letter it is

def area_for_authority(folded):
    return 'social' if any_of(folded, r'jobcenter|agentur fuer arbeit|sozialamt|rentenversicherung|krankenkasse|pflegekasse|buergergeld|'
                                       r'sozialgesetzbuch|\bsgb\b|elterngeld|wohngeld|versorgungsamt|berufsgenossenschaft') else 'administrative'


KINDS = [
    # id, label, legal area, stage, recognition rule (folded text -> bool)
    ('gerichtsvollzieher', 'Gerichtsvollzieher: Zahlungsaufforderung / Vermögensauskunft', 'contract', 'enforcement', lambda t: 'gerichtsvollzieher' in t and any_of(t, r'vermoegensauskunft', r'802f', r'zahlungsaufforderung', r'ladung')),
    ('pfaendung', 'Kontopfändung / Pfändungsbeschluss', 'contract', 'enforcement', lambda t: any_of(t, r'pfaendungs-? und ueberweisungsbeschluss', r'pfaendungsbeschluss', r'kontopfaendung', r'vorlaeufiges zahlungsverbot', r'pfaendung (ihres|des) (konto|guthaben|arbeitseinkommen)')),
    ('vollstreckungsbescheid', 'Vollstreckungsbescheid', 'contract', 'court', lambda t: 'vollstreckungsbescheid' in t and not has(t, r'antrag auf erlass eines vollstreckungsbescheid')),
    ('mahnbescheid', 'Mahnbescheid vom Gericht', 'contract', 'court', lambda t: 'mahnbescheid' in t),
    ('klage', 'Klage / Post vom Gericht', 'general', 'court', lambda t: any_of(t, r'klageschrift', r'erhebt?\s.{0,30}klage', r'erhebe ich.{0,30}klage', r'verteidigungsanzeige', r'schriftliche[ns]? vorverfahren', r'klageerwiderung', r'guetetermin')),
    ('strafbefehl', 'Strafbefehl', 'criminal', 'court', lambda t: 'strafbefehl' in t),
    ('bussgeld', 'Bußgeldbescheid', 'criminal', 'out_of_court', lambda t: any_of(t, r'bussgeldbescheid')),
    ('anhoerung', 'Anhörungsbogen (Verkehr / Ordnungswidrigkeit)', 'criminal', 'out_of_court', lambda t: any_of(t, r'anhoerungsbogen', r'anhoerung im bussgeldverfahren', r'zeugenfragebogen', r'anhoerung.{0,40}ordnungswidrigkeit')),
    ('betriebspruefung', 'Prüfungsanordnung (Betriebsprüfung)', 'administrative', 'out_of_court', lambda t: any_of(t, r'pruefungsanordnung', r'aussenpruefung', r'betriebspruefung', r'196 ao')),
    ('steuerbescheid', 'Bescheid vom Finanzamt / der Familienkasse', 'administrative', 'out_of_court', lambda t: any_of(t, r'finanzamt', r'familienkasse') and 'bescheid' in t),
    ('bescheid', 'Bescheid einer Behörde', 'administrative', 'out_of_court', lambda t: 'bescheid' in t and any_of(t, r'rechtsbehelfsbelehrung', r'widerspruch', r'behoerde', r'jobcenter', r'agentur fuer arbeit', r'landratsamt', r'stadt ', r'gemeinde', r'kasse')),
    ('abmahnung_urheber', 'Abmahnung (Urheberrecht / Wettbewerb)', 'commercial', 'out_of_court', lambda t: 'abmahnung' in t and any_of(t, r'urheber', r'filesharing', r'tauschboerse', r'unterlassungserklaerung', r'lizenz', r'markenrecht', r'wettbewerb')),
    ('abmahnung_arbeit', 'Abmahnung vom Arbeitgeber', 'employment', 'out_of_court', lambda t: 'abmahnung' in t and any_of(t, r'arbeitsverhaeltnis', r'arbeitsvertrag', r'arbeitspflicht', r'personalakte', r'arbeitgeber')),
    ('eigenkuendigung', 'Kündigung durch einen Mitarbeiter', 'employment', 'out_of_court', lambda t: any_of(t, r'kuendige ich', r'ich kuendige', r'meine kuendigung') and any_of(t, r'arbeitsverhaeltnis', r'arbeitsvertrag', r'beschaeftigungsverhaeltnis', r'arbeitsstelle')),
    ('kuendigung_arbeit', 'Kündigung des Arbeitsverhältnisses', 'employment', 'out_of_court', lambda t: 'kuendig' in t and any_of(t, r'arbeitsverhaeltnis', r'arbeitsvertrag', r'beschaeftigungsverhaeltnis', r'arbeitgeber', r'ausbildungsverhaeltnis')),
    ('kuendigung_wohnung', 'Kündigung der Wohnung', 'tenancy', 'out_of_court', lambda t: 'kuendig' in t and any_of(t, r'mietverhaeltnis', r'mietvertrag', r'wohnung', r'mietsache', r'mieter')),
    ('mieterhoehung', 'Mieterhöhung', 'tenancy', 'out_of_court', lambda t: any_of(t, r'mieterhoehung', r'zustimmung zur erhoehung', r'erhoehung der (netto|grund|kalt)?\s?miete', r'558 bgb')),
    ('betriebskosten', 'Betriebs- / Nebenkostenabrechnung', 'tenancy', 'out_of_court', lambda t: any_of(t, r'betriebskostenabrechnung', r'nebenkostenabrechnung', r'heizkostenabrechnung')),
    ('versicherung_ablehnung', 'Ablehnung durch eine Versicherung', 'contract', 'out_of_court', lambda t: 'versicherung' in t and any_of(t, r'lehnen .{0,40}ab', r'ablehnung', r'nicht eintrittspflichtig', r'keine leistung', r'leistungsfreiheit', r'deckung.{0,30}(versag|ablehn)')),
    ('inkasso', 'Forderung eines Inkassobüros', 'contract', 'out_of_court', lambda t: 'inkasso' in t),
    ('zahlungsaufforderung', 'Rechnung / Mahnung', 'contract', 'out_of_court', lambda t: any_of(t, r'mahnung', r'zahlungserinnerung', r'zahlungsaufforderung', r'rechnung', r'offene forderung', r'zahlungsverzug', r'rueckstand', r'restbetrag', r'ueberweisen sie')),
    ('sonstiges', 'Sonstiges Schreiben', 'general', 'initial', lambda t: True),
]
KIND_IDS = [kind[0] for kind in KINDS]
KIND_INFO = {kind[0]: {'id': kind[0], 'label': kind[1], 'legal_area': kind[2], 'stage': kind[3]} for kind in KINDS}


def classify(text):
    folded = fold(text)
    hits = [kind[0] for kind in KINDS if kind[0] != 'sonstiges' and kind[4](folded)]
    kind = hits[0] if hits else 'sonstiges'
    info = dict(KIND_INFO[kind])
    if kind == 'bescheid':
        info['legal_area'] = area_for_authority(folded)
    return info, hits[1:4]


# ---------------------------------------------------------------- the questions per kind

RECEIVED = {'id': 'received_on', 'type': 'date', 'label': 'Wann haben Sie den Brief bekommen?', 'help': 'Der Tag, an dem der Brief im Briefkasten lag.'}
SERVED = {'id': 'received_on', 'type': 'date', 'label': 'Welches Datum steht auf dem gelben Umschlag?', 'help': 'Post vom Gericht kommt meist im gelben Umschlag. Das dort vermerkte Zustelldatum ist der Fristbeginn. Ohne Umschlag: der Tag, an dem der Brief ankam.'}


def yesno(identifier, label, help_text=''):
    return {'id': identifier, 'type': 'choice', 'label': label, 'help': help_text, 'options': [['yes', 'Ja'], ['no', 'Nein'], ['unsure', 'Weiß ich nicht']]}


OWES = {'id': 'owes', 'type': 'choice', 'label': 'Schulden Sie den geforderten Betrag?', 'help': 'Ehrliche Einschätzung genügt. Sie entscheiden später selbst, was Sie abschicken.',
        'options': [['all', 'Ja, vollständig'], ['part', 'Nur einen Teil'], ['none', 'Nein'], ['unsure', 'Weiß ich nicht']]}

QUESTIONS = {
    'vollstreckungsbescheid': [SERVED, OWES],
    'mahnbescheid': [SERVED, OWES],
    'klage': [SERVED, {'id': 'court_type', 'type': 'choice', 'label': 'Von welchem Gericht kommt die Post?', 'options': [['amtsgericht', 'Amtsgericht'], ['landgericht', 'Landgericht'], ['arbeitsgericht', 'Arbeitsgericht'], ['other', 'Anderes Gericht']]},
              yesno('defend', 'Halten Sie die Forderung oder den Vorwurf für falsch?')],
    'strafbefehl': [SERVED, {'id': 'accused', 'type': 'choice', 'label': 'Stimmt der Vorwurf?', 'options': [['yes', 'Ja, aber die Strafe ist zu hoch'], ['no', 'Nein'], ['part', 'Teilweise'], ['unsure', 'Weiß ich nicht']]}],
    'bussgeld': [SERVED, yesno('driving_ban', 'Droht ein Fahrverbot oder gibt es Punkte in Flensburg?'), yesno('correct', 'Stimmt der Vorwurf (waren Sie z. B. selbst der Fahrer)?')],
    'anhoerung': [RECEIVED, yesno('was_driver', 'Waren Sie selbst der Fahrer bzw. die handelnde Person?', 'Sie müssen sich nicht selbst belasten. Angaben zur Person sind aber Pflicht.')],
    'steuerbescheid': [RECEIVED, yesno('wrong', 'Halten Sie den Bescheid für falsch?'), yesno('must_pay', 'Sollen Sie Geld nachzahlen?')],
    'bescheid': [RECEIVED, yesno('instructions', 'Steht am Ende des Bescheids eine „Rechtsbehelfsbelehrung“ (Hinweis, wie man Widerspruch einlegt)?'), yesno('wrong', 'Halten Sie den Bescheid für falsch?')],
    'abmahnung_urheber': [RECEIVED, yesno('signed', 'Haben Sie die beigefügte Unterlassungserklärung schon unterschrieben?')],
    'abmahnung_arbeit': [RECEIVED, yesno('disagree', 'Halten Sie die Abmahnung für ungerechtfertigt?')],
    'kuendigung_arbeit': [RECEIVED, yesno('fight', 'Möchten Sie sich gegen die Kündigung wehren?', 'Viele Kündigungen enden mit einer Abfindung – das geht nur, wenn Sie rechtzeitig klagen.'),
                          yesno('signed_by_boss', 'Hat der Arbeitgeber selbst (Inhaber/Geschäftsführung) unterschrieben oder lag eine Original-Vollmacht bei?'),
                          {'id': 'end_date', 'type': 'date', 'label': 'Zu welchem Datum soll das Arbeitsverhältnis enden?', 'optional': True}],
    'kuendigung_wohnung': [RECEIVED, yesno('immediate', 'Ist es eine fristlose Kündigung?'),
                           {'id': 'end_date', 'type': 'date', 'label': 'Bis wann sollen Sie ausziehen (Ende des Mietverhältnisses)?', 'optional': True},
                           yesno('hardship', 'Wäre der Auszug für Sie oder Ihre Familie eine besondere Härte?', 'z. B. Krankheit, hohes Alter, Schwangerschaft, Schulwechsel, kein bezahlbarer Ersatzwohnraum.')],
    'mieterhoehung': [RECEIVED, {'id': 'justified', 'type': 'choice', 'label': 'Halten Sie die Erhöhung für berechtigt?', 'help': 'Prüfpunkte: ortsübliche Vergleichsmiete (Mietspiegel), 15 Monate seit der letzten Erhöhung, höchstens 20 % (vielerorts 15 %) in drei Jahren.',
                                   'options': [['yes', 'Ja'], ['no', 'Nein'], ['unsure', 'Weiß ich nicht']]}],
    'betriebskosten': [RECEIVED, yesno('late', 'Endete der Abrechnungszeitraum mehr als 12 Monate bevor die Abrechnung ankam?', 'Beispiel: Abrechnung für 2024, angekommen erst im Januar 2026.'),
                       yesno('objections', 'Haben Sie Zweifel an einzelnen Posten?')],
    'versicherung_ablehnung': [RECEIVED, yesno('disagree', 'Halten Sie die Ablehnung für falsch?')],
    'inkasso': [RECEIVED, OWES, yesno('old', 'Ist die Forderung älter als drei Jahre (gerechnet ab Ende des Entstehungsjahres)?')],
    'zahlungsaufforderung': [RECEIVED, OWES, yesno('old', 'Ist die Forderung älter als drei Jahre (gerechnet ab Ende des Entstehungsjahres)?')],
    'gerichtsvollzieher': [SERVED, OWES, {'id': 'hearing_on', 'type': 'date', 'label': 'Welcher Termin zur Vermögensauskunft steht im Schreiben?', 'optional': True, 'help': 'Leer lassen, wenn kein Termin genannt ist.'}],
    'pfaendung': [SERVED, yesno('p_account', 'Haben Sie schon ein Pfändungsschutzkonto (P-Konto)?'), yesno('children', 'Haben Sie Kinder, für die Sie Unterhalt zahlen oder Kindergeld bekommen?')],
    'betriebspruefung': [RECEIVED, {'id': 'start_on', 'type': 'date', 'label': 'Wann soll die Prüfung beginnen?', 'optional': True}, yesno('postpone', 'Passt der Termin nicht (Urlaub, Krankheit, Jahresabschluss)?')],
    'eigenkuendigung': [RECEIVED, yesno('original', 'Liegt die Kündigung im Original mit Unterschrift vor (nicht nur E-Mail, Fax oder Foto)?'), {'id': 'end_date', 'type': 'date', 'label': 'Zu welchem Datum will der Mitarbeiter gehen?', 'optional': True}],
    'sonstiges': [RECEIVED],
}


# ---------------------------------------------------------------- the result

def period_end(start, amount, unit, state=None):
    try:
        return deadlines.calculate(start, amount, unit, 'event', state)
    except ValueError:
        return None


def end_of_month_after(start, months):
    index = start.month - 1 + months + 1
    first_next = date(start.year + index // 12, index % 12 + 1, 1)
    return first_next - timedelta(days=1)


def to_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


class Result:
    def __init__(self, kind, state=None):
        self.kind, self.state = kind, state
        self.deadline = None
        self.extra_deadlines = []
        self.steps, self.warnings, self.samples = [], [], []
        self.lawyer = None
        self.summary = ''

    def set_deadline(self, label, end, norm, basis, strict=True):
        if end:
            self.deadline = {'date': end.isoformat(), 'label': label, 'norm': norm, 'basis': basis, 'strict': strict}

    def calc(self, label, start, amount, unit, norm, basis, strict=True):
        calculated = period_end(start, amount, unit, self.state) if start else None
        if calculated:
            skipped = ', '.join(item['reason'] for item in calculated['skipped'])
            self.set_deadline(label, date.fromisoformat(calculated['end']), norm, basis + (f' Das Fristende ist wegen {skipped} auf den nächsten Werktag verschoben.' if calculated['shifted'] else ''), strict)
        return calculated

    def as_dict(self, today):
        if self.deadline:
            remaining = (date.fromisoformat(self.deadline['date']) - today).days
            self.deadline['days_left'] = remaining
        urgency = 'low'
        if self.deadline:
            days = self.deadline['days_left']
            urgency = 'overdue' if days < 0 else 'high' if days <= 5 else 'medium' if days <= 14 else 'low'
        return {'kind': KIND_INFO[self.kind], 'summary': self.summary, 'deadline': self.deadline, 'extra_deadlines': self.extra_deadlines,
                'urgency': urgency, 'steps': self.steps, 'warnings': self.warnings, 'samples': self.samples, 'lawyer': self.lawyer,
                'help': help_for(self.kind, self.lawyer), 'state': self.state,
                'disclaimer': f'Berechnet aus Ihren Angaben mit den Feiertagen {"in " + deadlines.STATES[self.state] if self.state else "bundesweit"}.'}


# Where to get (cheap) help, by kind of letter.
HELP = {
    'beratungshilfe': {'title': 'Beratungshilfe – Anwalt für 15 €', 'text': 'Bei geringem Einkommen stellt das Amtsgericht Ihres Wohnorts einen Beratungshilfeschein aus. Damit berät Sie ein Anwalt Ihrer Wahl; Sie zahlen höchstens 15 € (§§ 1, 6 BerHG, Nr. 2500 VV RVG).', 'sample': 'beratungshilfe'},
    'verbraucherzentrale': {'title': 'Verbraucherzentrale', 'text': 'Günstige Beratung zu Verträgen, Inkasso, Versicherungen und Energie.', 'link': 'https://www.verbraucherzentrale.de/beratung'},
    'schuldnerberatung': {'title': 'Kostenlose Schuldnerberatung', 'text': 'Hilft bei Ratenplänen, Pfändungsschutz und Verhandlungen mit Gläubigern.', 'link': 'https://www.meine-schulden.de/beratungsstellen'},
    'mieterverein': {'title': 'Mieterverein', 'text': 'Mietrechtsberatung für Mitglieder, oft ab ca. 5 € im Monat.', 'link': 'https://www.mieterbund.de/mietervereine/'},
    'arbeit': {'title': 'Gewerkschaft / Rechtsantragstelle', 'text': 'Gewerkschaftsmitglieder bekommen Rechtsschutz. Die Klage beim Arbeitsgericht können Sie kostenlos bei der Rechtsantragstelle aufnehmen lassen.', 'link': 'https://www.dgb-rechtsschutz.de/'},
    'versicherungsombudsmann': {'title': 'Versicherungsombudsmann', 'text': 'Kostenlose Schlichtung bei Streit mit der Versicherung bis 10.000 €, verbindlich für den Versicherer.', 'link': 'https://www.versicherungsombudsmann.de/'},
    'sozial': {'title': 'Sozialverband (VdK, SoVD)', 'text': 'Beratung und Vertretung im Widerspruchs- und Klageverfahren bei Sozialleistungen.', 'link': 'https://www.vdk.de/'},
}
HELP_BY_KIND = {
    'mahnbescheid': ['verbraucherzentrale', 'schuldnerberatung'], 'vollstreckungsbescheid': ['schuldnerberatung', 'beratungshilfe'],
    'gerichtsvollzieher': ['schuldnerberatung', 'beratungshilfe'], 'pfaendung': ['schuldnerberatung'], 'inkasso': ['verbraucherzentrale', 'schuldnerberatung'],
    'zahlungsaufforderung': ['verbraucherzentrale'], 'kuendigung_arbeit': ['arbeit', 'beratungshilfe'], 'abmahnung_arbeit': ['arbeit'],
    'kuendigung_wohnung': ['mieterverein', 'beratungshilfe'], 'mieterhoehung': ['mieterverein'], 'betriebskosten': ['mieterverein'],
    'versicherung_ablehnung': ['versicherungsombudsmann', 'verbraucherzentrale'], 'bescheid': ['sozial', 'beratungshilfe'],
    'klage': ['beratungshilfe'], 'strafbefehl': ['beratungshilfe'], 'abmahnung_urheber': ['verbraucherzentrale', 'beratungshilfe'],
}


def help_for(kind, lawyer):
    keys = list(HELP_BY_KIND.get(kind, []))
    if lawyer and 'beratungshilfe' not in keys:
        keys.append('beratungshilfe')
    return [{'id': key, **HELP[key]} for key in keys]


def notice_date(fields, answers):
    """Bekanntgabe of a posted administrative act: the 4th day after posting (§ 122 Abs. 2 Nr. 1 AO, § 41 Abs. 2 VwVfG,
    § 37 Abs. 2 SGB X, each as amended from 2025). If it arrived later, the later day counts – but that must be proven,
    so the earlier, safe date is used for the plan."""
    letter = to_date(fields.get('letter_date'))
    received = to_date(answers.get('received_on'))
    if letter:
        return letter + timedelta(days=4), 'Bescheiddatum + 4 Tage (gesetzliche Bekanntgabe)'
    return received, 'Eingangsdatum'


def evaluate(kind, fields, answers, today=None, state=None):
    today = today or date.today()
    result = Result(kind if kind in KIND_INFO else 'sonstiges', state if state in deadlines.STATES else None)
    kind = result.kind
    received = to_date(answers.get('received_on'))
    amount = fields.get('amount')
    money = f'{amount:,.2f} €'.replace(',', 'X').replace('.', ',').replace('X', '.') if isinstance(amount, (int, float)) and amount else 'den geforderten Betrag'
    letter_deadline = to_date(fields.get('letter_deadline'))
    owes = answers.get('owes')

    if kind == 'mahnbescheid':
        result.summary = f'Ein Gericht hat auf Antrag von {fields.get("creditor") or "dem Gläubiger"} einen Mahnbescheid erlassen. Das Gericht hat nicht geprüft, ob die Forderung besteht.'
        result.calc('Widerspruch beim Mahngericht', received, 2, 'weeks', '§ 692 Abs. 1 Nr. 3, § 694 ZPO',
                    'Zwei Wochen ab Zustellung. Danach kann der Gläubiger einen Vollstreckungsbescheid beantragen.')
        if owes == 'all':
            result.steps = [f'Zahlen Sie {money} einschließlich der im Bescheid genannten Kosten und Zinsen innerhalb der Frist, oder vereinbaren Sie mit dem Gläubiger eine Ratenzahlung.',
                            'Schicken Sie keinen Widerspruch, wenn Sie die Forderung schulden: das verursacht nur weitere Gerichts- und Anwaltskosten.',
                            'Bewahren Sie den Zahlungsbeleg auf.']
            result.samples = ['ratenzahlung']
        else:
            result.steps = ['Legen Sie Widerspruch ein: auf dem beigefügten Formular ankreuzen, unterschreiben und an das Mahngericht schicken (oder online über www.online-mahnantrag.de).',
                            'Eine Begründung ist nicht nötig.' if owes != 'part' else 'Kreuzen Sie den Teilwiderspruch an und tragen Sie den Betrag ein, den Sie bestreiten. Den unstreitigen Teil sollten Sie zahlen.',
                            'Danach muss der Gläubiger klagen und die Forderung beweisen. Das Gericht schreibt Ihnen dann erneut.']
            result.samples = ['widerspruch-mahnbescheid']
        result.warnings.append('Nicht ignorieren: ohne Widerspruch folgt ein Vollstreckungsbescheid, mit dem der Gerichtsvollzieher pfänden darf.')

    elif kind == 'vollstreckungsbescheid':
        result.summary = 'Der Vollstreckungsbescheid wirkt wie ein Urteil: der Gläubiger kann damit sofort pfänden lassen.'
        result.calc('Einspruch (Notfrist)', received, 2, 'weeks', '§§ 700 Abs. 1, 339 Abs. 1 ZPO', 'Zwei Wochen ab Zustellung; die Frist kann nicht verlängert werden.')
        if owes == 'all':
            result.steps = [f'Zahlen Sie {money} samt Kosten, oder bieten Sie sofort eine Ratenzahlung an, damit nicht gepfändet wird.', 'Ein Pfändungsschutzkonto (P-Konto) schützt Ihr Existenzminimum auf dem Girokonto.']
            result.samples = ['ratenzahlung', 'p-konto']
        else:
            result.steps = ['Legen Sie schriftlich Einspruch beim Gericht ein, das den Bescheid erlassen hat.', 'Der Einspruch braucht keine Begründung, aber er muss rechtzeitig beim Gericht ankommen.',
                            'Der Einspruch stoppt die Zwangsvollstreckung nicht automatisch. Bei drohender Pfändung zusätzlich die Einstellung der Zwangsvollstreckung beantragen (§ 719 ZPO).']
            result.samples = ['einspruch-vb']
        result.lawyer = 'Empfohlen: es geht um einen vollstreckbaren Titel.'

    elif kind == 'klage':
        court = answers.get('court_type') or ('arbeitsgericht' if 'arbeitsgericht' in fold(fields.get('court', '')) else 'landgericht' if 'landgericht' in fold(fields.get('court', '')) else 'amtsgericht')
        result.summary = f'Gegen Sie ist ein Gerichtsverfahren anhängig{(" beim " + fields["court"]) if fields.get("court") else ""}.'
        if court == 'arbeitsgericht':
            result.steps = ['Beim Arbeitsgericht gibt es zuerst einen Gütetermin. Das Datum steht im Schreiben: unbedingt hingehen.', 'Schreiben Sie bis dahin auf, was aus Ihrer Sicht passiert ist, und sammeln Sie Unterlagen.',
                            'In der ersten Instanz trägt jede Seite ihre Anwaltskosten selbst (§ 12a ArbGG). Gewerkschaft oder Rechtsschutzversicherung fragen.']
            if letter_deadline:
                result.set_deadline('Frist laut Schreiben des Gerichts', letter_deadline, 'Verfügung des Gerichts', 'Vom Gericht gesetzte Frist.')
        else:
            result.calc('Anzeige, dass Sie sich verteidigen wollen', received, 2, 'weeks', '§ 276 Abs. 1 Satz 1 ZPO',
                        'Im schriftlichen Vorverfahren zwei Wochen ab Zustellung (Notfrist). Für die Klageerwiderung setzt das Gericht eine weitere Frist von mindestens zwei Wochen.')
            if letter_deadline:
                result.extra_deadlines.append({'date': letter_deadline.isoformat(), 'label': 'Im Schreiben genannte Frist (prüfen, wofür sie gilt)'})
            result.steps = ['Lesen Sie die gerichtliche Verfügung: dort steht, welche Frist wofür gilt (Verteidigungsanzeige, Klageerwiderung oder Termin).',
                            'Wenn Sie die Forderung für falsch halten: zeigen Sie fristgerecht an, dass Sie sich verteidigen, und erwidern Sie auf die Klage.' if answers.get('defend') != 'no'
                            else 'Wenn die Forderung berechtigt ist: sprechen Sie mit der Gegenseite über eine Zahlung oder Raten. Ein sofortiges Anerkenntnis kann Kosten sparen (§ 93 ZPO).',
                            'Wer nichts tut, riskiert ein Versäumnisurteil ohne Prüfung der Sache (§ 331 ZPO).']
            result.samples = ['klageerwiderung', 'fristverlaengerung']
            if court == 'landgericht':
                result.lawyer = 'Pflicht: Vor dem Landgericht müssen Sie sich durch einen Anwalt vertreten lassen (§ 78 Abs. 1 ZPO). Wer Kosten nicht tragen kann, prüft Prozesskostenhilfe.'
                result.samples.append('pkh')
            else:
                result.lawyer = 'Empfohlen, beim Amtsgericht aber nicht Pflicht.'

    elif kind == 'strafbefehl':
        result.summary = 'Der Strafbefehl ist eine Verurteilung ohne Verhandlung. Wird er rechtskräftig, steht er einem Urteil gleich.'
        result.calc('Einspruch (Notfrist)', received, 2, 'weeks', '§ 410 Abs. 1 StPO', 'Zwei Wochen ab Zustellung.')
        accused = answers.get('accused')
        result.steps = ['Einspruch schriftlich beim Amtsgericht einlegen, das den Strafbefehl erlassen hat. Eine Begründung ist nicht nötig.',
                        'Sie können den Einspruch auf die Höhe der Tagessätze beschränken, wenn nur Ihr Einkommen falsch geschätzt wurde (§ 410 Abs. 2 StPO).' if accused == 'yes'
                        else 'Nach dem Einspruch gibt es eine Hauptverhandlung. Die Strafe kann dort auch höher ausfallen.',
                        'Äußern Sie sich nicht zur Sache, bevor Sie Akteneinsicht hatten.']
        result.samples = ['einspruch-strafbefehl', 'pflichtverteidiger']
        result.lawyer = 'Dringend empfohlen (Strafverteidigung).'

    elif kind == 'bussgeld':
        result.summary = 'Die Bußgeldstelle hat ein Bußgeld festgesetzt.'
        result.calc('Einspruch gegen den Bußgeldbescheid', received, 2, 'weeks', '§ 67 Abs. 1 OWiG', 'Zwei Wochen ab Zustellung.')
        if answers.get('correct') == 'yes' and answers.get('driving_ban') == 'no':
            result.steps = ['Wenn der Vorwurf stimmt und weder Fahrverbot noch Punkte drohen, ist Zahlen meist der günstigste Weg.', 'Überweisen Sie den Betrag mit dem Kassenzeichen aus dem Bescheid.']
        else:
            result.steps = ['Legen Sie schriftlich Einspruch bei der Bußgeldstelle ein. Eine Begründung ist nicht nötig.', 'Beantragen Sie Akteneinsicht (Messprotokoll, Eichschein, Foto), am besten über einen Anwalt.',
                            'Wichtig bei Fahrverbot: Sie können oft innerhalb von vier Monaten wählen, wann es beginnt (§ 25 Abs. 2a StVG), wenn Sie in den letzten zwei Jahren keines hatten.' if answers.get('driving_ban') == 'yes' else 'Der Einspruch kann bis zur Entscheidung wieder zurückgenommen werden.']
            result.samples = ['einspruch-bussgeld']
            if answers.get('driving_ban') == 'yes':
                result.lawyer = 'Empfohlen, vor allem bei Fahrverbot. Verkehrsrechtsschutz übernimmt die Kosten meist.'

    elif kind == 'anhoerung':
        result.summary = 'Die Behörde ermittelt wegen einer Ordnungswidrigkeit und gibt Ihnen Gelegenheit zur Äußerung.'
        result.steps = ['Angaben zur Person (Name, Geburtsdatum, Anschrift) müssen Sie machen (§ 111 OWiG).', 'Zur Sache dürfen Sie schweigen. Sie müssen sich nicht selbst und nahe Angehörige nicht belasten.',
                        'Wenn Sie selbst gefahren sind und der Vorwurf stimmt, können Sie ihn einräumen. Dann kommt der Bußgeldbescheid.' if answers.get('was_driver') == 'yes'
                        else 'Wenn Sie nicht gefahren sind, können Sie das mitteilen. Den Fahrer müssen Sie nicht nennen; dann kann aber ein Fahrtenbuch angeordnet werden.']
        result.samples = ['anhoerungsbogen']
        if letter_deadline:
            result.set_deadline('Rücksendung erbeten bis', letter_deadline, 'Bitte der Behörde', 'Keine gesetzliche Ausschlussfrist, aber besser einhalten.', strict=False)

    elif kind == 'steuerbescheid':
        start, basis = notice_date(fields, answers)
        result.summary = f'Bescheid vom {fields.get("sender") or "Finanzamt"}. Dagegen ist der Einspruch möglich (beim Kindergeld ebenso).'
        result.calc('Einspruch', start, 1, 'months', '§ 355 Abs. 1, § 122 Abs. 2 Nr. 1 AO', f'Ein Monat ab Bekanntgabe. Berechnet ab {basis}.')
        if answers.get('wrong') != 'no':
            result.steps = ['Legen Sie Einspruch ein: schriftlich oder über ELSTER („Einspruch“). Begründung kann nachgereicht werden.', 'Nennen Sie die Steuernummer und das Datum des Bescheids.']
            result.samples = ['einspruch-finanzamt']
        else:
            result.steps = ['Wenn der Bescheid stimmt, müssen Sie nichts tun außer ggf. pünktlich zahlen.']
        if answers.get('must_pay') == 'yes':
            result.steps.append('Der Einspruch stoppt die Zahlungspflicht nicht. Bei Zweifeln „Aussetzung der Vollziehung“ beantragen (§ 361 AO); wer nicht zahlen kann, beantragt Stundung (§ 222 AO).')
            result.samples.append('stundung-steuer')

    elif kind == 'bescheid':
        start, basis = notice_date(fields, answers)
        social = fields.get('legal_area') == 'social' or area_for_authority(fold(f"{fields.get('sender', '')} {fields.get('sender_address', '')}")) == 'social'
        result.summary = f'Bescheid von {fields.get("sender") or "einer Behörde"}.'
        if answers.get('instructions') == 'no':
            result.calc('Widerspruch (ohne Rechtsbehelfsbelehrung)', start, 1, 'years', '§ 58 Abs. 2 VwGO, § 66 Abs. 2 SGG',
                        f'Fehlt die Belehrung oder ist sie falsch, gilt ein Jahr ab Bekanntgabe. Berechnet ab {basis}. Sicherer ist es, trotzdem innerhalb eines Monats zu handeln.')
        else:
            result.calc('Widerspruch', start, 1, 'months', '§ 70 Abs. 1 VwGO, § 84 Abs. 1 SGG', f'Ein Monat ab Bekanntgabe. Berechnet ab {basis}.')
        if answers.get('wrong') != 'no':
            result.steps = ['Legen Sie schriftlich Widerspruch bei der Stelle ein, die den Bescheid erlassen hat (Anschrift steht in der Rechtsbehelfsbelehrung). Eine Begründung kann nachgereicht werden.',
                            'Beantragen Sie Akteneinsicht, wenn Sie nicht wissen, worauf die Entscheidung beruht.']
            result.samples = ['widerspruch-bescheid', 'akteneinsicht-behoerde']
            if social:
                result.steps.append('Frist verpasst? Bei Sozialleistungen hilft der Überprüfungsantrag (§ 44 SGB X) auch später noch.')
                result.samples.append('ueberpruefungsantrag')
        else:
            result.steps = ['Wenn der Bescheid stimmt, müssen Sie nichts tun. Heften Sie ihn ab.']

    elif kind == 'abmahnung_urheber':
        result.summary = 'Eine Abmahnung verlangt eine Unterlassungserklärung und meist Geld. Die gesetzte Frist ist kurz.'
        if letter_deadline:
            result.set_deadline('Frist laut Abmahnung', letter_deadline, 'Fristsetzung der Gegenseite', 'Verstreicht sie, droht eine einstweilige Verfügung mit hohen Kosten.')
        result.steps = ['Unterschreiben Sie die beigefügte Unterlassungserklärung nicht ungeprüft: sie ist oft zu weit gefasst.' if answers.get('signed') != 'yes'
                        else 'Sie haben bereits unterschrieben: lassen Sie prüfen, ob die Erklärung angefochten oder ihre Reichweite begrenzt werden kann.',
                        'Lassen Sie die Fristen nicht verstreichen: notfalls eine angepasste (modifizierte) Unterlassungserklärung abgeben.', 'Zahlen Sie nicht sofort; die Höhe ist häufig angreifbar (§ 97a UrhG).']
        result.samples = ['abmahnung-urheberrecht']
        result.lawyer = 'Dringend empfohlen.'

    elif kind == 'abmahnung_arbeit':
        result.summary = 'Die Abmahnung ist eine Warnung des Arbeitgebers. Sie ist oft Voraussetzung für eine spätere verhaltensbedingte Kündigung.'
        result.steps = ['Sie müssen nicht unterschreiben, dass Sie einverstanden sind (nur den Empfang bestätigen).',
                        'Sie können eine Gegendarstellung zur Personalakte geben (§ 83 Abs. 2 BetrVG) und die Entfernung verlangen.' if answers.get('disagree') != 'no' else 'Nehmen Sie die Abmahnung ernst: ein gleichartiger Verstoß kann zur Kündigung führen.',
                        'Eine feste gesetzliche Frist gibt es nicht. Reagieren Sie aber zeitnah.']
        result.samples = ['abmahnung-entfernung'] if answers.get('disagree') != 'no' else []

    elif kind == 'kuendigung_arbeit':
        result.summary = 'Ihr Arbeitgeber hat gekündigt. Für die Kündigungsschutzklage gilt eine sehr kurze Frist.'
        result.calc('Kündigungsschutzklage beim Arbeitsgericht', received, 3, 'weeks', '§ 4 Satz 1 KSchG',
                    'Drei Wochen ab Zugang der schriftlichen Kündigung. Danach gilt die Kündigung in aller Regel als wirksam (§ 7 KSchG).')
        end = to_date(answers.get('end_date'))
        if received:
            report = received + timedelta(days=3)
            result.extra_deadlines.append({'date': report.isoformat(), 'label': 'Bei der Agentur für Arbeit arbeitsuchend melden (§ 38 Abs. 1 SGB III)'
                                           + (' – spätestens drei Monate vor dem Ende, sonst innerhalb von drei Tagen' if end and (end - received).days > 92 else ' – innerhalb von drei Tagen nach Kenntnis')})
        result.steps = ['Melden Sie sich sofort arbeitsuchend bei der Agentur für Arbeit (online möglich). Sonst droht eine Sperrzeit beim Arbeitslosengeld.']
        if answers.get('signed_by_boss') in ('no', 'unsure'):
            result.steps.append('Hat jemand ohne Original-Vollmacht unterschrieben, können Sie die Kündigung unverzüglich zurückweisen (§ 174 BGB) – möglichst innerhalb einer Woche.')
            result.samples.append('174-zurueckweisung')
            if received:
                result.extra_deadlines.append({'date': (received + timedelta(days=7)).isoformat(), 'label': 'Zurückweisung nach § 174 BGB (unverzüglich, ca. eine Woche)'})
        if answers.get('fight') != 'no':
            result.steps.append('Klage beim Arbeitsgericht einreichen – selbst bei der Rechtsantragstelle des Gerichts oder über einen Anwalt. In der ersten Instanz gibt es keinen Anwaltszwang.')
            result.samples.insert(0, 'kschg-klage')
        result.steps.append('Verlangen Sie ein qualifiziertes Arbeitszeugnis.')
        result.samples.append('zeugnis')
        result.lawyer = 'Empfohlen (Fachanwalt für Arbeitsrecht, Gewerkschaft oder Rechtsschutzversicherung). Viele Klagen enden mit einer Abfindung im Vergleich.'

    elif kind == 'kuendigung_wohnung':
        end = to_date(answers.get('end_date'))
        result.summary = 'Ihr Vermieter hat das Mietverhältnis gekündigt. Sie müssen nicht ausziehen, nur weil eine Kündigung kommt; im Streit entscheidet ein Gericht.'
        if answers.get('immediate') == 'yes':
            result.steps = ['Bei fristloser Kündigung wegen Mietrückstand: Wer alle Rückstände spätestens zwei Monate nach Zustellung einer Räumungsklage bezahlt (oder das Sozialamt/Jobcenter die Übernahme zusagt), macht die fristlose Kündigung unwirksam (§ 569 Abs. 3 Nr. 2 BGB).',
                            'Prüfen Sie, ob die genannten Gründe stimmen, und widersprechen Sie schriftlich.', 'Wenden Sie sich sofort an einen Mieterverein, das Jobcenter/Sozialamt (Übernahme von Mietschulden) oder einen Anwalt.']
        else:
            result.steps = ['Prüfen Sie: Ist die Kündigung schriftlich, mit Grund (z. B. Eigenbedarf) und mit der richtigen Kündigungsfrist (§ 573c BGB: 3 bis 9 Monate je nach Wohndauer)?']
        if answers.get('hardship') != 'no' and end:
            two_months = deadlines.add_months(end, -2)[0] or deadlines.add_months(end, -2)[1]
            result.set_deadline('Widerspruch wegen Härte', two_months, '§§ 574, 574b Abs. 2 BGB', 'Spätestens zwei Monate vor dem Ende des Mietverhältnisses beim Vermieter (schriftlich).')
            result.steps.append('Bei einer Härte: schriftlich Widerspruch einlegen und die Gründe nennen.')
            result.samples.append('kuendigung-widerspruch-574')
        elif answers.get('hardship') != 'no':
            result.steps.append('Bei einer Härte: Widerspruch spätestens zwei Monate vor dem Ende des Mietverhältnisses (§ 574b BGB). Tragen Sie das Enddatum ein, dann berechnen wir die Frist.')
            result.samples.append('kuendigung-widerspruch-574')
        result.lawyer = 'Empfohlen: Mieterverein oder Fachanwalt für Mietrecht.'

    elif kind == 'mieterhoehung':
        result.summary = 'Der Vermieter verlangt Ihre Zustimmung zu einer höheren Miete.'
        if received:
            result.set_deadline('Zustimmung oder Ablehnung', end_of_month_after(received, 2), '§ 558b Abs. 1, 2 BGB',
                                'Bis zum Ende des zweiten Kalendermonats nach Zugang. Danach kann der Vermieter innerhalb von drei weiteren Monaten auf Zustimmung klagen.')
        if answers.get('justified') == 'yes':
            result.steps = ['Wenn die Erhöhung berechtigt ist: stimmen Sie schriftlich zu. Die höhere Miete gilt ab dem dritten Monat nach Zugang.']
        else:
            result.steps = ['Prüfen Sie den Mietspiegel Ihrer Stadt und die Begründung des Vermieters.', 'Sie können ganz oder teilweise zustimmen. Schweigen gilt nicht als Zustimmung.',
                            'Teilen Sie mit, dass Sie (noch) nicht zustimmen, und nennen Sie die Gründe.']
            result.samples = ['mieterhoehung-ablehnung']

    elif kind == 'betriebskosten':
        result.summary = 'Abrechnung der Nebenkosten für einen Abrechnungszeitraum.'
        if received:
            result.calc('Einwendungen gegen die Abrechnung', received, 12, 'months', '§ 556 Abs. 3 Satz 5, 6 BGB', 'Zwölf Monate ab Zugang der Abrechnung.', strict=True)
        if answers.get('late') == 'yes':
            result.steps.append('Kam die Abrechnung später als zwölf Monate nach Ende des Abrechnungszeitraums, darf der Vermieter in der Regel keine Nachzahlung mehr verlangen (§ 556 Abs. 3 Satz 3 BGB). Ein Guthaben müssen Sie trotzdem bekommen.')
        result.steps.append('Sie dürfen die Belege einsehen. Bis dahin können Sie die Nachzahlung zurückhalten.')
        if answers.get('objections') != 'no':
            result.samples = ['betriebskosten-einwand']

    elif kind == 'versicherung_ablehnung':
        result.summary = 'Die Versicherung hat eine Leistung abgelehnt.'
        result.steps = ['Verlangen Sie eine schriftliche Begründung und prüfen Sie die Versicherungsbedingungen.', 'Widersprechen Sie schriftlich und legen Sie Belege bei.',
                        'Kostenlose Schlichtung: Versicherungsombudsmann bzw. PKV-Ombudsmann.', 'Ansprüche verjähren in der Regel drei Jahre nach Ende des Jahres, in dem sie entstanden sind (§§ 195, 199 BGB).']
        result.samples = ['versicherung-ablehnung'] if answers.get('disagree') != 'no' else []

    elif kind in ('inkasso', 'zahlungsaufforderung'):
        creditor = fields.get('creditor') or fields.get('sender') or ('das Inkassobüro' if kind == 'inkasso' else 'der Absender')
        result.summary = f'{creditor} verlangt Zahlung von {money}.'
        if letter_deadline:
            result.set_deadline('Zahlungsfrist laut Schreiben', letter_deadline, 'Fristsetzung des Gläubigers', 'Keine gesetzliche Frist; danach drohen aber weitere Kosten und ein Mahnbescheid.', strict=False)
        elif fields.get('period') and received:
            period = fields['period']
            result.calc('Zahlungsfrist laut Schreiben', received, period['amount'], period['unit'], 'Fristsetzung des Gläubigers',
                        f'„{period["text"]}“ ab Eingang gerechnet. Keine gesetzliche Frist; danach drohen aber weitere Kosten und ein Mahnbescheid.', strict=False)
        if answers.get('old') == 'yes':
            result.steps.append('Die Forderung könnte verjährt sein (drei Jahre ab Jahresende, §§ 195, 199 BGB). Dann dürfen Sie die Zahlung verweigern – aber nur, wenn Sie die Einrede erheben.')
            result.samples.append('verjaehrung')
        if owes == 'all':
            result.steps.append(f'Wenn Sie {money} schulden: zahlen Sie die Hauptforderung, oder schlagen Sie Raten vor.')
            if kind == 'inkasso':
                result.steps.append('Inkassokosten sind nur zu ersetzen, wenn Sie vorher in Verzug waren (§ 286 BGB), und nur in begrenzter Höhe. Unklare Kostenpositionen können Sie zurückweisen.')
            result.samples.append('ratenzahlung')
        elif owes in ('none', 'part', 'unsure'):
            result.steps.append('Widersprechen Sie schriftlich und verlangen Sie eine nachvollziehbare Aufstellung (Vertrag, Datum, Hauptforderung, Zinsen, Kosten).')
            result.samples.append('inkasso-bestreiten' if kind == 'inkasso' else 'forderung-zurueckweisen')
            result.steps.append('Kommt danach ein Mahnbescheid vom Gericht: unbedingt innerhalb von zwei Wochen widersprechen.')
        result.steps.append('Einen negativen Eintrag bei Auskunfteien (z. B. Schufa) darf es für eine bestrittene Forderung grundsätzlich nicht geben.')

    elif kind == 'gerichtsvollzieher':
        result.summary = 'Der Gerichtsvollzieher vollstreckt eine Forderung, für die der Gläubiger schon einen Titel hat (Urteil, Vollstreckungsbescheid).'
        result.calc('Zahlungsfrist des Gerichtsvollziehers', received, 2, 'weeks', '§ 802f Abs. 1 ZPO', 'Zwei Wochen ab Zustellung. Danach findet der Termin zur Vermögensauskunft statt.')
        hearing = to_date(answers.get('hearing_on'))
        if hearing:
            result.extra_deadlines.append({'date': hearing.isoformat(), 'label': 'Termin zur Vermögensauskunft beim Gerichtsvollzieher'})
        result.steps = [f'Zahlen Sie {money} bis zum Fristende an den Gerichtsvollzieher – dann ist die Sache erledigt.' if owes == 'all'
                        else 'Rufen Sie den Gerichtsvollzieher an und bieten Sie eine Ratenzahlung an. Er kann einen Zahlungsplan bewilligen und die Vollstreckung so lange aufschieben (§ 802b ZPO).',
                        'Gehen Sie zum Termin. Wer nicht erscheint, riskiert einen Haftbefehl (§ 802g ZPO) und einen Eintrag im Schuldnerverzeichnis.',
                        'Richten Sie ein P-Konto ein, damit Ihr Grundbetrag auf dem Konto geschützt ist.']
        result.samples = ['ratenzahlung', 'p-konto']
        if owes in ('none', 'part'):
            result.steps.append('Gegen den Titel selbst hilft nur ein Rechtsbehelf beim Gericht, z. B. Einspruch gegen den Vollstreckungsbescheid, solange die Frist läuft.')

    elif kind == 'pfaendung':
        result.summary = 'Ein Gläubiger hat Ihr Konto oder Ihren Lohn pfänden lassen. Ein Grundbetrag bleibt geschützt – auf dem Konto aber nur mit P-Konto.'
        if answers.get('p_account') != 'yes':
            result.calc('Konto in ein P-Konto umwandeln', received, 1, 'months', '§ 850k Abs. 1 ZPO',
                        'Wandeln Sie das Konto innerhalb eines Monats nach Zustellung um, wirkt der Schutz zurück. Die Bank muss spätestens ab dem vierten Geschäftstag umstellen.')
            result.steps.append('Verlangen Sie bei Ihrer Bank sofort die Umwandlung in ein P-Konto. Das kostet nicht mehr als das bisherige Konto.')
            result.samples.append('p-konto')
        result.steps.append('Mit einer Bescheinigung nach § 903 ZPO (Schuldnerberatung, Arbeitgeber, Familienkasse, Jobcenter) wird der Freibetrag für Kinder und Kindergeld erhöht.' if answers.get('children') == 'yes'
                            else 'Der Grundfreibetrag ist automatisch geschützt; Sozialleistungen wie Kindergeld lassen sich mit einer Bescheinigung nach § 903 ZPO zusätzlich schützen.')
        result.steps.append('Sprechen Sie mit dem Gläubiger über Raten – dann kann er die Pfändung ruhen lassen.')
        result.samples.append('ratenzahlung')

    elif kind == 'betriebspruefung':
        start, basis = notice_date(fields, answers)
        result.summary = 'Das Finanzamt kündigt eine Außenprüfung (Betriebsprüfung) an.'
        result.calc('Einspruch gegen die Prüfungsanordnung', start, 1, 'months', '§§ 196, 355 AO', f'Ein Monat ab Bekanntgabe. Berechnet ab {basis}.', strict=False)
        begin = to_date(answers.get('start_on'))
        if begin:
            result.extra_deadlines.append({'date': begin.isoformat(), 'label': 'Beginn der Außenprüfung'})
        result.steps = ['Informieren Sie Ihren Steuerberater und stellen Sie Buchhaltung, Belege und Verträge für den Prüfungszeitraum zusammen.',
                        'Klären Sie, welche Daten digital übergeben werden (GoBD-Datenzugriff).',
                        'Ein Arbeitsplatz für den Prüfer muss bereitstehen; Auskünfte gibt eine benannte Auskunftsperson.']
        if answers.get('postpone') == 'yes':
            result.steps.insert(0, 'Beantragen Sie mit Begründung eine Verlegung des Prüfungsbeginns (§ 197 Abs. 2 AO). Bei wichtigen Gründen wird das regelmäßig gewährt.')
            result.samples.append('fristverlaengerung-steuer')

    elif kind == 'eigenkuendigung':
        end = to_date(answers.get('end_date'))
        result.summary = 'Ein Mitarbeiter hat das Arbeitsverhältnis gekündigt.'
        if answers.get('original') == 'no':
            result.steps.append('Eine Kündigung per E-Mail, Fax, WhatsApp oder Foto ist unwirksam (Schriftform, § 623 BGB). Verlangen Sie das unterschriebene Original.')
        result.steps += ['Prüfen Sie die Kündigungsfrist (Arbeitsvertrag, Tarifvertrag, sonst § 622 BGB: vier Wochen zum 15. oder Monatsende) und bestätigen Sie den Beendigungstermin schriftlich.',
                         'Planen Sie Resturlaub und Überstunden; nicht genommener Urlaub ist auszuzahlen (§ 7 Abs. 4 BUrlG).',
                         'Erteilen Sie ein Arbeitszeugnis (§ 109 GewO) und erstellen Sie die Arbeitsbescheinigung für die Agentur für Arbeit.']
        if end:
            result.set_deadline('Letzter Arbeitstag', end, '§ 622 BGB / Arbeitsvertrag', 'Beendigung des Arbeitsverhältnisses laut Kündigung.', strict=False)
            report = end + timedelta(weeks=6)
            result.extra_deadlines.append({'date': report.isoformat(), 'label': 'Abmeldung bei der Krankenkasse (spätestens sechs Wochen nach Ende, § 8 DEÜV)'})
        result.samples = ['zeugnis']

    else:
        result.summary = 'Für diese Art von Schreiben gibt es keinen festen Ablauf. Die erkannten Daten sind in der Akte gespeichert.'
        if letter_deadline:
            result.set_deadline('Frist laut Schreiben', letter_deadline, 'Angabe im Schreiben', 'Vom Absender genannte Frist.', strict=False)
        else:
            period = fields.get('period')
            if period and received:
                result.calc('Frist laut Schreiben', received, period['amount'], period['unit'], 'Angabe im Schreiben', f'„{period["text"]}“ ab Eingang gerechnet.', strict=False)
        result.steps = ['Prüfen Sie, was der Absender von Ihnen verlangt und bis wann.', 'In der Musterbibliothek finden Sie über 100 Vorlagen für Antworten.',
                        'Antworten Sie schriftlich und heben Sie eine Kopie auf.']
    return result.as_dict(today)


# ---------------------------------------------------------------- API

class AnalyzeInput(BaseModel):
    model_config = {'extra': 'forbid'}
    text: str = Field(min_length=20, max_length=120000)


class EvaluateInput(BaseModel):
    model_config = {'extra': 'forbid'}
    kind: Literal[tuple(KIND_IDS)]
    fields: dict = Field(default_factory=dict)
    answers: dict = Field(default_factory=dict)
    state: Literal[tuple(deadlines.STATES)] | None = None


class MoveInput(BaseModel):
    model_config = {'extra': 'forbid'}
    from_case_id: str = Field(min_length=1, max_length=64)
    document_id: str = Field(min_length=1, max_length=64)
    to_case_id: str = Field(min_length=1, max_length=64)


# Title the assistant gives the provisional case it opens for an upload before the letter is read.
PROVISIONAL_TITLES = ('Eingegangener Brief (in Prüfung)', 'Received letter (being checked)')


def router(require_user, db=None, record_activity=None, now=None, row_case=None):
    routes = APIRouter()

    if db is not None:
        @routes.post('/api/letter-assistant/move-letter')
        def move_letter(payload: MoveInput, user: dict = Depends(require_user)):
            """Files an uploaded letter in an existing case and retires the provisional case it was read in."""
            allowed = user.get('allowed_cases')
            if allowed is not None and (payload.from_case_id not in allowed or payload.to_case_id not in allowed):
                raise HTTPException(404, 'Case not found')
            if payload.from_case_id == payload.to_case_id:
                raise HTTPException(409, 'same_case')
            with db() as connection:
                connection.execute('BEGIN IMMEDIATE')
                source = connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (payload.from_case_id, user['id'])).fetchone()
                target = connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (payload.to_case_id, user['id'])).fetchone()
                if not source or not target:
                    raise HTTPException(404, 'Case not found')
                document = connection.execute('SELECT * FROM documents WHERE id=? AND case_id=?', (payload.document_id, payload.from_case_id)).fetchone()
                if not document:
                    raise HTTPException(404, 'Document not found')
                connection.execute('UPDATE documents SET case_id=? WHERE id=?', (payload.to_case_id, payload.document_id))
                record_activity(connection, payload.to_case_id, 'document_uploaded', document['original_name'])
                record_activity(connection, payload.from_case_id, 'document_moved', f"{document['original_name']} → {target['reference']}")
                # Only the empty provisional case is archived; a case with any other content stays as it is.
                left = connection.execute("""SELECT (SELECT COUNT(*) FROM documents WHERE case_id=:c) + (SELECT COUNT(*) FROM tasks WHERE case_id=:c)
                    + (SELECT COUNT(*) FROM drafts WHERE case_id=:c)""", {'c': payload.from_case_id}).fetchone()[0]
                if not left and source['title'] in PROVISIONAL_TITLES and not source['archived_at']:
                    connection.execute('UPDATE cases SET archived_at=?,archive_version=archive_version+1 WHERE id=?', (now(), payload.from_case_id))
                    record_activity(connection, payload.from_case_id, 'case_archived')
                return row_case(connection.execute('SELECT * FROM cases WHERE id=?', (payload.to_case_id,)).fetchone(), connection)

    @routes.get('/api/letter-assistant/kinds')
    def kinds(user: dict = Depends(require_user)):
        return [{**KIND_INFO[kind], 'questions': QUESTIONS[kind]} for kind in KIND_IDS]

    @routes.post('/api/letter-assistant/analyze')
    def analyze(payload: AnalyzeInput, user: dict = Depends(require_user)):
        kind, alternatives = classify(payload.text)
        return {'kind': kind, 'alternatives': [KIND_INFO[item] for item in alternatives], 'fields': read_fields(payload.text), 'questions': QUESTIONS[kind['id']]}

    @routes.post('/api/letter-assistant/evaluate')
    def evaluate_letter(payload: EvaluateInput, user: dict = Depends(require_user)):
        fields = dict(payload.fields)
        if fields.get('amount') not in (None, ''):
            try:
                fields['amount'] = float(fields['amount'])
            except (TypeError, ValueError):
                raise HTTPException(422, 'invalid_amount')
        for key in ('letter_date', 'letter_deadline'):
            if fields.get(key) and not to_date(fields[key]):
                raise HTTPException(422, 'invalid_date')
        if payload.answers.get('received_on') and not to_date(payload.answers['received_on']):
            raise HTTPException(422, 'invalid_date')
        return evaluate(payload.kind, fields, payload.answers, state=payload.state)

    return routes
