import { useEffect, useState } from "react";
import { IconArrowLeft } from "@tabler/icons-react";
import { BrandLogo } from "./BrandLogo.jsx";
import { API_BASE } from "./useCaseStorage.js";
import "./legal.css";

export const LEGAL_PAGES = ["impressum", "datenschutz", "agb"];
const STAND = "24.10.2026";

export function legalPageFromHash(hash = window.location.hash) {
  return LEGAL_PAGES.find(page => hash === "#" + page) || null;
}

const titles = {
  de: { impressum: "Impressum", datenschutz: "Datenschutzerklärung", agb: "Nutzungsbedingungen (AGB)" },
  en: { impressum: "Legal notice (Impressum)", datenschutz: "Privacy notice", agb: "Terms of use" },
};

export function LegalLinks({ lang, newTab = false }) {
  const extra = newTab ? { target: "_blank", rel: "noreferrer" } : {};
  return <>{LEGAL_PAGES.map(page => <a key={page} href={(newTab ? "/" : "") + "#" + page} {...extra}>{titles[lang][page]}</a>)}</>;
}

// Operator particulars come from the server's configuration; missing values are shown as missing, never invented.
function useOperator() {
  const [operator, setOperator] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    fetch(`${API_BASE}/api/public/operator`, { signal: abort.signal }).then(response => { if (!response.ok) throw new Error("operator"); return response.json(); }).then(setOperator).catch(error => { if (error.name !== "AbortError") setFailed(true); });
    return () => abort.abort();
  }, []);
  return { operator, failed };
}

function Missing({ de }) { return <span className="legal-missing">{de ? "[Angabe fehlt]" : "[not provided]"}</span>; }

function OperatorBlock({ operator, de }) {
  return <address className="legal-address">
    <strong>{operator.name || <Missing de={de} />}</strong>{operator.legal_form && <> ({operator.legal_form})</>}<br />
    {operator.address.length ? operator.address.map(line => <span key={line}>{line}<br /></span>) : <><Missing de={de} /><br /></>}
    {operator.email ? <a href={"mailto:" + operator.email}>{operator.email}</a> : <Missing de={de} />}
    {operator.phone && <><br />{de ? "Telefon" : "Phone"}: {operator.phone}</>}
  </address>;
}

function Impressum({ operator, de }) {
  const responsible = operator.content_responsible || operator.representative || operator.name;
  return <>
    <h2>{de ? "Angaben gemäß § 5 DDG" : "Information pursuant to § 5 DDG (German Digital Services Act)"}</h2>
    <OperatorBlock operator={operator} de={de} />
    {operator.representative && <p>{de ? "Vertreten durch" : "Represented by"}: {operator.representative}</p>}
    {operator.register && <p>{de ? "Registereintrag" : "Register entry"}: {operator.register}</p>}
    {operator.tax_id && <p>{de ? "Umsatzsteuer-Identifikationsnummer / Steuernummer" : "VAT / tax identification number"}: {operator.tax_id}</p>}
    <h2>{de ? "Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV" : "Responsible for content under § 18(2) MStV"}</h2>
    <p>{responsible || <Missing de={de} />}{operator.address.length > 0 && <>, {operator.address.join(", ")}</>}</p>
    <h2>{de ? "Verbraucherstreitbeilegung" : "Consumer dispute resolution"}</h2>
    <p>{de ? "Wir sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen." : "We are neither willing nor obliged to take part in dispute resolution proceedings before a consumer arbitration board."}</p>
    <h2>{de ? "Hinweis zur Nutzung" : "Note on use"}</h2>
    <p>{de ? "Die Rechtsassistentin Schimmelpilz ist eine Software zur Aktenorganisation, Recherche und Entwurfsvorbereitung. Sie erbringt keine Rechtsberatung und ersetzt nicht die Beratung durch eine zugelassene Rechtsanwältin oder einen zugelassenen Rechtsanwalt. Ergebnisse, insbesondere KI-Antworten, sind vor jeder Verwendung selbst zu prüfen." : "Rechtsassistentin Schimmelpilz is software for organising case files, research and preparing drafts. It does not provide legal advice and does not replace advice from a qualified lawyer. Results, in particular AI answers, must be checked before any use."}</p>
  </>;
}

function Privacy({ operator, de }) {
  const gemini = !["ollama", "groq", "openai"].includes(operator.ai_provider), groq = operator.ai_provider === "groq", other = operator.ai_provider === "openai";
  const hosting = operator.hosting || (de ? "unseren Hosting-Anbieter" : "our hosting provider");
  return <>
    <h2>{de ? "1. Verantwortlicher" : "1. Controller"}</h2>
    <OperatorBlock operator={operator} de={de} />
    <h2>{de ? "2. Welche Daten wir verarbeiten" : "2. Data we process"}</h2>
    <ul>
      <li>{de ? "Kontodaten: Name, E-Mail-Adresse, Anschrift, Kontotyp und freiwillige Organisations- und Berufsangaben, Passwort (nur als Hash), Einstellungen zur Zwei-Faktor-Anmeldung." : "Account data: name, email address, postal address, account type and optional organisation and professional details, password (hashed only), two-factor sign-in settings."}</li>
      <li>{de ? "Inhalte, die Sie speichern: Akten, Beteiligte, Kontakte, Dokumente und deren Textauszüge, Entwürfe, Aufgaben, Fristen, Kostenprüfungen und Rechercheverläufe. Diese können Daten Dritter und besondere Kategorien personenbezogener Daten enthalten; welche Inhalte Sie hochladen, entscheiden Sie." : "Content you store: case files, parties, contacts, documents and their text extracts, drafts, tasks, deadlines, cost reviews and research history. These may include data about third parties and special categories of personal data; you decide what you upload."}</li>
      <li>{de ? "Protokolle: Anmeldungen, Sitzungen und sicherheitsrelevante Aktionen (z. B. Freigaben, Löschungen, Administratorzugriffe) mit Zeitpunkt." : "Logs: sign-ins, sessions and security-relevant actions (e.g. access grants, deletions, administrator access) with time."}</li>
      <li>{de ? "Zahlungsdaten: gewählter Tarif, Betrag, Zahlungsdatum, bezahlter Zeitraum und die Clip-Transaktionsnummer. Karten- und Bankdaten erhalten wir nicht; diese gibt es nur bei Clip." : "Payment data: chosen plan, amount, payment date, paid period and the Clip transaction number. We do not receive card or bank details; those stay with Clip."}</li>
      <li>{de ? "Technisch notwendige Verbindungsdaten (z. B. IP-Adresse, Zeitpunkt) zur Auslieferung der Seite und zur Abwehr von Missbrauch, etwa zur Begrenzung von Anmeldeversuchen." : "Technically necessary connection data (e.g. IP address, time) to deliver the site and prevent abuse, such as limiting sign-in attempts."}</li>
    </ul>
    <h2>{de ? "3. Zwecke und Rechtsgrundlagen" : "3. Purposes and legal bases"}</h2>
    <ul>
      <li>{de ? "Bereitstellung des Kontos und der Funktionen, einschließlich KI-Recherche, Zahlungen und E-Mail-Benachrichtigungen: Art. 6 Abs. 1 lit. b DSGVO (Vertrag)." : "Providing your account and the features, including AI research, payments and email notifications: Art. 6(1)(b) GDPR (contract)."}</li>
      <li>{de ? "Aufbewahrung von Zahlungsbelegen: Art. 6 Abs. 1 lit. c DSGVO in Verbindung mit handels- und steuerrechtlichen Aufbewahrungspflichten." : "Retaining payment records: Art. 6(1)(c) GDPR together with commercial and tax retention duties."}</li>
      <li>{de ? "Sicherheit, Missbrauchsabwehr und Sicherungskopien: Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an einem sicheren Betrieb)." : "Security, abuse prevention and backups: Art. 6(1)(f) GDPR (legitimate interest in secure operation)."}</li>
      <li>{de ? "Speichern Sie Daten Dritter (z. B. Mandanten oder Gegner), sind Sie für deren Rechtsgrundlage verantwortlich. Für Kanzleien und Unternehmen schließen wir auf Anfrage einen Vertrag zur Auftragsverarbeitung nach Art. 28 DSGVO." : "If you store data about third parties (e.g. clients or opponents), you are responsible for its legal basis. For law firms and businesses we conclude a data processing agreement under Art. 28 GDPR on request."}</li>
    </ul>
    <h2>{de ? "4. Empfänger und Übermittlungen" : "4. Recipients and transfers"}</h2>
    <ul>
      <li>{de ? `Hosting: Alle Daten werden auf einem Server bei ${hosting} gespeichert, der uns als Auftragsverarbeiter dient.` : `Hosting: all data is stored on a server at ${hosting}, acting as our processor.`}</li>
      {gemini && <li>{de ? "KI-Recherche: Wenn Sie eine Recherchefrage stellen, werden die Frage, der bisherige Verlauf, die Aktenangaben der gewählten Akte, die von Ihnen ausgewählten Dokumentauszüge und die gefundenen Rechtsquellen an Google (Gemini API) übermittelt und dort zur Beantwortung verarbeitet. Wir nutzen den kostenpflichtigen Dienst, bei dem Google die Inhalte nach eigenen Angaben nicht zum Training verwendet. Dabei kann eine Übermittlung in die USA stattfinden; Google LLC ist nach dem EU-US Data Privacy Framework zertifiziert. Ohne Recherchefrage wird nichts an Google übermittelt." : "AI research: when you ask a research question, the question, the conversation so far, the selected case's particulars, the document excerpts you select and the legal sources found are sent to Google (Gemini API) and processed there to answer it. We use the paid service, under which Google states it does not use the content for training. This may involve a transfer to the USA; Google LLC is certified under the EU-US Data Privacy Framework. Nothing is sent to Google unless you ask a research question."}</li>}
      {other && <li>{de ? `KI-Recherche: Wenn Sie eine Recherchefrage stellen, werden die Frage, der bisherige Verlauf, die Aktenangaben der gewählten Akte, die von Ihnen ausgewählten Dokumentauszüge und die gefundenen Rechtsquellen an den KI-Dienst ${operator.ai_host || "des Betreibers"} übermittelt und dort zur Beantwortung verarbeitet. Je nach Anbieter kann eine Übermittlung in Drittländer stattfinden. Ohne Recherchefrage wird nichts übermittelt.` : `AI research: when you ask a research question, the question, the previous conversation, the particulars of the selected case, the document excerpts you selected and the legal sources found are sent to the AI service ${operator.ai_host || "chosen by the operator"} and processed there. Depending on the provider, this may involve a transfer to third countries. Nothing is sent unless you ask a research question.`}</li>}
      {groq && <li>{de ? "KI-Recherche: Wenn Sie eine Recherchefrage stellen, werden die Frage, der bisherige Verlauf, die Aktenangaben der gewählten Akte, die von Ihnen ausgewählten Dokumentauszüge und die gefundenen Rechtsquellen an Groq, Inc. (GroqCloud) übermittelt und dort zur Beantwortung verarbeitet. Dabei findet eine Übermittlung in die USA statt." : "AI research: when you ask a research question, the question, the previous conversation, the particulars of the selected case, the document excerpts you selected and the legal sources found are sent to Groq, Inc. (GroqCloud) and processed there to answer it. This involves a transfer to the USA."}</li>}
      <li>{de ? "Rechtsprechung und Zitatprüfung: Um passende Gerichtsentscheidungen zu finden und Zitate in KI-Antworten zu prüfen, fragen wir den kostenlosen Dienst nu:legal Deutsches Recht (Nulegal GmbH, Potsdam) ab. Dorthin gehen nur Suchbegriffe aus Gesetzesüberschriften und festen Fachbegriffen sowie die in einer Antwort genannten Paragrafen und Aktenzeichen – keine Namen, keine Sachverhalte und kein Brieftext." : "Case law and citation check: to find relevant court decisions and check citations in AI answers, we query the free service nu:legal Deutsches Recht (Nulegal GmbH, Potsdam). Only search terms taken from statute headings and fixed legal terms, and the sections and docket numbers named in an answer, are sent – no names, no facts and no letter text."}</li>
      <li>{de ? "Zahlungen: Bezahlen Sie einen Zugang, geben Sie Ihre Zahlungsdaten direkt auf der Seite von Clip ein (PayClip, S. de R.L. de C.V., Mexiko). Clip verarbeitet diese Daten in eigener Verantwortung nach seiner Datenschutzerklärung. Die Übermittlung nach Mexiko ist für die von Ihnen gewünschte Zahlung erforderlich (Art. 49 Abs. 1 lit. b DSGVO); für Mexiko besteht kein Angemessenheitsbeschluss der EU-Kommission." : "Payments: when you pay for access, you enter your payment details directly on Clip's page (PayClip, S. de R.L. de C.V., Mexico). Clip processes this data under its own responsibility and privacy policy. The transfer to Mexico is necessary for the payment you request (Art. 49(1)(b) GDPR); there is no EU adequacy decision for Mexico."}</li>
      <li>{de ? `E-Mail: Konto-E-Mails (z. B. Passwort zurücksetzen) und Entwürfe, die Sie ausdrücklich versenden, werden über ${operator.mail_provider || "unseren E-Mail-Versanddienst"} zugestellt.` : `Email: account emails (e.g. password reset) and drafts you explicitly send are delivered through ${operator.mail_provider || "our email delivery service"}.`}</li>
      <li>{de ? "Öffentliche Rechtsquellen werden von gesetze-im-internet.de und rechtsprechung-im-internet.de abgerufen; dabei werden keine Akteninhalte übermittelt. Richten Sie einen E-Mail-Import ein, ruft der Server Ihr eigenes Postfach ab." : "Public legal sources are fetched from gesetze-im-internet.de and rechtsprechung-im-internet.de without sending any case content. If you set up email import, the server fetches your own mailbox."}</li>
    </ul>
    <h2>{de ? "5. Speicherdauer" : "5. Retention"}</h2>
    <p>{de ? "Ihre Daten bleiben gespeichert, bis Sie sie oder Ihr Konto löschen; die Löschfunktionen finden Sie im Profil und in jeder Akte. Zahlungsbelege bewahren wir für die gesetzlichen Fristen auf (bis zu zehn Jahre), auch nach einer Kontolöschung. Verschlüsselte Sicherungskopien werden nach Ablauf ihrer Aufbewahrungszeit gelöscht; bis dahin können gelöschte Daten darin noch enthalten sein." : "Your data is kept until you delete it or your account; the deletion functions are in your profile and in each case file. We keep payment records for the statutory periods (up to ten years), including after account deletion. Encrypted backups are deleted when their retention period ends; until then they may still contain deleted data."}</p>
    <h2>{de ? "6. Cookies und lokale Speicherung" : "6. Cookies and local storage"}</h2>
    <p>{de ? "Wir verwenden nur technisch notwendige Speicherungen: ein Sitzungscookie für die Anmeldung, ein Cookie für den gewählten Arbeitsbereich sowie Ihre Spracheinstellung im Browser (§ 25 Abs. 2 TDDDG). Es gibt keine Analyse-, Tracking- oder Werbedienste und keine Inhalte von Drittservern; Schriften werden von unserem Server geladen." : "We only use technically necessary storage: a session cookie for sign-in, a cookie for the selected workspace and your language setting in the browser (§ 25(2) TDDDG). There are no analytics, tracking or advertising services and no content from third-party servers; fonts are served from our own server."}</p>
    <h2>{de ? "7. Ihre Rechte" : "7. Your rights"}</h2>
    <p>{de ? "Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit (die Exportfunktionen liefern Ihre Daten als Dateien) und Widerspruch gegen Verarbeitungen auf Grundlage berechtigter Interessen. Wenden Sie sich dazu an die oben genannte E-Mail-Adresse. Sie können sich außerdem bei einer Datenschutz-Aufsichtsbehörde beschweren, insbesondere in dem Mitgliedstaat Ihres Aufenthalts oder Arbeitsplatzes." : "You have the right of access, rectification, erasure, restriction of processing, data portability (the export functions provide your data as files) and to object to processing based on legitimate interests. Contact us at the email address above. You may also complain to a data protection supervisory authority, in particular in the member state where you live or work."}</p>
    <h2>{de ? "8. Keine automatisierten Entscheidungen" : "8. No automated decisions"}</h2>
    <p>{de ? "KI-Antworten sind Vorschläge zur Orientierung. Es findet keine automatisierte Entscheidung im Sinne von Art. 22 DSGVO statt." : "AI answers are suggestions for orientation. There is no automated decision-making within the meaning of Art. 22 GDPR."}</p>
  </>;
}

function Terms({ operator, de }) {
  const name = operator.name || (de ? "der Anbieter" : "the provider");
  return <>
    <h2>{de ? "1. Geltungsbereich" : "1. Scope"}</h2>
    <p>{de ? `Diese Bedingungen gelten für die Nutzung der Rechtsassistentin Schimmelpilz, angeboten von ${name} (Anbieterangaben im Impressum).` : `These terms apply to the use of Rechtsassistentin Schimmelpilz, offered by ${name} (provider details in the legal notice).`}</p>
    <h2>{de ? "2. Leistungen" : "2. Services"}</h2>
    <p>{de ? "Die Software unterstützt bei der Organisation von Akten und Unterlagen, bei der Recherche in öffentlichen Rechtsquellen, mit einem KI-Assistenten und bei der Vorbereitung bearbeitbarer Entwürfe. Sie erbringt keine Rechtsdienstleistung, prüft keine Rechtslage verbindlich und ersetzt keine anwaltliche Beratung. KI-Antworten können unvollständig oder falsch sein; Sie prüfen Ergebnisse, Fristen und Quellen vor jeder Verwendung selbst. Der E-Mail-Versand von Entwürfen ist keine Einreichung bei Gericht oder Behörden." : "The software helps organise case files and documents, research public legal sources with an AI assistant and prepare editable drafts. It does not provide legal services, does not give binding assessments of the law and does not replace advice from a lawyer. AI answers may be incomplete or wrong; you check results, deadlines and sources yourself before any use. Emailing drafts is not filing with a court or authority."}</p>
    <h2>{de ? "3. Konto" : "3. Account"}</h2>
    <p>{de ? "Ihre Angaben bei der Registrierung müssen zutreffen. Halten Sie Ihre Zugangsdaten geheim und nutzen Sie die Zwei-Faktor-Anmeldung. Teammitglieder erhalten eigene Zugänge; für deren Rechte in Ihrem Arbeitsbereich sind Sie verantwortlich." : "The details you give at registration must be accurate. Keep your credentials secret and use two-factor sign-in. Team members receive their own logins; you are responsible for their rights in your workspace."}</p>
    <h2>{de ? "4. Testzugang, Preise und Zahlung" : "4. Trial, prices and payment"}</h2>
    <p>{de ? "Der Testzugang beginnt mit der Registrierung, läuft sieben Tage und endet automatisch, ohne in einen bezahlten Zugang überzugehen. Bezahlte Zugänge werden jeweils für einen Monat im Voraus über einen Zahlungslink von Clip bezahlt; es gelten die bei der Zahlung angezeigten Endpreise einschließlich anfallender Steuern. Der bezahlte Zeitraum beginnt mit der Bestätigung Ihrer Zahlung, frühestens mit dem Ende eines laufenden Zeitraums. Es gibt keine automatische Verlängerung. Nach Ablauf bleiben Lesen, Herunterladen, Export und Löschen Ihrer Daten möglich." : "The trial starts at registration, runs for seven days and ends automatically without turning into paid access. Paid access is paid one month in advance at a time through a Clip payment link, at the final prices shown at payment, including applicable taxes. The paid period starts when your payment is confirmed, at the earliest when a running period ends. Nothing renews automatically. After expiry you can still read, download, export and delete your data."}</p>
    <h2>{de ? "5. Widerrufsrecht für Verbraucher" : "5. Right of withdrawal for consumers"}</h2>
    <p>{de ? "Verbraucher können einen bezahlten Monat binnen 14 Tagen ab Vertragsschluss ohne Angabe von Gründen widerrufen. Zur Ausübung genügt eine eindeutige Erklärung (z. B. per E-Mail) an die im Impressum genannte Adresse; die rechtzeitige Absendung wahrt die Frist. Im Fall des Widerrufs erstatten wir alle Zahlungen unverzüglich, spätestens binnen 14 Tagen, über dasselbe Zahlungsmittel. Haben Sie verlangt, dass der bezahlte Zugang während der Widerrufsfrist beginnt, zahlen Sie einen angemessenen Betrag für den bis zum Widerruf bereitgestellten Anteil." : "Consumers may withdraw from a paid month within 14 days of conclusion of the contract without giving reasons. A clear statement (e.g. by email) to the address in the legal notice is sufficient; sending it in time meets the deadline. If you withdraw, we refund all payments without delay and within 14 days at the latest, using the same means of payment. If you requested that paid access start during the withdrawal period, you pay a reasonable amount for the share provided until withdrawal."}</p>
    <h2>{de ? "6. Ihre Pflichten" : "6. Your obligations"}</h2>
    <p>{de ? "Sie speichern nur Inhalte, zu deren Verarbeitung Sie berechtigt sind, und nutzen die Software nicht rechtswidrig oder so, dass ihr Betrieb gestört wird. Berufsrechtliche Pflichten, etwa die Verschwiegenheit, bleiben Ihre Verantwortung." : "You only store content you are entitled to process and do not use the software unlawfully or in a way that disrupts its operation. Professional duties, such as confidentiality, remain your responsibility."}</p>
    <h2>{de ? "7. Verfügbarkeit" : "7. Availability"}</h2>
    <p>{de ? "Wir bemühen uns um einen störungsfreien Betrieb, können aber keine ununterbrochene Verfügbarkeit zusagen, insbesondere bei Wartung oder Ausfällen von Drittdiensten wie der KI-Recherche." : "We aim for uninterrupted operation but cannot promise constant availability, especially during maintenance or outages of third-party services such as AI research."}</p>
    <h2>{de ? "8. Haftung" : "8. Liability"}</h2>
    <p>{de ? "Wir haften unbeschränkt bei Vorsatz und grober Fahrlässigkeit, bei Verletzung von Leben, Körper oder Gesundheit und nach dem Produkthaftungsgesetz. Bei leichter Fahrlässigkeit haften wir nur für die Verletzung wesentlicher Vertragspflichten und begrenzt auf den vorhersehbaren, vertragstypischen Schaden. Im Übrigen ist die Haftung ausgeschlossen." : "We are liable without limitation for intent and gross negligence, for injury to life, body or health and under the Product Liability Act. For slight negligence we are only liable for breach of essential contractual obligations, limited to foreseeable damage typical for the contract. Otherwise liability is excluded."}</p>
    <h2>{de ? "9. Laufzeit und Kündigung" : "9. Term and termination"}</h2>
    <p>{de ? "Sie können Ihr Konto jederzeit im Profil löschen. Wir können den Vertrag aus wichtigem Grund kündigen, etwa bei schwerem Missbrauch; zuvor erhalten Sie, soweit zumutbar, Gelegenheit zum Export Ihrer Daten." : "You can delete your account at any time in your profile. We may terminate for good cause, such as serious misuse; where reasonable, you will first be given the opportunity to export your data."}</p>
    <h2>{de ? "10. Änderungen" : "10. Changes"}</h2>
    <p>{de ? "Änderungen dieser Bedingungen teilen wir Ihnen per E-Mail mit. Für bereits bezahlte Zeiträume gelten die bei der Zahlung gültigen Bedingungen." : "We notify you of changes to these terms by email. Periods already paid for remain under the terms valid at payment."}</p>
    <h2>{de ? "11. Schlussbestimmungen" : "11. Final provisions"}</h2>
    <p>{de ? "Es gilt deutsches Recht unter Ausschluss des UN-Kaufrechts. Für Verbraucher bleiben zwingende Schutzvorschriften ihres Aufenthaltsstaats unberührt. Für Kaufleute ist Gerichtsstand der Sitz des Anbieters." : "German law applies, excluding the UN Convention on Contracts for the International Sale of Goods. For consumers, mandatory protective provisions of their country of residence remain unaffected. For merchants, the place of jurisdiction is the provider's seat."}</p>
  </>;
}

export function LegalPage({ page, lang, setLang }) {
  const de = lang === "de";
  const { operator, failed } = useOperator();
  useEffect(() => { window.scrollTo(0, 0); document.title = titles[lang][page] + " · Rechtsassistentin Schimmelpilz"; }, [page, lang]);
  const Body = { impressum: Impressum, datenschutz: Privacy, agb: Terms }[page];
  return <div className="site legal-site">
    <header className="site-header"><a className="brand-link" href="#top"><BrandLogo /></a><nav className="legal-nav"><button className={de ? "language active" : "language"} onClick={() => setLang("de")}>DE</button><span className="language-sep">|</span><button className={!de ? "language active" : "language"} onClick={() => setLang("en")}>EN</button></nav></header>
    <main id="main" className="legal-main">
      <a className="legal-back" href="#top"><IconArrowLeft size={17} />{de ? "Zurück" : "Back"}</a>
      <h1>{titles[lang][page]}</h1>
      {failed && <p className="storage-error" role="alert">{de ? "Die Anbieterangaben konnten nicht geladen werden. Bitte später erneut versuchen." : "The provider details could not be loaded. Please try again later."}</p>}
      {operator && !operator.complete && <p className="storage-error" role="alert">{de ? "Die Anbieterangaben sind noch nicht vollständig hinterlegt." : "The provider details have not been fully provided yet."}</p>}
      {operator && <Body operator={operator} de={de} />}
      <p className="legal-stand">{de ? "Stand" : "Last updated"}: {STAND}</p>
    </main>
    <footer className="site-footer"><BrandLogo /><span /><LegalLinks lang={lang} /></footer>
  </div>;
}
