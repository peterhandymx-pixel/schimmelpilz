import unittest
from datetime import date

from fastapi.testclient import TestClient

from server import app as api
from server import letter_assistant as la
from server.tests import test_inbox

MAHNBESCHEID = """Amtsgericht Coburg · Zentrales Mahngericht · 96450 Coburg
Herrn
Max Mustermann
Hauptstraße 5
80331 München

Geschäftszeichen: 26-1234567-0-3
Datum: 02.11.2026

Mahnbescheid
Der Antragsteller Beispiel Versand GmbH macht folgenden Anspruch geltend:
Hauptforderung 412,50 EUR
Gesamtbetrag 498,30 EUR
Sie können innerhalb von zwei Wochen Widerspruch erheben."""

KUENDIGUNG = """Muster Logistik GmbH · Industriestr. 3 · 90402 Nürnberg
Frau Erika Beispiel
Am Bach 2
90403 Nürnberg
Nürnberg, 30.10.2026
Kündigung Ihres Arbeitsverhältnisses
hiermit kündigen wir das mit Ihnen bestehende Arbeitsverhältnis ordentlich zum 31.12.2026."""

INKASSO = """Rasch Inkasso GmbH, Postfach 1, 20095 Hamburg
Forderungsnummer: RX-778812
Hamburg, den 20. Oktober 2026
Zahlungsaufforderung
im Auftrag unserer Mandantin fordern wir Sie auf, den offenen Betrag von 1.234,56 € bis zum 10.11.2026 zu zahlen."""


class ReadingTests(unittest.TestCase):
    def test_mahnbescheid_fields_and_kind(self):
        kind, _ = la.classify(MAHNBESCHEID)
        self.assertEqual(kind['id'], 'mahnbescheid')
        fields = la.read_fields(MAHNBESCHEID)
        self.assertEqual(fields['sender'], 'Amtsgericht Coburg')
        self.assertEqual(fields['letter_date'], '2026-11-02')
        self.assertEqual(fields['reference'], '26-1234567-0-3')
        self.assertEqual(fields['amount'], 498.30)
        self.assertEqual(fields['period']['amount'], 2)
        self.assertEqual(fields['period']['unit'], 'weeks')
        self.assertIn('Amtsgericht Coburg', fields['court'])
        self.assertEqual(fields['creditor'], 'Beispiel Versand GmbH')
        self.assertEqual(la.read_fields(INKASSO)['creditor'], '')
        self.assertEqual(la.read_fields('Rasch Inkasso GmbH, im Auftrag unserer Mandantin, der Muster Telekom AG, fordern wir Sie auf, 50,00 EUR zu zahlen.')['creditor'], 'Muster Telekom AG')

    def test_kinds_are_told_apart(self):
        self.assertEqual(la.classify(KUENDIGUNG)[0]['id'], 'kuendigung_arbeit')
        self.assertEqual(la.classify(INKASSO)[0]['id'], 'inkasso')
        self.assertEqual(la.classify('Vollstreckungsbescheid aufgrund des Mahnbescheids vom 1.9.2026')[0]['id'], 'vollstreckungsbescheid')
        self.assertEqual(la.classify('Abmahnung. Im Wiederholungsfall müssen Sie mit der Kündigung des Arbeitsverhältnisses rechnen.')[0]['id'], 'abmahnung_arbeit')
        self.assertEqual(la.classify('Finanzamt München – Bescheid für 2025 über Einkommensteuer')[0]['id'], 'steuerbescheid')
        bescheid = la.classify('Jobcenter Köln. Bescheid über Bürgergeld. Rechtsbehelfsbelehrung: Widerspruch innerhalb eines Monats')[0]
        self.assertEqual((bescheid['id'], bescheid['legal_area']), ('bescheid', 'social'))
        self.assertEqual(la.classify('Sehr geehrte Frau, wir laden Sie zum Sommerfest ein.')[0]['id'], 'sonstiges')

    def test_words_dates_and_deadline_in_letter(self):
        fields = la.read_fields(INKASSO)
        self.assertEqual((fields['letter_date'], fields['letter_deadline'], fields['amount'], fields['reference']), ('2026-10-20', '2026-11-10', 1234.56, 'RX-778812'))
        self.assertEqual(fields['sender'], 'Rasch Inkasso GmbH')


class ResultTests(unittest.TestCase):
    today = date(2026, 11, 4)

    def test_mahnbescheid_two_weeks_from_service(self):
        result = la.evaluate('mahnbescheid', la.read_fields(MAHNBESCHEID), {'received_on': '2026-11-04', 'owes': 'none'}, self.today)
        self.assertEqual(result['deadline']['date'], '2026-11-18')
        self.assertEqual(result['samples'], ['widerspruch-mahnbescheid'])
        self.assertEqual(result['urgency'], 'low' if result['deadline']['days_left'] > 14 else 'medium')
        paying = la.evaluate('mahnbescheid', {}, {'received_on': '2026-11-04', 'owes': 'all'}, self.today)
        self.assertEqual(paying['samples'], ['ratenzahlung'])

    def test_dismissal_three_weeks_and_report_within_three_days(self):
        result = la.evaluate('kuendigung_arbeit', {}, {'received_on': '2026-10-31', 'fight': 'yes', 'signed_by_boss': 'unsure', 'end_date': '2026-12-31'}, self.today)
        # 31.10.2026 + 3 weeks = Saturday 21.11.2026 -> Monday 23.11.2026 (§ 193 BGB).
        self.assertEqual(result['deadline']['date'], '2026-11-23')
        self.assertEqual(result['samples'][0], 'kschg-klage')
        self.assertIn('174-zurueckweisung', result['samples'])
        self.assertEqual(result['extra_deadlines'][0]['date'], '2026-11-03')

    def test_tax_notice_counts_from_fourth_day_after_posting(self):
        result = la.evaluate('steuerbescheid', {'letter_date': '2026-10-01'}, {'received_on': '2026-10-03', 'wrong': 'yes', 'must_pay': 'yes'}, self.today)
        # Bekanntgabe 05.10.2026, one month -> 05.11.2026.
        self.assertEqual(result['deadline']['date'], '2026-11-05')
        self.assertEqual(result['urgency'], 'high')
        self.assertIn('stundung-steuer', result['samples'])

    def test_rent_increase_until_end_of_second_month(self):
        result = la.evaluate('mieterhoehung', {}, {'received_on': '2026-11-03', 'justified': 'no'}, self.today)
        self.assertEqual(result['deadline']['date'], '2027-01-31')

    def test_notice_to_quit_hardship_two_months_before_end(self):
        result = la.evaluate('kuendigung_wohnung', {}, {'received_on': '2026-10-01', 'immediate': 'no', 'end_date': '2027-04-30', 'hardship': 'yes'}, self.today)
        self.assertEqual(result['deadline']['date'], '2027-02-28')

    def test_missing_instructions_give_one_year(self):
        result = la.evaluate('bescheid', {'letter_date': '2026-10-01'}, {'received_on': '2026-10-05', 'instructions': 'no'}, self.today)
        self.assertEqual(result['deadline']['date'], '2027-10-05')


class AssistantApiTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_analyze_and_evaluate(self):
        with TestClient(api.app) as client:
            self.login(client)
            analysis = client.post('/api/letter-assistant/analyze', json={'text': MAHNBESCHEID}).json()
            self.assertEqual(analysis['kind']['id'], 'mahnbescheid')
            self.assertEqual([q['id'] for q in analysis['questions']], ['received_on', 'owes'])
            result = client.post('/api/letter-assistant/evaluate', json={'kind': 'mahnbescheid', 'fields': analysis['fields'], 'answers': {'received_on': '2026-11-04', 'owes': 'part'}})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['deadline']['date'], '2026-11-18')
            self.assertEqual(client.post('/api/letter-assistant/evaluate', json={'kind': 'nix', 'fields': {}, 'answers': {}}).status_code, 422)
            self.assertEqual(client.post('/api/letter-assistant/evaluate', json={'kind': 'inkasso', 'fields': {'amount': 'viel'}, 'answers': {}}).status_code, 422)
            self.assertEqual(len(client.get('/api/letter-assistant/kinds').json()), len(la.KIND_IDS))


class NewKindsTests(unittest.TestCase):
    today = date(2026, 11, 4)

    def test_enforcement_and_business_letters_are_recognised(self):
        self.assertEqual(la.classify('Der Gerichtsvollzieher. Ladung zum Termin zur Abgabe der Vermögensauskunft, Vollstreckungsbescheid vom 1.9.2026')[0]['id'], 'gerichtsvollzieher')
        self.assertEqual(la.classify('Pfändungs- und Überweisungsbeschluss des Amtsgerichts')[0]['id'], 'pfaendung')
        self.assertEqual(la.classify('Finanzamt Nürnberg – Prüfungsanordnung nach § 196 AO')[0]['id'], 'betriebspruefung')
        self.assertEqual(la.classify('Hiermit kündige ich mein Arbeitsverhältnis fristgerecht zum 31.12.2026.')[0]['id'], 'eigenkuendigung')
        self.assertEqual(la.classify(KUENDIGUNG)[0]['id'], 'kuendigung_arbeit')

    def test_p_account_within_one_month(self):
        result = la.evaluate('pfaendung', {}, {'received_on': '2026-11-02', 'p_account': 'no', 'children': 'yes'}, self.today)
        self.assertEqual(result['deadline']['date'], '2026-12-02')
        self.assertIn('p-konto', result['samples'])
        self.assertEqual([item['id'] for item in result['help']], ['schuldnerberatung'])

    def test_state_holidays_move_the_deadline(self):
        # 01.10.2026 + 4 = 05.10.2026; one month -> 05.11.2026 (Thursday). Use a period ending on Allerheiligen instead:
        result = la.evaluate('mahnbescheid', {}, {'received_on': '2026-10-18', 'owes': 'none'}, self.today, state='BY')
        self.assertEqual(result['deadline']['date'], '2026-11-02')  # 01.11.2026 is a Sunday and Allerheiligen
        # 11.10.2027 + 3 weeks = Monday 01.11.2027: a working day nationwide, Allerheiligen in Bavaria.
        nationwide = la.evaluate('kuendigung_arbeit', {}, {'received_on': '2027-10-11'}, self.today)
        bavaria = la.evaluate('kuendigung_arbeit', {}, {'received_on': '2027-10-11'}, self.today, state='BY')
        self.assertEqual(nationwide['deadline']['date'], '2027-11-01')
        self.assertEqual(bavaria['deadline']['date'], '2027-11-02')
        self.assertIn('Allerheiligen', bavaria['deadline']['basis'])
        reformation = la.evaluate('kuendigung_arbeit', {}, {'received_on': '2026-10-10'}, self.today, state='SN')
        self.assertEqual(reformation['deadline']['date'], '2026-11-02')  # 31.10.2026 Saturday + Reformationstag
        self.assertIn('Sachsen', reformation['disclaimer'])

    def test_lawyer_cases_offer_legal_aid(self):
        result = la.evaluate('strafbefehl', {}, {'received_on': '2026-11-02'}, self.today)
        self.assertEqual(result['help'][0]['id'], 'beratungshilfe')

    def test_rent_arrears_letter_reads_remaining_amount_and_relative_deadline(self):
        letter = """Beispiel Vermietung GmbH, Vermieterweg 5, 10117 Berlin
Berlin, 02.11.2026
Betreff: Ihre Mängelanzeige / Mietrückstand
die Miete für Oktober 2026 in Höhe von 900,00 EUR wurde nur zu 700,00 EUR gezahlt.
Bitte überweisen Sie den Restbetrag von 200,00 EUR innerhalb von 14 Tagen nach Zugang dieses Schreibens."""
        fields = la.read_fields(letter)
        self.assertEqual(fields['amount'], 200.0)
        self.assertEqual(fields['period']['amount'], 14)
        self.assertEqual(la.classify(letter)[0]['id'], 'zahlungsaufforderung')
        result = la.evaluate('zahlungsaufforderung', fields, {'received_on': '2026-11-04', 'owes': 'none'}, self.today)
        self.assertEqual(result['deadline']['date'], '2026-11-18')
        self.assertIn('forderung-zurueckweisen', result['samples'])


class MoveLetterTests(test_inbox.InboxTests):
    test_unassigned_persistence_then_exact_file_and_text_review_in_case = None
    test_ownership_validation_stale_updates_and_single_assignment = None
    test_rejected_uploads_leave_no_files_and_auth_guard_applies = None
    test_atomic_assignment_rollback_and_failed_upload_cleanup = None
    test_correction_guards_and_atomic_rollback = None
    test_correction_preserves_snapshots_blocks_old_sources_and_can_assign_back = None

    def test_uploaded_letter_moves_into_existing_case_and_provisional_case_is_archived(self):
        from server.tests.test_document_research import synthetic_pdf
        with TestClient(api.app) as client:
            self.login(client, 'move-letter@example.invalid')
            existing = self.case(client)
            provisional = client.post('/api/cases', json={'title': la.PROVISIONAL_TITLES[0], 'description': 'Only synthetic testing, no real client data.'}).json()['id']
            document = client.post(f'/api/cases/{provisional}/documents', files={'file': ('Brief.pdf', synthetic_pdf(), 'application/pdf')}).json()
            moved = client.post('/api/letter-assistant/move-letter', json={'from_case_id': provisional, 'document_id': document['id'], 'to_case_id': existing})
            self.assertEqual(moved.status_code, 200, moved.text)
            self.assertIn(document['id'], [item['id'] for item in moved.json()['documents']])
            self.assertTrue(client.get(f'/api/cases/{provisional}').json()['archived_at'])
            self.assertEqual(client.get(f'/api/cases/{existing}/documents/{document["id"]}/text').status_code, 200)
            # The same letter cannot be moved twice, and a case with own content is never archived.
            again = client.post('/api/letter-assistant/move-letter', json={'from_case_id': provisional, 'document_id': document['id'], 'to_case_id': existing})
            self.assertEqual(again.status_code, 404)
            busy = client.post('/api/cases', json={'title': la.PROVISIONAL_TITLES[0], 'description': 'Only synthetic testing, no real client data.'}).json()['id']
            first = client.post(f'/api/cases/{busy}/documents', files={'file': ('A.pdf', synthetic_pdf(), 'application/pdf')}).json()
            client.post(f'/api/cases/{busy}/documents', files={'file': ('B.pdf', synthetic_pdf(), 'application/pdf')})
            client.post('/api/letter-assistant/move-letter', json={'from_case_id': busy, 'document_id': first['id'], 'to_case_id': existing})
            self.assertFalse(client.get(f'/api/cases/{busy}').json()['archived_at'])
            self.login(client, 'other-move@example.invalid')
            self.assertEqual(client.post('/api/letter-assistant/move-letter', json={'from_case_id': busy, 'document_id': first['id'], 'to_case_id': existing}).status_code, 404)
