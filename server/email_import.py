"""E-mails into the case file: .eml (RFC 822) and Outlook .msg become one PDF of the message plus its attachments.

No AI and no network: the standard library parses .eml, olefile reads the Outlook compound file. The PDF carries
sender, recipients, date, subject and the plain text (HTML bodies are reduced to text). Attachments of allowed types
are stored as separate documents; everything else is listed in the PDF as "nicht übernommen".
"""
import email
import email.policy
import html
import io
import re
import struct
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

MAIL_EXTENSIONS = {'.eml', '.msg'}
MAX_ATTACHMENTS = 30


class MailError(ValueError):
    pass


def html_to_text(markup: str) -> str:
    markup = re.sub(r'(?is)<(script|style|head)\b.*?</\1>', ' ', markup or '')
    markup = re.sub(r'(?i)<br\s*/?>|</(p|div|tr|li|h[1-6]|table)>', '\n', markup)
    markup = re.sub(r'(?i)<li\b[^>]*>', '• ', markup)
    text = html.unescape(re.sub(r'<[^>]+>', '', markup)).replace('\xa0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n\s*\n\s*\n+', '\n\n', '\n'.join(line.strip() for line in text.split('\n'))).strip()


def clean(value, limit=500):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def safe_name(name, fallback):
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', '_', (name or '').replace('\\', '/').split('/')[-1]).strip(' .')
    return (name or fallback)[:200]


def parse_eml(data: bytes) -> dict:
    try:
        message = email.message_from_bytes(data, policy=email.policy.default)
    except Exception as error:  # malformed input
        raise MailError('unreadable_mail') from error
    if not (message['from'] or message['subject'] or message['date']):
        raise MailError('not_a_mail')
    when = None
    try:
        when = parsedate_to_datetime(message['date']) if message['date'] else None
    except (TypeError, ValueError):
        when = None
    plain, markup, attachments = [], [], []
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = (part.get_content_disposition() or '').lower()
        filename = part.get_filename()
        kind = part.get_content_type()
        if disposition == 'attachment' or filename or kind == 'message/rfc822':
            if kind == 'message/rfc822':
                payload = part.get_payload()
                inner = payload[0] if isinstance(payload, list) and payload else payload
                content = inner.as_bytes() if hasattr(inner, 'as_bytes') else b''
                filename = filename or 'weitergeleitete-nachricht.eml'
            else:
                content = part.get_payload(decode=True) or b''
            attachments.append({'name': safe_name(filename, f'anhang-{len(attachments) + 1}'), 'data': content})
            continue
        try:
            text = part.get_content()
        except Exception:
            text = (part.get_payload(decode=True) or b'').decode('latin-1', 'replace')
        if kind == 'text/plain':
            plain.append(text)
        elif kind == 'text/html':
            markup.append(text)
    body = '\n\n'.join(plain).strip() or html_to_text('\n'.join(markup))
    return {'subject': clean(message['subject']), 'sender': clean(message['from']), 'to': clean(message['to'], 1500), 'cc': clean(message['cc'], 1500),
            'date': when, 'body': body, 'attachments': attachments}


def filetime(value: int):
    if not value:
        return None
    try:
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value // 10)
    except OverflowError:
        return None


def parse_msg(data: bytes) -> dict:
    import olefile
    if not olefile.isOleFile(io.BytesIO(data)):
        raise MailError('not_a_mail')
    ole = olefile.OleFileIO(io.BytesIO(data))
    try:
        return read_msg(ole)
    finally:
        ole.close()


def read_msg(ole, root=()) -> dict:
    """Outlook message from an olefile-like object (exists, openstream, listdir); root is the storage path."""
    def stream(name):
        path = list(root) + [name]
        return ole.openstream(path).read() if ole.exists('/'.join(path)) else None

    def text(tag):
        raw = stream(f'__substg1.0_{tag}001F')
        if raw is not None:
            return raw.decode('utf-16-le', 'replace').rstrip('\x00')
        raw = stream(f'__substg1.0_{tag}001E')
        return raw.decode('cp1252', 'replace').rstrip('\x00') if raw is not None else ''

    subject = text('0037')
    if not subject and not text('0C1A') and not text('1000') and stream('__properties_version1.0') is None:
        raise MailError('not_a_mail')
    sender_name, sender_mail = text('0C1A'), text('0C1F') or text('5D01')
    sender = f'{sender_name} <{sender_mail}>' if sender_name and sender_mail and sender_mail not in sender_name else sender_name or sender_mail
    when = None
    headers = text('007D')
    match = re.search(r'(?im)^Date:\s*(.+)$', headers or '')
    if match:
        try:
            when = parsedate_to_datetime(match.group(1).strip())
        except (TypeError, ValueError):
            when = None
    properties = stream('__properties_version1.0')
    if when is None and properties and len(properties) > 32:
        found = {}
        for offset in range(32, len(properties) - 15, 16):
            tag, _flags, value = struct.unpack('<IIQ', properties[offset:offset + 16])
            found[tag] = value
        when = filetime(found.get(0x0E060040) or found.get(0x00390040) or 0)
    body = text('1000')
    if not body:
        raw_html = stream('__substg1.0_10130102')
        if raw_html:
            body = html_to_text(raw_html.decode('utf-8', 'replace') if b'charset=utf-8' in raw_html[:2000].lower() else raw_html.decode('cp1252', 'replace'))
    attachments = []
    for entry in sorted({tuple(path[:len(root) + 1]) for path in ole.listdir(streams=True, storages=True) if list(path[:len(root)]) == list(root) and len(path) > len(root)}):
        name = entry[-1]
        if not name.startswith('__attach_version1.0_'):
            continue
        sub = list(entry)

        def sub_text(tag):
            for suffix, codec in (('001F', 'utf-16-le'), ('001E', 'cp1252')):
                path = '/'.join(sub + [f'__substg1.0_{tag}{suffix}'])
                if ole.exists(path):
                    return ole.openstream(sub + [f'__substg1.0_{tag}{suffix}']).read().decode(codec, 'replace').rstrip('\x00')
            return ''

        filename = sub_text('3707') or sub_text('3704') or sub_text('3001')
        data_path = sub + ['__substg1.0_37010102']
        if ole.exists('/'.join(data_path)):
            content = ole.openstream(data_path).read()
        else:
            content = b''  # embedded Outlook item or OLE object: listed but not stored
            filename = filename or 'eingebettetes-element.msg'
        attachments.append({'name': safe_name(filename, f'anhang-{len(attachments) + 1}'), 'data': content})
    return {'subject': clean(subject), 'sender': clean(sender), 'to': clean(text('0E04'), 1500), 'cc': clean(text('0E03'), 1500),
            'date': when, 'body': (body or '').replace('\r\n', '\n').strip(), 'attachments': attachments}


def parse(data: bytes, extension: str) -> dict:
    return parse_msg(data) if extension == '.msg' else parse_eml(data)


def local(moment):
    if not moment:
        return ''
    try:
        from zoneinfo import ZoneInfo
        moment = moment.astimezone(ZoneInfo('Europe/Berlin')) if moment.tzinfo else moment
    except Exception:
        pass
    return moment.strftime('%d.%m.%Y, %H:%M Uhr')


def mail_pdf(mail: dict, case_reference: str, stored: list[str], skipped: list[str]) -> bytes:
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=10, leading=13.5, textColor=colors.HexColor('#1f2d26'))
    small = ParagraphStyle('small', parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor('#5d6b60'))
    bold = ParagraphStyle('bold', parent=base, fontName='Helvetica-Bold')
    title = ParagraphStyle('title', parent=base, fontName='Helvetica-Bold', fontSize=14, leading=18, spaceAfter=6)
    cell = lambda value, style=base: Paragraph(escape(str(value)), style)
    rows = [[cell('Von', bold), cell(mail['sender'] or '–')], [cell('An', bold), cell(mail['to'] or '–')]]
    if mail['cc']:
        rows.append([cell('Kopie', bold), cell(mail['cc'])])
    rows += [[cell('Datum', bold), cell(local(mail['date']) or '–')], [cell('Betreff', bold), cell(mail['subject'] or '(ohne Betreff)')]]
    if stored or skipped:
        listed = [f'{name} (in der Akte)' for name in stored] + [f'{name} (nicht übernommen)' for name in skipped]
        rows.append([cell('Anhänge', bold), cell('; '.join(listed))])
    head = Table(rows, colWidths=[22 * mm, None])
    head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, -1), (-1, -1), 0.8, colors.HexColor('#2f5d4d')),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    story = [Paragraph('E-Mail', title), head, Spacer(1, 10)]
    body = mail['body'] or '(Kein Text in der Nachricht.)'
    for block in body[:400000].split('\n'):
        story.append(Paragraph(escape(block).replace('\t', '    ') or '&nbsp;', base))

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(colors.HexColor('#5d6b60'))
        canvas.drawString(20 * mm, 12 * mm, f'Akte {case_reference} · E-Mail vom {local(mail["date"]) or "unbekannten Datum"} · in die Akte übernommen')
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f'Seite {doc.page}')
        canvas.restoreState()

    output = io.BytesIO()
    SimpleDocTemplate(output, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                      title=mail['subject'] or 'E-Mail', author='').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def pdf_name(mail: dict) -> str:
    day = mail['date'].strftime('%Y-%m-%d') + ' ' if mail['date'] else ''
    return safe_name(f'E-Mail {day}{mail["subject"] or "ohne Betreff"}'[:150], 'E-Mail') + '.pdf'
