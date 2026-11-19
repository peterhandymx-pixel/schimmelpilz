// Guided tours. Private persons get plain language; law firms and businesses get short, technical notes.
// A step: target (CSS selector), view to open first, Frau Schimmelpilz's pose, text; finish marks the last step.

const consumer = {
  de: [
    { pose: "wave", text: "Hallo, ich bin Frau Schimmelpilz! In einer Minute zeige ich Ihnen, wie Sie mit mir Ihre Post erledigen. Sie können jederzeit überspringen." },
    { target: '[data-module="assistant"]', view: "assistant", pose: "point", text: "Hier fängt alles an: der Brief-Assistent. Immer wenn Post kommt – oder Sie selbst etwas verschickt haben – klicken Sie hier." },
    { target: ".letter-assistant .sp-replies", view: "assistant", pose: "think", text: "Ich frage Sie zuerst: Haben Sie einen Brief bekommen oder etwas verschickt? Dann fotografieren Sie den Brief – mehrere Seiten auf einmal gehen auch – oder tippen ihn ab." },
    { target: ".letter-assistant .sp-track", view: "assistant", pose: "read", text: "Dann arbeite ich wie in einer Kanzlei: Akte anlegen, Brief lesen, Angaben prüfen, ein paar Fragen, Frist notieren. Die Frist berechne ich nach festen Regeln – mit Wochenenden und Feiertagen." },
    { target: '[data-module="cases"]', pose: "file", text: "Meine Vorgänge: Für jede Sache gibt es eine Akte. Dort liegt alles beisammen – Briefe, Fristen und Ihre Schreiben." },
    { target: '[data-module="tasks"]', pose: "alarm", text: "Fristen & Termine: Hier steht, was bis wann erledigt sein muss. Ich erinnere Sie per E-Mail – einmal rechtzeitig vorher und noch einmal am Tag vor Ablauf." },
    { target: '[data-module="documents"]', pose: "read", text: "Meine Unterlagen: alle Briefe und Fotos. Mit „Ansehen“ öffnen Sie das Original – Seite für Seite." },
    { target: '[data-module="drafts"]', pose: "file", text: "Meine Schreiben: Antworten und Widersprüche, die ich für Sie vorbereite. Sie können alles ändern und als PDF oder Word speichern." },
    { target: '[data-module="samples"]', pose: "point", text: "Vorlagen: über 100 fertige Musterschreiben, schon mit Ihren Daten ausgefüllt – vom Widerspruch bis zur Kündigung." },
    { target: '[data-module="account"]', pose: "smile", text: "Mein Konto: Hier stehen Ihre Anschrift – die brauche ich für Ihre Schreiben – und die Einstellung für die E-Mail-Erinnerungen." },
    { target: ".desk-mode-switch", pose: "point", text: "Und wenn Sie mehr brauchen: Hier schalten Sie zur vollen Ansicht mit Recherche, Kostenprüfung und allen Werkzeugen um." },
    { target: ".tour-replay", pose: "smile", text: "Diesen Rundgang finden Sie hier jederzeit wieder." },
    { pose: "cheer", text: "Das war's schon! Sollen wir gleich Ihren ersten Brief anschauen?", finish: "assistant" },
  ],
  en: [
    { pose: "wave", text: "Hello, I'm Ms Schimmelpilz! In one minute I'll show you how we deal with your post together. You can skip at any time." },
    { target: '[data-module="assistant"]', view: "assistant", pose: "point", text: "Everything starts here: the letter assistant. Whenever post arrives – or you sent something yourself – click here." },
    { target: ".letter-assistant .sp-replies", view: "assistant", pose: "think", text: "First I ask: did you receive a letter or send one? Then take a photo – several pages at once work too – or type it in." },
    { target: ".letter-assistant .sp-track", view: "assistant", pose: "read", text: "Then I work like a law office: open a file, read the letter, check the details, ask a few questions, note the deadline – calculated by fixed rules, with weekends and holidays." },
    { target: '[data-module="cases"]', pose: "file", text: "My matters: every matter has its own file with all letters, deadlines and your replies." },
    { target: '[data-module="tasks"]', pose: "alarm", text: "Deadlines: what has to be done by when. I remind you by email – once in good time and again the day before." },
    { target: '[data-module="documents"]', pose: "read", text: "My documents: all letters and photos. “View” opens the original, page by page." },
    { target: '[data-module="drafts"]', pose: "file", text: "My letters: replies and objections I prepare for you. Change anything, save as PDF or Word." },
    { target: '[data-module="samples"]', pose: "point", text: "Templates: more than 100 ready-made sample letters, already filled in with your details." },
    { target: '[data-module="account"]', pose: "smile", text: "My account: your address – I need it for your letters – and the email reminder setting." },
    { target: ".desk-mode-switch", pose: "point", text: "Need more? Switch to the full view with research, cost review and all tools here." },
    { target: ".tour-replay", pose: "smile", text: "You can start this tour again here at any time." },
    { pose: "cheer", text: "That's it! Shall we look at your first letter right away?", finish: "assistant" },
  ],
};

// First steps for professionals; firm and business differ in wording (Mandant vs. Vorgang) and in the team step.
function firstSteps(firm) {
  return {
    de: [
      { view: "overview", pose: "wave", text: firm ? "Willkommen. Kurzer Überblick über den Arbeitsplatz der Kanzlei – etwa eine Minute. Vertiefende Rundgänge (Diktat, Recherche, Abrechnung …) finden Sie unter „Hilfe & Rundgänge“."
        : "Willkommen. Kurzer Überblick über Ihren Arbeitsplatz – etwa eine Minute. Vertiefende Rundgänge finden Sie unter „Hilfe & Rundgänge“." },
      { target: '[data-module="overview"]', view: "overview", pose: "point", text: "Arbeitsplatz: fällige und überfällige Fristen, offene Aufgaben und zuletzt bearbeitete Akten auf einen Blick." },
      { target: ".desk-topbar .desk-button.solid", pose: "file", text: firm ? "Neue Akte: Mandant, Gegner, Rechtsgebiet, Gegenstandswert; Az. des Gerichts und der Gegenseite werden getrennt geführt. Aktenzeichen fortlaufend (SCH-JJJJ-…) oder aus Ihrem bisherigen Nummernkreis."
        : "Neue Akte: Vorgang, Gegenseite, Rechtsgebiet, Streitwert; Az. von Gericht und Gegenseite getrennt. Aktenzeichen fortlaufend oder aus Ihrem bisherigen Nummernkreis." },
      { target: '[data-module="inbox"]', pose: "read", text: "Posteingang: Eingänge ohne Akte erfassen und später zuordnen. Texterkennung (OCR) läuft lokal; Umzuordnungen bleiben protokolliert." },
      { target: '[data-module="tasks"]', pose: "alarm", text: "Termine/Fristen: Notfristen und Fristen mit Vorfrist; der Fristenrechner berücksichtigt Landesfeiertage. E-Mail-Erinnerung zur Vorfrist und am Vortag, Kalender-Export als ICS." },
      { target: '[data-module="drafts"]', pose: "file", text: "Schriftverkehr: Schriftsätze aus Vorlagen mit den Aktendaten. Beim Klageentwurf wird das zuständige Gericht sachlich und örtlich ermittelt und in der Zuständigkeitsbegründung belegt. Ausgabe als PDF oder Word mit Briefkopf, mit Prüf- und Freigabestatus." },
      { target: '[data-module="research"]', pose: "think", text: "Recherche: KI-Antworten auf Grundlage des Gesetzeskatalogs, passender Rechtsprechung (nu:legal) und einer Fachanleitung je Rechtsgebiet; zitierte Normen und Aktenzeichen werden automatisch geprüft. Arbeitshilfe – vor Verwendung prüfen." },
      ...(firm ? [{ target: '[data-module="dictate"]', pose: "point", text: "Diktat und Schreibpool: diktieren mit F-Tasten wie am Diktiergerät, das Sekretariat übernimmt aus dem Pool. Eigener Rundgang unter „Hilfe & Rundgänge“." }] : []),
      { target: '[data-module="team"]', pose: "smile", text: firm ? "Team & Rechte: Mitarbeiter einladen, Bearbeiten oder Lesen, auf einzelne Akten beschränkbar. Löschen bleibt dem Inhaber vorbehalten."
        : "Team & Rechte: Kollegen einladen, Bearbeiten oder Lesen, auf einzelne Akten beschränkbar." },
      { target: ".tour-replay", pose: "cheer", text: "Alle Rundgänge finden Sie hier. Gleich die erste Akte anlegen?", finish: "new-case" },
    ],
    en: [
      { view: "overview", pose: "wave", text: "Welcome. A short overview of the workspace – about one minute. More detailed tours are under “Help & tours”." },
      { target: '[data-module="overview"]', view: "overview", pose: "point", text: "Workspace: due and overdue deadlines, open tasks and recent files at a glance." },
      { target: ".desk-topbar .desk-button.solid", pose: "file", text: "New file: client, opponent, area of law, value; court and opponent references kept separately. References run consecutively or continue your own scheme." },
      { target: '[data-module="inbox"]', pose: "read", text: "Inbox: record incoming documents without a file and assign them later. OCR runs locally; reassignments stay logged." },
      { target: '[data-module="tasks"]', pose: "alarm", text: "Deadlines: statutory and other deadlines with advance notice; the calculator includes state holidays. Email reminders, ICS calendar export." },
      { target: '[data-module="drafts"]', pose: "file", text: "Correspondence: pleadings from templates with file data. For claims the competent court is determined and reasoned. PDF or Word with letterhead, review and approval status." },
      { target: '[data-module="research"]', pose: "think", text: "Research: AI answers based on the statute catalogue, case law (nu:legal) and an expert guide per area; cited sections and dockets are checked automatically. A working aid – review before use." },
      ...(firm ? [{ target: '[data-module="dictate"]', pose: "point", text: "Dictation and typing pool: dictate with F keys like a dictation device; staff take dictations from the pool. Own tour under “Help & tours”." }] : []),
      { target: '[data-module="team"]', pose: "smile", text: "Team & rights: invite staff, edit or read-only, limited to single files if needed." },
      { target: ".tour-replay", pose: "cheer", text: "All tours are here. Create your first file now?", finish: "new-case" },
    ],
  };
}

const dictation = {
  de: [
    { target: ".dictation-meta", view: "dictate", pose: "file", text: "Jedes Diktat gehört zu einer Akte. Priorität (normal, eilig, sofort) und ein Hinweis fürs Sekretariat gehen mit." },
    { target: ".dictation-transport", view: "dictate", pose: "point", text: "Bedienung wie am Diktiergerät: F8 Aufnahme, F5 Wiedergabe/Pause, F4 Stopp, F6/F7 zurück/vor – gedrückt halten spult schnell. Pos1/Ende springen an Anfang und Ende." },
    { target: ".dictation-mode", view: "dictate", pose: "think", text: "Korrekturen im laufenden Diktat: Überschreiben ersetzt ab der Position, Einfügen schiebt den Rest nach hinten. Einfg wechselt den Modus." },
    { target: ".dictation .sample-actions", view: "dictate", pose: "file", text: "Senden legt das Diktat in den Schreibpool und vermerkt es in der Aktenhistorie. Offene eigene Diktate lassen sich zurückziehen." },
    { target: ".dictation-filters", view: "pool", pose: "read", text: "Schreibpool: Filter nach Diktant und Status, sortiert nach Priorität. „Diktat übernehmen“ sperrt es für andere." },
    { target: ".dictation-pool .desk-panel-heading", view: "pool", pose: "read", text: "Abhörplatz: F5/F4/F6/F7 wirken auch beim Tippen im Textfeld, Geschwindigkeit 0,6–1,5×, Rücksprung bei Pause einstellbar. Die Abschrift geht direkt als Entwurf in die Akte." },
    { pose: "cheer", text: "Zum Abschluss „Als erledigt markieren“ mit Vermerk – wer wann geschrieben hat, steht in der Aktenhistorie.", finish: "dictate" },
  ],
  en: [
    { target: ".dictation-meta", view: "dictate", pose: "file", text: "Every dictation belongs to a file, with priority and a note for the typing staff." },
    { target: ".dictation-transport", view: "dictate", pose: "point", text: "Works like a dictation device: F8 record, F5 play/pause, F4 stop, F6/F7 back/forward (hold to spool), Home/End." },
    { target: ".dictation-mode", view: "dictate", pose: "think", text: "Corrections: overwrite replaces from the cursor, insert pushes the rest back. Insert key toggles." },
    { target: ".dictation .sample-actions", view: "dictate", pose: "file", text: "Send puts the dictation into the typing pool and logs it in the file history." },
    { target: ".dictation-filters", view: "pool", pose: "read", text: "Typing pool: filter by author and status, sorted by priority. Taking a dictation locks it for others." },
    { target: ".dictation-pool .desk-panel-heading", view: "pool", pose: "read", text: "Playback: F keys work while typing, speed 0.6–1.5×, rewind on pause. The transcript goes into the file as a draft." },
    { pose: "cheer", text: "Finally “mark as done” with a note – who typed it and when is logged in the file history.", finish: "dictate" },
  ],
};

export const TOURS = [
  { id: "consumer", title: { de: "Rundgang: So funktioniert's", en: "Tour: how it works" }, audiences: ["consumer"], auto: true, steps: consumer },
  { id: "first-firm", title: { de: "Erste Schritte (Kanzlei)", en: "First steps (law firm)" }, audiences: ["law_firm"], auto: true, steps: firstSteps(true) },
  { id: "first-business", title: { de: "Erste Schritte", en: "First steps" }, audiences: ["business"], auto: true, steps: firstSteps(false) },
  { id: "dictation", title: { de: "Diktat & Schreibpool", en: "Dictation & typing pool" }, audiences: ["law_firm"], offerOn: ["dictate", "pool"], steps: dictation },
];

export const toursFor = audience => TOURS.filter(tour => tour.audiences.includes(audience));
export const tourKey = (userId, tourId) => `schimmelpilz.tour.${tourId}.${userId}`;
