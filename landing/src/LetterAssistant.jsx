import { useEffect, useRef, useState } from "react";
import { IconMailOpened, IconCamera, IconKeyboard, IconArrowLeft, IconArrowRight, IconCheck, IconAlertTriangle, IconCalendarDue, IconEdit, IconScale, IconFolder, IconLoader2, IconLifebuoy, IconExternalLink, IconBell, IconMailForward } from "@tabler/icons-react";
import { request, readPreference, writePreference } from "./useCaseStorage.js";
import { dateLabel, localToday, taskRows } from "./workbench.js";
import { DateInput } from "./DateInput";
import "./letter-assistant.css";
import { AssistantSays, OfficeTrack } from "./Schimmelpilz.jsx";
import { CitedAnswer, CaseLawList, CitationCheck, SkillNote } from "./LegalSources.jsx";

// What the comic assistant says at each step, in the order a law office handles incoming post.
const G = {
  de: {
    track: ["Post annehmen", "Akte anlegen", "Brief lesen", "Angaben prüfen", "Fragen klären", "Frist notieren", "Antwort vorbereiten"],
    hello: name => `Hallo${name ? ` ${name}` : ""}, ich bin Frau Schimmelpilz, Ihre Rechtsassistentin.\nHaben Sie Post bekommen?`,
    yesPost: "Ja, ich habe einen Brief bekommen", noPost: "Nein – was steht bei mir an?", backPost: "Doch, ich habe einen Brief",
    bring: "Prima, dann her damit! Fotografieren Sie den Brief oder tippen Sie ihn ab. Ich lege eine Akte an, lese ihn genau durch und sage Ihnen, was zu tun ist – und bis wann.",
    follow: title => `Ein neuer Brief zur Akte „${title}“? Her damit – ich lege ihn dazu.`,
    openList: n => `Dann schauen wir in Ihre Akten: ${n === 1 ? "eine offene Frist" : `${n} offene Fristen`}. Ist da inzwischen etwas passiert?`,
    calm: "Alles ruhig – keine offenen Fristen. Sobald Post kommt, bin ich da.",
    reading: ["Ich lege eine neue Akte an …", "Ich lese den Brief …", "Wer schreibt, was wird verlangt, gibt es eine Frist?"],
    readingSay: stage => stage === 0 ? "Einen Moment, ich nehme den Brief an und lege eine Akte an." : stage === 1 ? "Jetzt lese ich den Brief – Wort für Wort, wie in der Kanzlei." : "Fast fertig – ich sortiere, was im Brief steht.",
    readingNote: "Bei Fotos dauert das Lesen etwas länger.",
    found: (kind, party, amount) => `Ich habe den Brief gelesen. Das ist: ${kind}${party ? ` von ${party}` : ""}${amount ? `, es geht um ${amount}` : ""}.\nBitte schauen Sie kurz über meine Notizen – stimmt alles?`,
    unreadable: "Hm, den Text kann ich leider nicht entziffern. Tragen Sie die wichtigsten Angaben bitte selbst ein – ich helfe danach weiter.",
    match: party => `\nÜbrigens: Zu ${party} haben Sie schon eine Akte. Soll ich den Brief dazulegen?`,
    asking: (i, n) => `Frage ${i} von ${n}`,
    calculating: "Einen Moment – ich rechne die Frist aus, mit Wochenenden und Feiertagen.",
    urgent: (label, date, days) => `Achtung! ${label}: ${date} – ${days}. Das gehen wir am besten sofort an. Unten steht, was zu tun ist.`,
    soon: (label, date, days) => `${label}: ${date} – ${days}. Das ist gut zu schaffen, aber bitte nicht liegen lassen.`,
    relaxed: (label, date, days) => `${label}: ${date} – ${days}. Genug Zeit. Ich habe unten aufgeschrieben, was zu tun ist.`,
    none: "Für diesen Brief gibt es keine feste Frist. Reagieren Sie trotzdem zeitnah – unten steht, wie.",
    filed: title => `Ich habe alles in die Akte „${title}“ gelegt und die Frist notiert.`,
    filing: "Ich lege alles in Ihre Akte …",
    own: summary => `Moment – das ist kein Brief an Sie, sondern ein Schreiben von Ihnen selbst. ${summary}\nAuf ein eigenes Schreiben muss ich keine Frist berechnen. Ich lege es zur Akte, damit alles beisammen ist.`,
    ownMatch: (ref, title) => `Zur Akte ${ref} · ${title} legen`, ownNew: "Neue Akte dafür anlegen", ownIncoming: "Nein, das habe ich bekommen",
    ownDone: title => `Erledigt – Ihr Schreiben liegt jetzt in der Akte „${title}“. Kommt eine Antwort, laden Sie sie einfach hier hoch.`,
    ownTitle: (court, ref) => `Eigenes Schreiben${court ? ` an ${court}` : ""}${ref ? ` (${ref})` : ""}`,
    matter: "Gut. Gehört der Brief zu einer neuen Sache – oder zu einer Akte, die wir schon haben?",
    matterNew: "Neue Sache", matterOld: "Bestehende Akte",
    pick: "Zu welcher Akte? Nennen Sie mir das Aktenzeichen – unseres, das vom Gericht oder das der Gegenseite. Sie können auch nach dem Namen suchen.",
    pickLabel: "Aktenzeichen oder Name", pickNone: "Dazu finde ich keine Akte. Prüfen Sie das Aktenzeichen – oder legen wir eine neue Sache an?", pickNew: "Doch neue Sache",
    aiRead: summary => `Ich habe den Brief gelesen. ${summary}\nBitte schauen Sie kurz über meine Notizen – stimmt alles?`,
    aiToggle: provider => `Brief mit KI lesen und erklären lassen (Text geht zur Auswertung an ${provider})`,
    explainTitle: "Frau Schimmelpilz erklärt",
    explaining: "Ich schreibe Ihnen gerade auf, was der Brief bedeutet …",
    explainFailed: "Die Erklärung konnte gerade nicht erstellt werden. Frist und Schritte oben gelten trotzdem.",
    explainNote: "Von der KI formuliert – die Frist oben ist nach festen Regeln berechnet.",
  },
  en: {
    track: ["Receive post", "Open file", "Read letter", "Check details", "Questions", "Note deadline", "Prepare reply"],
    hello: name => `Hello${name ? ` ${name}` : ""}, I'm Ms Schimmelpilz, your legal assistant.\nDid you receive a letter?`,
    yesPost: "Yes, I received a letter", noPost: "No – what is pending?", backPost: "Actually, I have a letter",
    bring: "Great, let's have it! Take a photo of the letter or type it in. I'll open a file, read it carefully and tell you what to do – and by when.",
    follow: title => `A new letter for "${title}"? Let's have it – I'll add it to the file.`,
    openList: n => `Then let's look at your files: ${n === 1 ? "one open deadline" : `${n} open deadlines`}. Has anything happened since?`,
    calm: "All quiet – no open deadlines. I'm here as soon as post arrives.",
    reading: ["Opening a new file …", "Reading the letter …", "Who writes, what is demanded, is there a deadline?"],
    readingSay: stage => stage === 0 ? "One moment, I'm taking the letter and opening a file." : stage === 1 ? "Now I'm reading the letter – word by word, like in a law office." : "Almost done – I'm sorting out what the letter says.",
    readingNote: "Photos take a little longer to read.",
    found: (kind, party, amount) => `I've read the letter. It is: ${kind}${party ? ` from ${party}` : ""}${amount ? `, about ${amount}` : ""}.\nPlease check my notes – is everything right?`,
    unreadable: "Hm, I can't make out the text. Please enter the key details yourself – I'll take it from there.",
    match: party => `\nBy the way: you already have a file for ${party}. Shall I add the letter to it?`,
    asking: (i, n) => `Question ${i} of ${n}`,
    calculating: "One moment – I'm calculating the deadline, including weekends and holidays.",
    urgent: (label, date, days) => `Attention! ${label}: ${date} – ${days}. Best to act right away. What to do is below.`,
    soon: (label, date, days) => `${label}: ${date} – ${days}. Manageable, but please don't leave it.`,
    relaxed: (label, date, days) => `${label}: ${date} – ${days}. Plenty of time. I've written down below what to do.`,
    none: "There is no fixed deadline for this letter. Still, reply soon – see below.",
    filed: title => `I've put everything into the file "${title}" and noted the deadline.`,
    filing: "Filing everything in your case …",
    own: summary => `Wait – this is not a letter to you but one you wrote yourself. ${summary}\nI don't need to calculate a deadline for your own letter. I'll put it in the file so everything is together.`,
    ownMatch: (ref, title) => `Add to file ${ref} · ${title}`, ownNew: "Open a new file for it", ownIncoming: "No, I received it",
    ownDone: title => `Done – your letter is now in the file "${title}". When a reply arrives, just upload it here.`,
    ownTitle: (court, ref) => `Own letter${court ? ` to ${court}` : ""}${ref ? ` (${ref})` : ""}`,
    matter: "Good. Is the letter about a new matter – or about a file we already have?",
    matterNew: "New matter", matterOld: "Existing file",
    pick: "Which file? Tell me the reference – ours, the court's or the other side's. You can also search by name.",
    pickLabel: "Reference or name", pickNone: "I can't find a file for that. Check the reference – or shall we open a new matter?", pickNew: "New matter after all",
    aiRead: summary => `I've read the letter. ${summary}\nPlease check my notes – is everything right?`,
    aiToggle: provider => `Let AI read and explain the letter (the text is sent to ${provider} for this)`,
    explainTitle: "Ms Schimmelpilz explains",
    explaining: "I'm writing down what the letter means for you …",
    explainFailed: "The explanation could not be created right now. The deadline and steps above still apply.",
    explainNote: "Worded by AI – the deadline above is calculated by fixed rules.",
  },
};

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// Same party? Compares names without case, punctuation or legal-form spacing; never merges on a short fragment.
const partyKey = name => (name || "").toLowerCase().replace(/[^a-z0-9äöüß]+/g, "");
export function sameParty(a, b) {
  const left = partyKey(a), right = partyKey(b);
  if (left.length < 5 || right.length < 5) return false;
  return left === right || left.includes(right) || right.includes(left);
}

// Fills the reply draft with what the assistant already knows. Only unambiguous placeholders are
// replaced; choices such as "[vollständig / in Höhe von …]" stay for the person to decide.
export function fillLetterPlaceholders(body, { fields = {}, answers = {}, user = {}, today }) {
  const date = iso => dateLabel(iso, "de");
  let text = body.replace("[Ort], [Datum]", `${user.city || "[Ort]"}, ${date(today)}`);
  if (fields.letter_date) {
    text = text.replace(/((?:Ihre?|Ihr)\b[^\n]*? vom )\[Datum\]/, `$1${date(fields.letter_date)}`)
      .replace(/(Schreiben vom )\[Datum\]/g, `$1${date(fields.letter_date)}`);
  }
  if (answers.received_on) text = text.replace(/(zugegangen am )\[Datum\]/g, `$1${date(answers.received_on)}`);
  if (fields.reference) text = text.replace(/((?:Nummer|Aktenzeichen) )\[Nummer\]/g, `$1${fields.reference}`);
  if (fields.amount) {
    const money = Number(fields.amount).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    text = text.replace(/(über )\[Betrag\]( EUR)/g, `$1${money}$2`);
  }
  if (user.full_name) text = text.replace("[Name / Unterschrift]", user.full_name);
  return text;
}
const FINISHED = ["done", "no_text", "failed", "ocr_unavailable", "interrupted"];
const STATE_KEY = "schimmelpilz.state";
const STATES = [["BW", "Baden-Württemberg"], ["BY", "Bayern"], ["BE", "Berlin"], ["BB", "Brandenburg"], ["HB", "Bremen"], ["HH", "Hamburg"], ["HE", "Hessen"], ["MV", "Mecklenburg-Vorpommern"], ["NI", "Niedersachsen"], ["NW", "Nordrhein-Westfalen"], ["RP", "Rheinland-Pfalz"], ["SL", "Saarland"], ["SN", "Sachsen"], ["ST", "Sachsen-Anhalt"], ["SH", "Schleswig-Holstein"], ["TH", "Thüringen"]];
const PROVIDERS = { groq: "Groq (USA)", gemini: "Google Gemini (USA)", ollama: "ein lokales KI-Modell" };
const AI_KEY = "schimmelpilz.letterAi";
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const euro = value => Number(value).toLocaleString("de-DE", { style: "currency", currency: "EUR" });

const T = {
  de: {
    heroTitle: "Ich habe einen Brief bekommen", heroText: "Laden Sie den Brief hoch. Wir lesen die wichtigsten Angaben heraus, Sie bestätigen sie, beantworten ein paar Fragen – und erhalten die Frist, die nächsten Schritte und einen fertigen Antwortentwurf.",
    upload: "Foto oder PDF hochladen", uploadHint: "Handyfoto genügt. JPG, PNG oder PDF bis 10 MB.", type: "Text abtippen oder einfügen", typeHint: "Wenn Sie den Brief als E-Mail oder Text haben.",
    letterText: "Text des Briefs", letterPlaceholder: "Absender, Datum, Betreff und den Text des Briefs hier einfügen …", analyse: "Auswerten", cancel: "Abbrechen",
    open: "Offene Fristen", openHint: "Was ist inzwischen passiert?", done: "Erledigt", doneNote: "Über den Brief-Assistenten als erledigt markiert", newLetter: "Neuer Brief dazu", nothing: "Nichts gemacht",
    missedStrict: "Bei einer verpassten gerichtlichen Frist hilft oft die Wiedereinsetzung in den vorigen Stand – Antrag binnen zwei Wochen nach Wegfall des Hindernisses (§§ 233, 234 ZPO). Holen Sie sofort anwaltliche Hilfe; bei einer Mahnbescheid-Frist ist der Widerspruch oft noch möglich, solange kein Vollstreckungsbescheid erlassen ist.",
    missedSoft: "Holen Sie die Antwort jetzt nach – besser spät als gar nicht. Kommt ein Mahnbescheid, laden Sie ihn hier hoch.",
    followUp: "Neuer Brief zur Akte", allFeatures: "Alle Funktionen anzeigen (Akten, Vorlagen, Recherche …)",
    uploading: "Brief wird hochgeladen …", reading: "Brief wird gelesen …", readingLong: "Texterkennung läuft noch – Fotos brauchen etwas länger …", evaluating: "Ergebnis wird berechnet …", analysing: "Brief wird ausgewertet …",
    unreadable: "Den Text konnten wir nicht lesen. Tragen Sie die wichtigsten Angaben bitte selbst ein – das Foto sehen Sie daneben.",
    badType: "Dieses Dateiformat wird nicht unterstützt. Bitte PDF, JPG oder PNG verwenden.", tooBig: "Die Datei ist größer als 10 MB.", failed: "Der Brief konnte nicht verarbeitet werden. Bitte erneut versuchen oder den Text abtippen.", offline: "Die Auswertung ist gerade nicht erreichbar.", checkData: "Bitte prüfen Sie die eingetragenen Daten (Datum, Betrag).",
    step1: "Schritt 1 von 3 · Angaben prüfen", confirmTitle: "Stimmt das so?", confirmText: "Das haben wir aus dem Brief gelesen. Korrigieren Sie, was nicht passt.",
    kind: "Art des Schreibens", state: "Ihr Bundesland (für Feiertage)", stateNone: "nur bundesweite Feiertage", showText: "Erkannten Text anzeigen", yes: "Ja, stimmt – weiter",
    fields: { sender: "Absender", sender_address: "Anschrift des Absenders", creditor: "Gegenseite / Gläubiger (falls nicht der Absender)", letter_date: "Datum des Briefs", reference: "Aktenzeichen / Kundennummer", amount: "Geforderter Betrag (€)", letter_deadline: "Im Brief genannte Frist" },
    question: (i, n) => `Schritt 2 von 3 · Frage ${i} von ${n}`, today: "Heute", back: "Zurück", next: "Weiter", show: "Ergebnis anzeigen",
    step3: "Schritt 3 von 3 · Ergebnis", amount: "Betrag", statutory: " · gesetzliche Frist", overdue: d => `seit ${d} Tagen abgelaufen – jetzt sofort handeln`, todayLeft: "heute!", left: d => `noch ${d} Tage`,
    noDeadline: "Für dieses Schreiben gibt es keine feste gesetzliche Frist. Reagieren Sie trotzdem zeitnah.", more: "Weitere Termine", todo: "Das ist jetzt zu tun", lawyer: "Anwalt:",
    prepare: "Antwort vorbereiten", prepareText: "Der Entwurf ist mit Ihren Angaben ausgefüllt. Ergänzen Sie nur noch die Stellen in [eckigen Klammern].",
    help: "Hilfe in der Nähe", form: "Antrag vorbereiten", saved: t => `Gespeichert in der Akte „${t}“`, savedDeadline: " – mit Frist und Erinnerung.", saving: "Wird in Ihrer Akte gespeichert …", saveFailed: "Das Ergebnis wird angezeigt, konnte aber nicht in der Akte gespeichert werden.",
    openCase: "Akte öffnen", another: "Weiteren Brief prüfen", reminders: "Erinnerung per E-Mail vor jeder Frist", remindersOff: "E-Mail-Versand ist auf diesem Server noch nicht eingerichtet.",
    matchText: (ref, title) => `Sie haben bereits eine Akte mit dieser Gegenseite: ${ref} · ${title}.`, matchAttach: "Brief zu dieser Akte nehmen",
    matchChosen: ref => `Der Brief wird zur Akte ${ref} genommen. Ihre bisherigen Angaben und Fristen dort bleiben erhalten.`, matchUndo: "Doch neue Akte anlegen",
  },
  en: {
    heroTitle: "I received a letter", heroText: "Upload the letter. We read the key details, you confirm them, answer a few questions – and get the deadline, next steps and a ready-made reply draft. Results follow German law and are shown in German.",
    upload: "Upload photo or PDF", uploadHint: "A phone photo is fine. JPG, PNG or PDF up to 10 MB.", type: "Type or paste the text", typeHint: "If you have the letter as an email or text.",
    letterText: "Letter text", letterPlaceholder: "Paste sender, date, subject and the letter text here …", analyse: "Analyse", cancel: "Cancel",
    open: "Open deadlines", openHint: "What has happened since?", done: "Done", doneNote: "Marked as done in the letter assistant", newLetter: "New letter on this", nothing: "Did nothing",
    missedStrict: "For a missed court deadline, reinstatement is often possible – apply within two weeks after the obstacle ends (§§ 233, 234 ZPO). Get a lawyer now; against a payment order (Mahnbescheid) an objection usually still works until an enforcement order is issued.",
    missedSoft: "Reply now – late is better than never. If a payment order arrives, upload it here.",
    followUp: "New letter for this file", allFeatures: "Show all features (files, templates, research …)",
    uploading: "Uploading letter …", reading: "Reading letter …", readingLong: "Text recognition still running – photos take a little longer …", evaluating: "Calculating result …", analysing: "Analysing letter …",
    unreadable: "We could not read the text. Please enter the key details yourself – the photo is shown next to the form.",
    badType: "This file type is not supported. Please use PDF, JPG or PNG.", tooBig: "The file is larger than 10 MB.", failed: "The letter could not be processed. Try again or type the text.", offline: "The analysis is not reachable right now.", checkData: "Please check the dates and the amount.",
    step1: "Step 1 of 3 · Check details", confirmTitle: "Is this correct?", confirmText: "This is what we read from the letter. Correct anything that does not fit.",
    kind: "Type of letter", state: "Your federal state (for holidays)", stateNone: "nationwide holidays only", showText: "Show recognised text", yes: "Yes, correct – continue",
    fields: { sender: "Sender", sender_address: "Sender's address", creditor: "Opposing party / creditor (if not the sender)", letter_date: "Date of the letter", reference: "Reference / customer number", amount: "Amount demanded (€)", letter_deadline: "Deadline stated in the letter" },
    question: (i, n) => `Step 2 of 3 · Question ${i} of ${n}`, today: "Today", back: "Back", next: "Next", show: "Show result",
    step3: "Step 3 of 3 · Result", amount: "Amount", statutory: " · statutory deadline", overdue: d => `expired ${d} days ago – act now`, todayLeft: "today!", left: d => `${d} days left`,
    noDeadline: "There is no fixed statutory deadline for this letter. Still, reply soon.", more: "Further dates", todo: "What to do now", lawyer: "Lawyer:",
    prepare: "Prepare a reply", prepareText: "The draft is filled in with your details. Only complete the parts in [square brackets].",
    help: "Help near you", form: "Prepare application", saved: t => `Saved in the file “${t}”`, savedDeadline: " – with deadline and reminder.", saving: "Saving to your file …", saveFailed: "The result is shown but could not be saved to the file.",
    openCase: "Open file", another: "Check another letter", reminders: "Email reminder before every deadline", remindersOff: "Email sending is not set up on this server yet.",
    matchText: (ref, title) => `You already have a file with this opposing party: ${ref} · ${title}.`, matchAttach: "Add letter to this file",
    matchChosen: ref => `The letter will be added to file ${ref}. Your existing details and deadlines there are kept.`, matchUndo: "Create a new file instead",
  },
};
const FIELD_TYPES = { letter_date: "date", letter_deadline: "date", amount: "number" };

const PROVISIONAL_TITLES = ["Eingegangener Brief (in Prüfung)", "Received letter (being checked)"];

// Reads the text of an uploaded letter once the automatic text recognition has finished (at most about two minutes).
async function readUploadedText(caseId, documentId, onProgress) {
  for (let attempt = 0; attempt < 60; attempt++) {
    const item = await request(`/cases/${caseId}`);
    const document = item.documents.find(entry => entry.id === documentId);
    if (document && FINISHED.includes(document.auto_text_status)) break;
    onProgress(attempt);
    await wait(2000);
  }
  const text = await request(`/cases/${caseId}/documents/${documentId}/text`);
  return text.units.map(unit => unit.reviewed_text ?? unit.original_text ?? "").join("\n\n").trim();
}

// Switch for deadline reminders by email; shown in the assistant and in the account.
export function ReminderToggle({ lang = "de" }) {
  const c = T[lang] || T.de;
  const [settings, setSettings] = useState(null);
  useEffect(() => { request("/reminders/settings").then(setSettings).catch(() => setSettings(null)); }, []);
  if (!settings) return null;
  const change = enabled => request("/reminders/settings", json("PUT", { enabled })).then(setSettings).catch(() => {});
  return <label className="la-reminder"><input type="checkbox" checked={settings.enabled} onChange={event => change(event.target.checked)} /><IconBell size={17} />{c.reminders}{!settings.mail_available && <small> · {c.remindersOff}</small>}</label>;
}

// Guided path for people without legal training: letter in, confirmed data, a few questions, a dated next step.
export function LetterAssistant({ lang = "de", user, storage, onDraft, open, onShowAll }) {
  const c = T[lang] || T.de;
  const [step, setStep] = useState("start");
  const [error, setError] = useState(""), [progress, setProgress] = useState("");
  const [pasted, setPasted] = useState(""), [typing, setTyping] = useState(false);
  const [kinds, setKinds] = useState([]);
  const [caseItem, setCaseItem] = useState(null), [followCase, setFollowCase] = useState(null);
  const [text, setText] = useState(""), [preview, setPreview] = useState("");
  const [kind, setKind] = useState("sonstiges"), [fields, setFields] = useState({}), [legalArea, setLegalArea] = useState("");
  const [state, setState] = useState(() => readPreference(STATE_KEY) || "");
  const [answers, setAnswers] = useState({}), [questionIndex, setQuestionIndex] = useState(0);
  const [result, setResult] = useState(null), [saved, setSaved] = useState(null), [samples, setSamples] = useState([]), [helpSamples, setHelpSamples] = useState({});
  const [missed, setMissed] = useState({});
  // AI reads and explains the letter when the operator enables it and the person agrees (remembered on this device).
  const [aiStatus, setAiStatus] = useState(null), [aiWanted, setAiWanted] = useState(() => readPreference(AI_KEY) !== "0");
  const [aiSummary, setAiSummary] = useState(""), [explanation, setExplanation] = useState(null);
  const aiOn = Boolean(aiStatus?.enabled && aiStatus?.ready && aiWanted);
  // true when the person chose to file this letter in an existing case they already run:
  // that case's particulars and deadlines stay; only empty fields are filled.
  const [attachOnly, setAttachOnly] = useState(false);
  // The assistant first asks whether post has arrived: ask | yes | no.
  const [post, setPost] = useState("ask");
  const [caseQuery, setCaseQuery] = useState("");
  // id of the letter uploaded into the provisional case, so it can move to an existing case.
  const [uploadedDoc, setUploadedDoc] = useState("");
  const fileInput = useRef(null);
  const today = localToday();
  const profileAddress = user?.street ? `${user.street}\n${user.postal_code} ${user.city}` : "";
  const party = fields.creditor || fields.sender;
  const provisional = Boolean(caseItem && uploadedDoc && PROVISIONAL_TITLES.includes(caseItem.title));
  const refKey = value => (value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  const sameReference = item => refKey(fields.reference).length >= 5 && [item.reference, item.details?.court_reference, item.details?.opponent_reference].some(value => refKey(value) === refKey(fields.reference));
  const matchingCase = !followCase && (!caseItem || provisional) && (party || fields.reference) ? (storage.cases || []).find(item => !item.archived_at && item.id !== caseItem?.id && (sameReference(item) || (party && sameParty(item.details?.opponent_name, party)))) : null;

  useEffect(() => { request("/letter-assistant/kinds").then(setKinds).catch(() => setKinds([])); }, []);
  useEffect(() => { request("/research/status").then(setAiStatus).catch(() => setAiStatus(null)); }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const questions = kinds.find(item => item.id === kind)?.questions || [];
  const openDeadlines = taskRows(storage.cases).filter(row => !row.completed && row.due_on && ["deadline", "notfrist"].includes(row.kind) && !row.caseItem.archived_at).slice(0, 6);

  const reset = () => { setPost((storage.cases || []).some(item => !item.archived_at) ? "matter" : "yes"); setCaseQuery(""); setAiSummary(""); setExplanation(null); setStep("start"); setError(""); setPasted(""); setTyping(false); setCaseItem(null); setFollowCase(null); setAttachOnly(false); setUploadedDoc(""); setText(""); setPreview(""); setFields({}); setAnswers({}); setQuestionIndex(0); setResult(null); setSaved(null); };

  const analyze = async letterText => {
    if (letterText.trim().length < 20) {
      setFields({}); setKind("sonstiges"); setError(c.unreadable); setStep("confirm");
      return;
    }
    const analysis = await request("/letter-assistant/analyze", json("POST", { text: letterText.slice(0, 120000), use_ai: aiOn }));
    setKind(analysis.kind.id); setLegalArea(analysis.kind.legal_area); setFields(analysis.fields); setAiSummary(analysis.ai ? analysis.summary : "");
    setStep(analysis.direction === "outgoing" ? "own" : "confirm");
  };

  const startWithFile = async file => {
    if (!file) return;
    setError(""); setStep("reading"); setProgress(c.uploading);
    if (file.type.startsWith("image/")) setPreview(URL.createObjectURL(file));
    let target = followCase;
    try {
      if (!target) {
        target = await storage.createCase({ title: PROVISIONAL_TITLES[lang === "de" ? 0 : 1], description: "Über den Brief-Assistenten angelegt; die Angaben werden noch geprüft.", language: "de",
          details: { audience: user.audience, client_name: user.organisation || user.full_name, client_address: profileAddress, client_email: user.email, client_role: "respondent" } });
      }
      setCaseItem(target);
      const body = new FormData(); body.append("file", file);
      const document = await request(`/cases/${target.id}/documents`, { method: "POST", body });
      if (!followCase) setUploadedDoc(document.id);
      setProgress(c.reading);
      const letterText = await readUploadedText(target.id, document.id, attempt => setProgress(attempt < 5 ? c.reading : c.readingLong));
      setText(letterText);
      await analyze(letterText);
    } catch (problem) {
      setError(problem.status === 415 ? c.badType : problem.status === 413 ? c.tooBig : c.failed);
      setStep(target ? "confirm" : "start");
    }
  };

  const startWithText = async () => {
    setError(""); setStep("reading"); setProgress(c.analysing);
    if (followCase) setCaseItem(followCase);
    try { setText(pasted); await analyze(pasted); } catch { setError(c.offline); setStep("start"); }
  };

  const confirm = event => {
    event.preventDefault();
    writePreference(STATE_KEY, state);
    setAnswers(current => ({ received_on: current.received_on || today, ...current }));
    setQuestionIndex(0); setStep("questions");
  };

  const answer = (id, value) => setAnswers(current => ({ ...current, [id]: value }));
  const nextQuestion = () => { if (questionIndex + 1 < questions.length) setQuestionIndex(questionIndex + 1); else evaluate(answers); };

  const evaluate = async given => {
    setError(""); setStep("evaluating");
    try {
      const outcome = await request("/letter-assistant/evaluate", json("POST", { kind, state: state || null, fields: { ...fields, legal_area: legalArea, amount: fields.amount === "" ? null : fields.amount }, answers: given }));
      setResult(outcome); setStep("result");
      setExplanation(aiOn ? { loading: true } : null);
      if (aiOn) request("/letter-assistant/explain", json("POST", { kind, state: state || null, fields: { ...fields, legal_area: legalArea, amount: fields.amount === "" ? null : fields.amount }, answers: given, text: text.slice(0, 120000) }))
        .then(answer => setExplanation({ text: answer.text, caseLaw: answer.case_law || [], check: answer.citation_check || [], skill: answer.skill || null })).catch(() => setExplanation({ failed: true }));
      const { SAMPLES } = await import("./documentSamples.js");
      setSamples(outcome.samples.map(id => SAMPLES.find(sample => sample.id === id)).filter(Boolean));
      setHelpSamples(Object.fromEntries(outcome.help.filter(item => item.sample).map(item => [item.id, SAMPLES.find(sample => sample.id === item.sample)]).filter(([, sample]) => sample)));
      await save(outcome, given);
    } catch (problem) {
      setError(problem.status === 422 ? c.checkData : c.offline);
      setStep("questions");
    }
  };

  // Files the result in the person's case: title, opponent, dates and a deadline with reminder.
  const save = async (outcome, given) => {
    try {
      let target = attachOnly ? followCase : caseItem || followCase;
      // An uploaded letter sits in a provisional case until now; it moves into the chosen existing case.
      if (attachOnly && provisional && caseItem.id !== followCase.id) {
        target = await request("/letter-assistant/move-letter", json("POST", { from_case_id: caseItem.id, document_id: uploadedDoc, to_case_id: followCase.id }));
        setUploadedDoc("");
      }
      const party = fields.creditor || fields.sender;
      const title = followCase ? followCase.title : `${outcome.kind.label}${party ? ` – ${party}` : ""}`.slice(0, 120);
      const entry = `${outcome.kind.label}${given.received_on ? ` (eingegangen ${dateLabel(given.received_on, "de")})` : ""}: ${outcome.summary}${text ? `\n\nBrieftext (Auszug):\n${text.slice(0, 1800)}` : ""}`;
      const description = (followCase ? `${followCase.description}\n\n— Neuer Brief —\n${entry}` : `${entry}\n\nAngelegt mit dem Brief-Assistenten.`).slice(-4000);
      // Post from a court or authority: the sender is the court, the opponent is the party behind the letter.
      const official = /gericht|mahngericht|gerichtsvollzieher/i.test(fields.sender || "") || ["court", "enforcement"].includes(outcome.kind.stage);
      const courtLine = official ? [fields.court || fields.sender, fields.sender_address].filter(Boolean).join(", ") : "";
      const before = target?.details || { audience: user.audience, client_name: user.organisation || user.full_name, client_address: profileAddress, client_email: user.email };
      const computed = {
        ...before,
        client_address: before.client_address || profileAddress,
        client_role: "respondent", opponent_name: (fields.creditor || (official ? "" : fields.sender) || before.opponent_name || "").slice(0, 160),
        opponent_address: (fields.creditor || official ? before.opponent_address || "" : fields.sender_address || "").slice(0, 500),
        opponent_reference: official ? before.opponent_reference || "" : (fields.reference || "").slice(0, 100), court_reference: official ? (fields.reference || "").slice(0, 100) : (before.court_reference || ""),
        legal_area: outcome.kind.legal_area, stage: outcome.kind.stage, received_on: given.received_on || null, deadline: outcome.deadline?.date || null,
        deadline_note: outcome.deadline ? `${outcome.deadline.label} (${outcome.deadline.norm})`.slice(0, 300) : "",
        dispute_value: fields.amount ? Number(fields.amount) : before.dispute_value ?? null, court: official ? courtLine.slice(0, 160) : (before.court || ""),
        objective: outcome.steps[0]?.slice(0, 2000) || "",
      };
      // Filing into a case the person runs themselves must not overwrite its particulars.
      const details = attachOnly ? Object.fromEntries(Object.entries(computed).map(([key, value]) => [key, before[key] === "" || before[key] == null ? value : before[key]])) : computed;
      target = target ? await storage.updateCase(target.id, { title, description, language: "de", details })
        : await storage.createCase({ title, description, language: "de", details });
      // A new letter in the same matter replaces the deadlines of the previous one.
      if (followCase && !attachOnly) for (const task of (target.tasks || []).filter(task => !task.completed && ["deadline", "notfrist"].includes(task.kind))) {
        target = await storage.saveTask(target.id, { title: task.title, note: task.note || "", due_on: task.due_on, priority: task.priority, kind: task.kind, due_time: task.due_time || null, pre_days: task.pre_days ?? 0, completed: true, completion_note: `Überholt durch neuen Brief: ${outcome.kind.label}` }, task.id);
      }
      const dated = [outcome.deadline && { title: outcome.deadline.label, date: outcome.deadline.date, note: `${outcome.deadline.basis} ${outcome.deadline.norm}`, strict: outcome.deadline.strict }, ...outcome.extra_deadlines.map(item => ({ title: item.label, date: item.date, note: "", strict: false }))].filter(Boolean);
      for (const item of dated) {
        if (item.date < today || target.tasks?.some(task => task.title === item.title.slice(0, 200) && task.due_on === item.date)) continue;
        const daysLeft = Math.round((new Date(item.date) - new Date(today)) / 86400000);
        target = await storage.saveTask(target.id, { title: item.title.slice(0, 200), note: item.note.slice(0, 2000), due_on: item.date, priority: "high", kind: item.strict ? "notfrist" : "deadline", pre_days: Math.max(0, Math.min(7, daysLeft - 1)) });
      }
      setCaseItem(target); setSaved(target);
      storage.reload?.();
    } catch {
      setError(c.saveFailed);
    }
  };

  const draftFrom = sample => import("./documentSamples.js").then(({ sampleContext }) => onDraft({ body: fillLetterPlaceholders(sample.body(sampleContext(saved || caseItem)), { fields, answers, user, today }), language: "de", kind: sample.kind, recipient: "" }, saved || caseItem));
  const fileOwn = async existing => {
    setError("");
    try {
      const note = `— Eigenes Schreiben${fields.letter_date ? ` vom ${dateLabel(fields.letter_date, "de")}` : ""} —\n${aiSummary || ""}${text ? `\n\nText (Auszug):\n${text.slice(0, 1500)}` : ""}`;
      let target = existing || followCase;
      if (target && provisional && uploadedDoc) {
        target = await request("/letter-assistant/move-letter", json("POST", { from_case_id: caseItem.id, document_id: uploadedDoc, to_case_id: target.id }));
        setUploadedDoc("");
      }
      const details = target ? target.details : { audience: user.audience, client_name: user.organisation || user.full_name, client_address: profileAddress, client_email: user.email };
      const filled = { ...details, court: details.court || fields.court || "", court_reference: details.court_reference || fields.reference || "", opponent_name: details.opponent_name || fields.creditor || "" };
      if (target) target = await storage.updateCase(target.id, { title: target.title, description: `${target.description || ""}\n\n${note}`.slice(-4000), language: "de", details: filled });
      else if (caseItem) target = await storage.updateCase(caseItem.id, { title: g.ownTitle(fields.court, fields.reference).slice(0, 120), description: note.slice(0, 4000), language: "de", details: filled });
      else target = await storage.createCase({ title: g.ownTitle(fields.court, fields.reference).slice(0, 120), description: note.slice(0, 4000), language: "de", details: filled });
      setCaseItem(target); setSaved(target); setStep("ownDone"); storage.reload?.();
    } catch { setError(c.saveFailed); }
  };
  const attachTo = item => { setFollowCase(item); setAttachOnly(true); };
  const complete = row => storage.saveTask(row.caseItem.id, { title: row.title, note: row.note || "", due_on: row.due_on, priority: row.priority, kind: row.kind, due_time: row.due_time || null, pre_days: row.pre_days ?? 0, completed: true, completion_note: c.doneNote }, row.id).catch(() => setError(c.offline));
  const followUp = row => { setFollowCase(row.caseItem); setError(""); window.scrollTo?.({ top: 0, behavior: "smooth" }); };

  const question = questions[questionIndex];
  const g = G[lang] || G.de;
  const firstName = "";
  // Existing files the letter may belong to, found by our reference, the court's or the other side's, or by name.
  const activeCases = (storage.cases || []).filter(item => !item.archived_at);
  const needle = caseQuery.trim().toLowerCase();
  const caseHits = activeCases.filter(item => !needle || [item.reference, item.title, item.details?.court_reference, item.details?.opponent_reference, item.details?.opponent_name, item.details?.client_name]
    .some(value => (value || "").toLowerCase().includes(needle))).slice(0, 6);
  const gotPost = () => { setCaseQuery(""); setPost(activeCases.length ? "matter" : "yes"); };
  const pickCase = item => { setFollowCase(item); setAttachOnly(true); setPost("yes"); };
  const readingStage = progress === c.uploading ? 0 : text || progress === c.analysing ? 2 : 1;
  // The assistant's reaction to the result: alarmed for short deadlines, relaxed when there is time.
  const verdict = outcome => {
    const deadline = outcome.deadline;
    if (!deadline) return { pose: "cheer", mood: "smile", text: g.none };
    const days = deadline.days_left < 0 ? c.overdue(-deadline.days_left) : deadline.days_left === 0 ? c.todayLeft : c.left(deadline.days_left);
    const args = [deadline.label, dateLabel(deadline.date, lang), days];
    if (["overdue", "high"].includes(outcome.urgency)) return { pose: "alarm", mood: "worried", text: g.urgent(...args) };
    if (outcome.urgency === "medium") return { pose: "point", mood: "focus", text: g.soon(...args) };
    return { pose: "cheer", mood: "grin", text: g.relaxed(...args) };
  };
  const answered = question && (question.optional || answers[question.id]);

  return <section className="letter-assistant">
    {step === "start" && <>
      <OfficeTrack steps={g.track} current={0} />
      {followCase ? <AssistantSays pose="file" mood="smile" text={g.follow(followCase.title)} />
        : post === "ask" ? <AssistantSays pose="wave" mood="grin" text={g.hello(firstName)}>
          <button className="sp-reply primary" onClick={gotPost}><IconMailOpened size={17} />{g.yesPost}</button>
          <button className="sp-reply" onClick={() => setPost("no")}>{g.noPost}</button></AssistantSays>
        : post === "no" ? <AssistantSays pose={openDeadlines.length ? "file" : "cheer"} mood={openDeadlines.length ? "focus" : "grin"} text={openDeadlines.length ? g.openList(openDeadlines.length) : g.calm}>
          <button className="sp-reply primary" onClick={gotPost}><IconMailOpened size={17} />{g.backPost}</button></AssistantSays>
        : post === "matter" ? <AssistantSays pose="think" mood="think" text={g.matter}>
          <button className="sp-reply primary" onClick={() => setPost("yes")}>{g.matterNew}</button>
          <button className="sp-reply" onClick={() => setPost("pick")}><IconFolder size={17} />{g.matterOld}</button></AssistantSays>
        : post === "pick" ? <AssistantSays pose="file" mood="focus" text={g.pick} />
        : <AssistantSays pose="point" mood="grin" text={g.bring} />}
      {!followCase && post === "pick" && <div className="la-card la-pick">
        <label>{g.pickLabel}<input autoFocus value={caseQuery} onChange={event => setCaseQuery(event.target.value)} placeholder="SCH-2026-… / 26-1234567-0-1 / Name" /></label>
        {caseHits.length ? <ul className="la-followups">{caseHits.map(item => <li key={item.id}><button className="desk-link la-followup-title" onClick={() => pickCase(item)}>
          <strong>{item.reference}</strong> {item.title}<small>{[item.details?.opponent_name, item.details?.court_reference].filter(Boolean).join(" · ")}</small></button></li>)}</ul>
          : <p className="field-help">{g.pickNone}</p>}
        <div className="la-actions"><button className="desk-link" onClick={() => setPost("matter")}><IconArrowLeft size={16} />{c.back}</button><button className="desk-button" onClick={() => setPost("yes")}>{g.pickNew}</button></div>
      </div>}
      {error && <p role="alert" className="la-error">{error}</p>}
      {(post === "yes" || followCase) && <div className="la-choices">
        <button className="la-choice" onClick={() => fileInput.current?.click()}><IconCamera size={30} stroke={1.4} /><strong>{c.upload}</strong><small>{c.uploadHint}</small></button>
        <button className="la-choice" onClick={() => setTyping(true)}><IconKeyboard size={30} stroke={1.4} /><strong>{c.type}</strong><small>{c.typeHint}</small></button>
      </div>}
      <input ref={fileInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx" capture="environment" onChange={event => { startWithFile(event.target.files?.[0]); event.target.value = ""; }} />
      {typing && <div className="la-card"><label>{c.letterText}<textarea rows={10} value={pasted} onChange={event => setPasted(event.target.value)} placeholder={c.letterPlaceholder} /></label>
        <div className="la-actions"><button className="desk-button solid" disabled={pasted.trim().length < 20} onClick={startWithText}>{c.analyse}<IconArrowRight size={17} /></button><button className="desk-link" onClick={() => setTyping(false)}>{c.cancel}</button></div></div>}
      {followCase && <p className="la-more"><button className="desk-link" onClick={() => { setFollowCase(null); setAttachOnly(false); setPost(activeCases.length ? "matter" : "yes"); }}>{c.cancel}</button></p>}
      {!followCase && post === "no" && openDeadlines.length > 0 && <div className="la-card"><h3><IconCalendarDue size={19} />{c.open}</h3><p className="field-help">{c.openHint}</p>
        <ul className="la-followups">{openDeadlines.map(row => { const over = row.due_on < today; return <li key={row.id} className={over ? "over" : row.due_on <= today ? "due" : ""}>
          <button className="desk-link la-followup-title" onClick={() => open(row.caseItem.id, "tasks")}><strong>{dateLabel(row.due_on, lang)}</strong> {row.title}<small>{row.caseItem.title}</small></button>
          <span className="la-followup-actions"><button className="desk-button" onClick={() => complete(row)}><IconCheck size={15} />{c.done}</button><button className="desk-button" onClick={() => followUp(row)}><IconMailForward size={15} />{c.newLetter}</button>
            {over && <button className="desk-link" onClick={() => setMissed({ ...missed, [row.id]: !missed[row.id] })}>{c.nothing}</button>}</span>
          {missed[row.id] && <p className="la-warning"><IconAlertTriangle size={17} />{row.kind === "notfrist" ? c.missedStrict : c.missedSoft}</p>}</li>; })}</ul></div>}
      {aiStatus?.enabled && aiStatus?.ready && (post === "yes" || followCase) && <label className="la-reminder"><input type="checkbox" checked={aiWanted} onChange={event => { setAiWanted(event.target.checked); writePreference(AI_KEY, event.target.checked ? "1" : "0"); }} />{g.aiToggle(PROVIDERS[aiStatus.provider] || aiStatus.provider)}</label>}
      <ReminderToggle lang={lang} />
      <p className="la-more"><button className="desk-link" onClick={onShowAll}>{c.allFeatures}</button></p>
    </>}

    {step === "reading" && <><OfficeTrack steps={g.track} current={readingStage === 0 ? 1 : 2} busy />
      <AssistantSays pose={readingStage === 0 ? "file" : "read"} mood="focus" text={g.readingSay(readingStage)} note={progress === c.readingLong ? g.readingNote : ""}>
        <ul className="sp-checklist">{g.reading.map((line, index) => <li key={line} className={index < readingStage ? "done" : index === readingStage ? "now" : ""}>{line}</li>)}</ul></AssistantSays></>}
    {step === "evaluating" && <><OfficeTrack steps={g.track} current={5} busy /><AssistantSays pose="read" mood="focus" text={g.calculating} /></>}

    {step === "own" && <><OfficeTrack steps={g.track} current={2} />
      <AssistantSays pose="think" mood="focus" text={g.own(aiSummary)}>
        {(followCase || matchingCase) && <button className="sp-reply primary" onClick={() => fileOwn(followCase || matchingCase)}><IconFolder size={17} />{g.ownMatch((followCase || matchingCase).reference, (followCase || matchingCase).title)}</button>}
        {!followCase && <button className={followCase || matchingCase ? "sp-reply" : "sp-reply primary"} onClick={() => fileOwn(null)}>{g.ownNew}</button>}
        <button className="sp-reply" onClick={() => setStep("confirm")}>{g.ownIncoming}</button>
      </AssistantSays>
      {error && <p role="alert" className="la-error">{error}</p>}</>}
    {step === "ownDone" && saved && <><OfficeTrack steps={g.track} current={7} />
      <AssistantSays pose="cheer" mood="grin" text={g.ownDone(saved.title)}>
        <button className="sp-reply primary" onClick={() => open(saved.id, "overview")}><IconFolder size={17} />{c.openCase}</button>
        <button className="sp-reply" onClick={reset}><IconMailOpened size={17} />{c.another}</button>
      </AssistantSays></>}
    {step === "confirm" && <OfficeTrack steps={g.track} current={3} />}
    {step === "confirm" && (error === c.unreadable ? <AssistantSays pose="think" mood="worried" text={g.unreadable} />
      : <AssistantSays pose="file" mood="smile" text={(aiSummary ? g.aiRead(aiSummary) : g.found(kinds.find(item => item.id === kind)?.label || kind, party, fields.amount ? euro(fields.amount) : "")) + (matchingCase ? g.match(party) : "")} />)}
    {step === "confirm" && <form className={preview ? "la-card la-with-preview" : "la-card"} onSubmit={confirm}>
      <div>
        <p className="la-step">{c.step1}</p>
        {error && error !== c.unreadable && <p role="alert" className="la-error">{error}</p>}
        <label>{c.kind}<select value={kind} onChange={event => { setKind(event.target.value); setLegalArea(kinds.find(item => item.id === event.target.value)?.legal_area || ""); }}>{kinds.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <div className="la-grid">{Object.entries(c.fields).map(([id, label]) => <label key={id}>{label}{FIELD_TYPES[id] === "date"
          ? <DateInput lang={lang} value={fields[id] || ""} onChange={event => setFields({ ...fields, [id]: event.target.value })} />
          : <input type={FIELD_TYPES[id] || "text"} step={id === "amount" ? "0.01" : undefined} min={id === "amount" ? 0 : undefined} value={fields[id] ?? ""} onChange={event => setFields({ ...fields, [id]: event.target.value })} />}</label>)}
          <label>{c.state}<select value={state} onChange={event => setState(event.target.value)}><option value="">{c.stateNone}</option>{STATES.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label></div>
        {matchingCase && <p className="la-match"><IconFolder size={18} /><span>{c.matchText(matchingCase.reference, matchingCase.title)}</span><button type="button" className="desk-button" onClick={() => attachTo(matchingCase)}>{c.matchAttach}</button></p>}
        {followCase && attachOnly && <p className="la-match chosen"><IconCheck size={18} /><span>{c.matchChosen(followCase.reference)}</span><button type="button" className="desk-link" onClick={() => { setFollowCase(null); setAttachOnly(false); }}>{c.matchUndo}</button></p>}
        {text && <details className="la-text"><summary>{c.showText}</summary><pre>{text}</pre></details>}
        <div className="la-actions"><button className="desk-button solid"><IconCheck size={17} />{c.yes}</button><button type="button" className="desk-link" onClick={reset}>{c.cancel}</button></div>
      </div>
      {preview && <a className="la-preview" href={preview} target="_blank" rel="noreferrer"><img src={preview} alt={c.upload} /></a>}
    </form>}

    {step === "questions" && question && <><OfficeTrack steps={g.track} current={4} />
      <AssistantSays pose="think" mood="think" text={question.label} note={question.help || ""} /></>}
    {step === "questions" && question && <div className="la-card">
      <p className="la-step">{c.question(questionIndex + 1, questions.length)}</p>
      <div className="la-progress"><span style={{ width: `${((questionIndex + 1) / questions.length) * 100}%` }} /></div>
      {error && <p role="alert" className="la-error">{error}</p>}
      {question.type === "date" ? <div className="la-date"><DateInput lang={lang} max={question.id === "received_on" ? today : undefined} value={answers[question.id] || ""} onChange={event => answer(question.id, event.target.value)} />
        {question.id === "received_on" && <button type="button" className="desk-link" onClick={() => answer(question.id, today)}>{c.today}</button>}</div>
        : <div className="la-options">{question.options.map(([value, label]) => <button key={value} type="button" className={answers[question.id] === value ? "la-option chosen" : "la-option"} onClick={() => answer(question.id, value)}>{label}</button>)}</div>}
      <div className="la-actions"><button className="desk-link" onClick={() => questionIndex ? setQuestionIndex(questionIndex - 1) : setStep("confirm")}><IconArrowLeft size={16} />{c.back}</button>
        <button className="desk-button solid" disabled={!answered} onClick={nextQuestion}>{questionIndex + 1 < questions.length ? c.next : c.show}<IconArrowRight size={17} /></button></div>
    </div>}

    {step === "result" && result && <div className="la-result">
      <OfficeTrack steps={g.track} current={saved ? (samples.length ? 6 : 7) : 5} busy={!saved} />
      <AssistantSays {...verdict(result)} note={saved ? g.filed(saved.title) : g.filing} />
      <div className="la-card"><p className="la-step">{c.step3}</p><h2>{result.kind.label}</h2><p>{result.summary}</p>{fields.amount ? <p><strong>{c.amount}:</strong> {euro(fields.amount)}</p> : null}</div>
      {result.deadline ? <div className={`la-deadline ${result.urgency}`}><IconCalendarDue size={34} stroke={1.4} /><div>
        <span>{result.deadline.label}{result.deadline.strict ? c.statutory : ""}</span>
        <strong>{dateLabel(result.deadline.date, lang)}</strong>
        <small>{result.deadline.days_left < 0 ? c.overdue(-result.deadline.days_left) : result.deadline.days_left === 0 ? c.todayLeft : c.left(result.deadline.days_left)} · {result.deadline.norm}</small>
        <p>{result.deadline.basis}</p></div></div>
        : <div className="la-card"><p><IconCalendarDue size={18} /> {c.noDeadline}</p></div>}
      {explanation && <div className="la-card la-explain"><h3>{g.explainTitle}</h3>
        {explanation.loading ? <p className="la-busy" role="status"><IconLoader2 className="la-spin" size={20} />{g.explaining}</p>
          : explanation.failed ? <p className="field-help">{g.explainFailed}</p>
          : <><CitedAnswer answer={explanation.text} caseLaw={explanation.caseLaw} /><CitationCheck lang={lang} items={explanation.check} /><SkillNote lang={lang} skill={explanation.skill} /><CaseLawList lang={lang} items={explanation.caseLaw} /><p className="la-disclaimer">{g.explainNote}</p></>}</div>}
      {result.extra_deadlines.length > 0 && <div className="la-card"><h3>{c.more}</h3><ul className="la-deadlines">{result.extra_deadlines.map(item => <li key={item.label}><strong>{dateLabel(item.date, lang)}</strong> {item.label}</li>)}</ul></div>}
      <div className="la-card"><h3>{c.todo}</h3><ol className="la-steps">{result.steps.map(item => <li key={item}>{item}</li>)}</ol>
        {result.warnings.map(item => <p key={item} className="la-warning"><IconAlertTriangle size={18} />{item}</p>)}
        {result.lawyer && <p className="la-lawyer"><IconScale size={18} /><span><strong>{c.lawyer}</strong> {result.lawyer}</span></p>}</div>
      {samples.length > 0 && <div className="la-card"><h3>{c.prepare}</h3><p>{c.prepareText}</p>
        <div className="la-samples">{samples.map(sample => <button key={sample.id} className="desk-button" disabled={!saved && !caseItem} onClick={() => draftFrom(sample)}><IconEdit size={17} />{sample.title}</button>)}</div></div>}
      {result.help.length > 0 && <div className="la-card"><h3><IconLifebuoy size={19} />{c.help}</h3><div className="la-help">{result.help.map(item => <div key={item.id} className="la-help-item"><strong>{item.title}</strong><p>{item.text}</p>
        <span>{item.link && <a className="desk-link" href={item.link} target="_blank" rel="noreferrer">{item.link.replace(/^https?:\/\/(www\.)?/, "").split("/")[0]}<IconExternalLink size={14} /></a>}
          {helpSamples[item.id] && <button className="desk-link" disabled={!saved && !caseItem} onClick={() => draftFrom(helpSamples[item.id])}><IconEdit size={14} />{c.form}</button>}</span></div>)}</div></div>}
      {error && <p role="alert" className="la-error">{error}</p>}
      <div className="la-card la-saved">{saved ? <p><IconFolder size={18} /> {c.saved(saved.title)}{result.deadline && result.deadline.date >= today ? c.savedDeadline : "."}</p> : <p role="status">{c.saving}</p>}
        <div className="la-actions">{saved && <button className="desk-button" onClick={() => open(saved.id, "overview")}><IconFolder size={17} />{c.openCase}</button>}<button className="desk-button solid" onClick={reset}><IconMailOpened size={17} />{c.another}</button></div></div>
      <p className="la-disclaimer">{result.disclaimer}</p>
    </div>}
  </section>;
}
