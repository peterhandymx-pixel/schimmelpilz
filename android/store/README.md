# Google-Play-Eintrag

Alles für die Play Console an einem Ort. Texte zum Hineinkopieren, Grafiken in diesem Ordner.

| Datei | Verwendung in der Play Console |
|---|---|
| `icon-512.png` | App-Symbol (512 × 512) |
| `feature-graphic-1024x500.png` | Vorschaugrafik (1024 × 500) |
| `de/phone-01 … 06.png` | Smartphone-Screenshots (1080 × 1920), deutsche Oberfläche mit Demodaten |

Die Screenshots zeigen synthetische Demodaten. Die Antwort im zweiten und dritten Bild ist ein
Demo-Eintrag, keine Ausgabe des KI-Modells; die Gesetzestexte (§ 536, § 536c BGB) sind echt.
Neu erzeugen: `ScreenshotTest` (siehe `android/README.md`), dann die Rahmen wie hier gestalten.

## Store-Texte – Deutsch (Standardsprache)

**App-Name** (max. 30 Zeichen, hier 30):

```
Rechtsassistentin Schimmelpilz
```

**Kurzbeschreibung** (max. 80 Zeichen):

```
Rechtsfragen stellen, Antworten mit Gesetzen – Akten, Fristen, Post im Griff.
```

**Vollständige Beschreibung** (max. 4000 Zeichen):

```
Recht verstehen. Einfach fragen.

Rechtsassistentin Schimmelpilz beantwortet Ihre Rechtsfrage in eigenen Worten – und zeigt die Gesetze, auf die sich die Antwort stützt. Entwickelt von einem ausgebildeten Rechtsanwaltsfachangestellten.

FRAGEN STATT SUCHEN
• Frage zu einer Akte stellen, Antwort mit Quellenangaben erhalten
• Jede Quelle antippen und den Wortlaut des Gesetzes direkt lesen
• Antwort kopieren, teilen oder als PDF bzw. Word-Datei weitergeben

AKTEN, POST UND FRISTEN UNTERWEGS
• Alle Akten mit Beteiligten, Dokumenten, Entwürfen und Fristen
• Briefe mit der Kamera scannen und als PDF in den Posteingang legen
• Eingänge nur auf Ihre ausdrückliche Bestätigung einer Akte zuordnen
• Fristen und Aufgaben nach Fälligkeit, überfällige Fristen hervorgehoben
• Deutsches Datumsformat, Oberfläche auf Deutsch und Englisch, heller und dunkler Modus

IHRE DATEN BLEIBEN BEI IHREM SERVER
Die App verbindet sich mit dem Schimmelpilz-Server Ihrer Kanzlei bzw. Ihres Anbieters. Die KI läuft auf diesem Server; Fragen und Dokumente werden nicht an fremde KI-Dienste geschickt. Ihr Konto können Sie jederzeit in der App löschen.

FÜR WEN
Für Kanzleien, Unternehmen und Privatpersonen, die bereits ein Schimmelpilz-Konto haben oder eines in der Web-App anlegen. Weitere Module wie Kostenprüfung, Verfahrenswege, Briefpapier und Teamrechte öffnen sich in der Web-App mit demselben Konto.

WICHTIGER HINWEIS
Schimmelpilz liefert allgemeine Rechtsinformationen, keine anwaltliche Beratung im Einzelfall. Prüfen Sie Antworten und Fristen selbst oder lassen Sie sie von einer Anwältin, einem Anwalt oder einer Beratungsstelle prüfen.
```

## Store texts – English

**App name:** `Rechtsassistentin Schimmelpilz` (brand name, not translated)

**Short description** (max. 80):

```
Ask legal questions, get answers with statutes – cases, deadlines, mail.
```

**Full description:**

```
Understand the law. Just ask.

Rechtsassistentin Schimmelpilz answers your legal question in your own words – and shows the statutes the answer relies on. Developed by a trained German paralegal.

ASK INSTEAD OF SEARCHING
• Ask a question about a case and get an answer with sources
• Tap any source to read the statute's exact wording
• Copy or share the answer, or pass it on as a PDF or Word file

CASES, MAIL AND DEADLINES ON THE GO
• All cases with parties, documents, drafts and deadlines
• Scan letters with the camera and add them to the inbox as PDF
• Assign incoming items to a case only after your explicit confirmation
• Deadlines and tasks by due date, overdue items highlighted
• German and English interface, light and dark mode

YOUR DATA STAYS WITH YOUR SERVER
The app connects to the Schimmelpilz server of your firm or provider. The AI runs on that server; questions and documents are not sent to third-party AI services. You can delete your account in the app at any time.

WHO IT IS FOR
Law firms, businesses and individuals with a Schimmelpilz account (created in the web app). Further modules such as cost review, procedural routes, letter paper and team permissions open in the web app with the same account.

IMPORTANT
Schimmelpilz provides general legal information, not individual legal advice. Check answers and deadlines yourself or have them checked by a lawyer or advice centre.
```

## Datensicherheit (Formular „Data safety“) – Vorlage

Stand des Codes in diesem Repository. Vor dem Absenden mit dem tatsächlichen Serverbetrieb
(Hosting, E-Mail-Anbieter, Zahlungsanbieter) und der Datenschutzerklärung abgleichen.

| Frage | Antwort |
|---|---|
| Werden Daten erhoben oder geteilt? | Ja, erhoben. Nicht an Dritte geteilt (Übertragung nur an den eigenen Server des Betreibers). |
| Verschlüsselung bei der Übertragung | Ja – Release-Builds erlauben nur HTTPS. |
| Löschung auf Anfrage möglich | Ja – in der App unter Mehr → Konto löschen und in der Web-App unter Kanzlei / Profil. |
| Persönliche Angaben | Name, E-Mail-Adresse; bei Registrierung im Web zusätzlich Anschrift und Telefon (optional). Zweck: Kontoverwaltung, App-Funktionen. |
| Dateien und Dokumente | Hochgeladene und gescannte Dokumente. Zweck: App-Funktionen. |
| Nachrichten / sonstige Inhalte | Rechtsfragen und Antworten, Fristen, Aufgaben, Kontakte. Zweck: App-Funktionen. |
| Finanzdaten | Nicht in der App. Bezahlt wird in der Web-App über Clip-Zahlungslinks. |
| Standort, Kontakte des Geräts, Fotos-Mediathek | Nein. Der Dokumentenscanner (Google Play Services) gibt nur das fertige PDF an die App. |
| App-Aktivität, Absturzberichte, Werbe-ID | Keine eigenen Analyse-, Absturz- oder Werbe-SDKs. Der ML-Kit-Dokumentenscanner von Google kann Diagnosedaten an Google senden – vor dem Absenden mit Googles Angaben „ML Kit – Data disclosure“ abgleichen. |

**Weitere Pflichtangaben in der Play Console**

- **Datenschutzerklärung (URL):** Seite des Betreibers, z. B. `https://<ihre-domain>/datenschutz`.
- **Kontolöschung (URL außerhalb der App):** Web-App, Anmeldung → Kanzlei / Profil → Konto löschen,
  z. B. `https://<ihre-domain>/`; Hinweis in der Console: „Anmelden, Kanzlei / Profil, Konto löschen“.
- **Inhaltseinstufung (IARC):** Das Logo zeigt eine Comic-Szene, in der eine Anwältin eine Justitia-Statue
  am Hals packt. Im Fragebogen bei Gewalt „comicartige/unrealistische Gewalt gegen nicht-menschliche
  Figur“ angeben; Ergebnis erfahrungsgemäß USK 6 / PEGI 7 – maßgeblich ist der Fragebogen.
- **Zielgruppe:** ab 18 Jahren (rechtliche Inhalte, Kontoanlage). Keine Inhalte für Kinder.
- **Zugang für die Prüfung:** Die App braucht ein Konto. In „App-Zugriff“ ein Demo-Konto mit E-Mail
  und Passwort hinterlegen (ohne Zwei-Faktor-Anmeldung).
- **Kategorie:** Business (alternativ: Produktivität).
