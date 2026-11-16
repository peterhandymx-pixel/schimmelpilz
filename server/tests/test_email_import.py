import io
import struct
from email.message import EmailMessage

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server import app as api, email_import
from server.tests import test_inbox


def sample_eml(html_only=False):
    message = EmailMessage()
    message['From'] = 'Müller Bau GmbH <info@mueller-bau.example>'
    message['To'] = 'kanzlei@example.invalid'
    message['Subject'] = 'Ihre Mängelrüge vom 03.11.2026'
    message['Date'] = 'Tue, 10 Nov 2026 09:15:00 +0100'
    if html_only:
        message.set_content('<html><body><p>Sehr geehrte Damen und Herren,</p><p>wir weisen die M&auml;ngel zur&uuml;ck.</p><script>x()</script></body></html>', subtype='html')
    else:
        message.set_content('Sehr geehrte Damen und Herren,\nwir weisen die Mängel zurück.\nMit freundlichen Grüßen')
        message.add_attachment(b'%PDF-1.4 fake', maintype='application', subtype='pdf', filename='Stellungnahme.pdf')
        message.add_attachment(b'MZ', maintype='application', subtype='octet-stream', filename='programm.exe')
    return message.as_bytes()


def test_parse_eml_text_attachments_and_html():
    mail = email_import.parse_eml(sample_eml())
    assert mail['subject'] == 'Ihre Mängelrüge vom 03.11.2026'
    assert 'Müller Bau' in mail['sender'] and 'zurück' in mail['body']
    assert [item['name'] for item in mail['attachments']] == ['Stellungnahme.pdf', 'programm.exe']
    assert mail['date'].day == 10
    html_mail = email_import.parse_eml(sample_eml(html_only=True))
    assert 'Mängel zurück' in html_mail['body'] and 'x()' not in html_mail['body'] and '<p>' not in html_mail['body']
    assert email_import.pdf_name(mail) == 'E-Mail 2026-11-10 Ihre Mängelrüge vom 03.11.2026.pdf'


def test_not_a_mail_is_rejected():
    for data in (b'just some text', b''):
        try:
            email_import.parse_eml(data)
        except email_import.MailError:
            continue
        raise AssertionError('accepted non-mail')


class FakeOle:
    """Minimal stand-in for olefile.OleFileIO with the streams of an Outlook message."""
    def __init__(self, streams):
        self.streams = streams

    def exists(self, path):
        return path in self.streams or any(name.startswith(path + '/') for name in self.streams)

    def openstream(self, path):
        return io.BytesIO(self.streams['/'.join(path)])

    def listdir(self, streams=True, storages=False):
        return [name.split('/') for name in self.streams]


def test_read_msg_with_attachment_and_delivery_time():
    utf16 = lambda text: text.encode('utf-16-le')
    filetime = int((1793000000 + 11644473600) * 10_000_000)   # 2026-10-26 (UTC)
    properties = b'\0' * 32 + struct.pack('<IIQ', 0x0E060040, 0, filetime)
    ole = FakeOle({
        '__substg1.0_0037001F': utf16('Kündigung Mietvertrag'), '__substg1.0_0C1A001F': utf16('Erika Muster'),
        '__substg1.0_0C1F001F': utf16('erika@example.invalid'), '__substg1.0_0E04001F': utf16('Kanzlei'),
        '__substg1.0_1000001F': utf16('Anbei die Kündigung.\r\nGruß'), '__properties_version1.0': properties,
        '__attach_version1.0_#00000000/__substg1.0_3707001F': utf16('Kuendigung.pdf'),
        '__attach_version1.0_#00000000/__substg1.0_37010102': b'%PDF-1.4 x',
    })
    mail = email_import.read_msg(ole)
    assert mail['subject'] == 'Kündigung Mietvertrag'
    assert mail['sender'] == 'Erika Muster <erika@example.invalid>'
    assert mail['body'] == 'Anbei die Kündigung.\nGruß'
    assert mail['date'].year == 2026 and mail['date'].month == 10
    assert mail['attachments'] == [{'name': 'Kuendigung.pdf', 'data': b'%PDF-1.4 x'}]


def test_msg_that_is_not_ole_is_rejected():
    try:
        email_import.parse_msg(b'not an ole file')
    except email_import.MailError:
        return
    raise AssertionError('accepted non-OLE data')


class EmailImportTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_upload_eml_creates_pdf_and_allowed_attachments(self):
        with TestClient(api.app) as client:
            self.login(client, 'mailimport@example.invalid')
            case = client.post('/api/cases', json={'title': 'Werklohn', 'description': 'Synthetische Akte für den E-Mail-Import.'}).json()
            response = client.post(f"/api/cases/{case['id']}/documents", files={'file': ('Mängelrüge.eml', sample_eml(), 'message/rfc822')})
            self.assertEqual(response.status_code, 201, response.text)
            result = response.json()
            self.assertTrue(result['original_name'].startswith('E-Mail 2026-11-10'))
            self.assertEqual([item['original_name'] for item in result['extra_documents']], ['Stellungnahme.pdf'])
            self.assertEqual(result['skipped_attachments'], ['programm.exe'])
            pdf = client.get(f"/api/cases/{case['id']}/documents/{result['id']}/download")
            text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
            self.assertIn('Müller Bau GmbH', text)
            self.assertIn('nicht übernommen', text)
            names = [item['original_name'] for item in client.get(f"/api/cases/{case['id']}").json()['documents']]
            self.assertEqual(len(names), 2)
            bad = client.post(f"/api/cases/{case['id']}/documents", files={'file': ('kaputt.msg', b'no outlook file', 'application/vnd.ms-outlook')})
            self.assertEqual(bad.status_code, 422)
