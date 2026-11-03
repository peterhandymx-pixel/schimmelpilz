"""Outgoing email through the operator's own SMTP server.

Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM and SMTP_SECURITY (starttls|ssl|none).
For local testing, MAIL_OUTBOX_DIR writes each message as an .eml file instead of sending it.
Nothing is sent when neither is configured.
"""
import os
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


class MailUnavailable(RuntimeError):
    pass


def outbox():
    value = os.getenv('MAIL_OUTBOX_DIR', '').strip()
    return Path(value) if value else None


def configured():
    return bool(outbox() or (os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM')))


def send(to, subject, body, attachments=(), reply_to=None):
    """attachments: iterable of (filename, bytes, maintype, subtype). Returns the Message-ID."""
    if not configured():
        raise MailUnavailable('mail_not_configured')
    sender = os.getenv('SMTP_FROM', 'Schimmelpilz <noreply@localhost>')
    message = EmailMessage()
    message['From'], message['To'], message['Subject'] = sender, to, subject
    message['Date'] = formatdate(localtime=True)
    message['Message-ID'] = make_msgid(domain=sender.rsplit('@', 1)[-1].strip('> ') or 'localhost')
    if reply_to:
        message['Reply-To'] = reply_to
    message.set_content(body)
    for filename, content, maintype, subtype in attachments:
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    folder = outbox()
    if folder:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{uuid.uuid4()}.eml').write_bytes(bytes(message))
        return message['Message-ID']
    host, security = os.environ['SMTP_HOST'], os.getenv('SMTP_SECURITY', 'starttls').lower()
    port = int(os.getenv('SMTP_PORT') or (465 if security == 'ssl' else 587 if security == 'starttls' else 25))
    context = ssl.create_default_context()
    try:
        if security == 'ssl':
            client = smtplib.SMTP_SSL(host, port, timeout=30, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=30)
        with client:
            if security == 'starttls':
                client.starttls(context=context)
            if os.getenv('SMTP_USER'):
                client.login(os.environ['SMTP_USER'], os.getenv('SMTP_PASSWORD', ''))
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise MailUnavailable('mail_delivery_failed') from None
    return message['Message-ID']
