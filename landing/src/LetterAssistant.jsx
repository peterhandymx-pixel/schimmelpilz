import { useEffect, useRef, useState } from "react";
import { IconMailOpened, IconCamera, IconKeyboard, IconArrowLeft, IconArrowRight, IconCheck, IconAlertTriangle, IconCalendarDue, IconEdit, IconScale, IconFolder, IconLoader2, IconLifebuoy, IconExternalLink, IconBell, IconMailForward } from "@tabler/icons-react";
import { request, readPreference, writePreference } from "./useCaseStorage.js";
import { dateLabel, localToday, taskRows } from "./workbench.js";
import "./letter-assistant.css";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const FINISHED = ["done", "no_text", "failed", "ocr_unavailable", "interrupted"];
const STATE_KEY = "schimmelpilz.state";
const STATES = [["BW", "Baden-Württemberg"], ["BY", "Bayern"], ["BE", "Berlin"], ["BB", "Brandenburg"], ["HB", "Bremen"], ["HH", "Hamburg"], ["HE", "Hessen"], ["MV", "Mecklenburg-Vorpommern"], ["NI", "Niedersachsen"], ["NW", "Nordrhein-Westfalen"], ["RP", "Rheinland-Pfalz"], ["SL", "Saarland"], ["SN", "Sachsen"], ["ST", "Sachsen-Anhalt"], ["SH", "Schleswig-Holstein"], ["TH", "Thüringen"]];
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
  },
};
const FIELD_TYPES = { letter_date: "date", letter_deadline: "date", amount: "number" };

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
  const fileInput = useRef(null);
  const today = localToday();

  useEffect(() => { request("/letter-assistant/kinds").then(setKinds).catch(() => setKinds([])); }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const questions = kinds.find(item => item.id === kind)?.questions || [];
  const openDeadlines = taskRows(storage.cases).filter(row => !row.completed && row.due_on && ["deadline", "notfrist"].includes(row.kind) && !row.caseItem.archived_at).slice(0, 6);

  const reset = () => { setStep("start"); setError(""); setPasted(""); setTyping(false); setCaseItem(null); setFollowCase(null); setText(""); setPreview(""); setFields({}); setAnswers({}); setQuestionIndex(0); setResult(null); setSaved(null); };

  const analyze = async letterText => {
    if (letterText.trim().length < 20) {
      setFields({}); setKind("sonstiges"); setError(c.unreadable); setStep("confirm");
      return;
    }
    const analysis = await request("/letter-assistant/analyze", json("POST", { text: letterText.slice(0, 120000) }));
    setKind(analysis.kind.id); setLegalArea(analysis.kind.legal_area); setFields(analysis.fields);
    setStep("confirm");
  };

  const startWithFile = async file => {
    if (!file) return;
    setError(""); setStep("reading"); setProgress(c.uploading);
    if (file.type.startsWith("image/")) setPreview(URL.createObjectURL(file));
    let target = followCase;
    try {
      if (!target) {
        target = await storage.createCase({ title: lang === "de" ? "Eingegangener Brief (in Prüfung)" : "Received letter (being checked)", description: "Über den Brief-Assistenten angelegt; die Angaben werden noch geprüft.", language: "de",
          details: { audience: user.audience, client_name: user.organisation || user.full_name, client_email: user.email, client_role: "respondent" } });
      }
      setCaseItem(target);
      const body = new FormData(); body.append("file", file);
      const document = await request(`/cases/${target.id}/documents`, { method: "POST", body });
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
      let target = caseItem || followCase;
      const party = fields.creditor || fields.sender;
      const title = followCase ? followCase.title : `${outcome.kind.label}${party ? ` – ${party}` : ""}`.slice(0, 120);
      const entry = `${outcome.kind.label}${given.received_on ? ` (eingegangen ${dateLabel(given.received_on, "de")})` : ""}: ${outcome.summary}${text ? `\n\nBrieftext (Auszug):\n${text.slice(0, 1800)}` : ""}`;
      const description = (followCase ? `${followCase.description}\n\n— Neuer Brief —\n${entry}` : `${entry}\n\nAngelegt mit dem Brief-Assistenten.`).slice(-4000);
      // Post from a court or authority: the sender is the court, the opponent is the party behind the letter.
      const official = /gericht|mahngericht|gerichtsvollzieher/i.test(fields.sender || "") || ["court", "enforcement"].includes(outcome.kind.stage);
      const courtLine = official ? [fields.court || fields.sender, fields.sender_address].filter(Boolean).join(", ") : "";
      const before = target?.details || { audience: user.audience, client_name: user.organisation || user.full_name, client_email: user.email };
      const details = {
        ...before,
        client_role: "respondent", opponent_name: (fields.creditor || (official ? "" : fields.sender) || before.opponent_name || "").slice(0, 160),
        opponent_address: (fields.creditor || official ? before.opponent_address || "" : fields.sender_address || "").slice(0, 500),
        opponent_reference: official ? before.opponent_reference || "" : (fields.reference || "").slice(0, 100), court_reference: official ? (fields.reference || "").slice(0, 100) : (before.court_reference || ""),
        legal_area: outcome.kind.legal_area, stage: outcome.kind.stage, received_on: given.received_on || null, deadline: outcome.deadline?.date || null,
        deadline_note: outcome.deadline ? `${outcome.deadline.label} (${outcome.deadline.norm})`.slice(0, 300) : "",
        dispute_value: fields.amount ? Number(fields.amount) : before.dispute_value ?? null, court: official ? courtLine.slice(0, 160) : (before.court || ""),
        objective: outcome.steps[0]?.slice(0, 2000) || "",
      };
      target = target ? await storage.updateCase(target.id, { title, description, language: "de", details })
        : await storage.createCase({ title, description, language: "de", details });
      // A new letter in the same matter replaces the deadlines of the previous one.
      if (followCase) for (const task of (target.tasks || []).filter(task => !task.completed && ["deadline", "notfrist"].includes(task.kind))) {
        target = await storage.saveTask(target.id, { title: task.title, note: task.note || "", due_on: task.due_on, priority: task.priority, kind: task.kind, due_time: task.due_time || null, pre_days: task.pre_days ?? 0, completed: true, completion_note: `Überholt durch neuen Brief: ${outcome.kind.label}` }, task.id);
      }
      const dated = [outcome.deadline && { title: outcome.deadline.label, date: outcome.deadline.date, note: `${outcome.deadline.basis} ${outcome.deadline.norm}`, strict: outcome.deadline.strict }, ...outcome.extra_deadlines.map(item => ({ title: item.label, date: item.date, note: "", strict: false }))].filter(Boolean);
      for (const item of dated) {
        if (item.date < today || target.tasks?.some(task => task.title === item.title.slice(0, 200) && task.due_on === item.date)) continue;
        const daysLeft = Math.round((new Date(item.date) - new Date(today)) / 86400000);
        target = await storage.saveTask(target.id, { title: item.title.slice(0, 200), note: item.note.slice(0, 2000), due_on: item.date, priority: "high", kind: item.strict ? "notfrist" : "deadline", pre_days: Math.max(0, Math.min(7, daysLeft - 1)) });
      }
      setCaseItem(target); setSaved(target);
    } catch {
      setError(c.saveFailed);
    }
  };

  const draftFrom = sample => import("./documentSamples.js").then(({ sampleContext }) => onDraft({ body: sample.body(sampleContext(saved || caseItem)), language: "de", kind: sample.kind, recipient: "" }, saved || caseItem));
  const complete = row => storage.saveTask(row.caseItem.id, { title: row.title, note: row.note || "", due_on: row.due_on, priority: row.priority, kind: row.kind, due_time: row.due_time || null, pre_days: row.pre_days ?? 0, completed: true, completion_note: c.doneNote }, row.id).catch(() => setError(c.offline));
  const followUp = row => { setFollowCase(row.caseItem); setError(""); window.scrollTo?.({ top: 0, behavior: "smooth" }); };

  const question = questions[questionIndex];
  const answered = question && (question.optional || answers[question.id]);

  return <section className="letter-assistant">
    {step === "start" && <>
      <div className="la-hero"><IconMailOpened size={40} stroke={1.3} /><div><h2>{followCase ? c.followUp : c.heroTitle}</h2><p>{followCase ? followCase.title : c.heroText}</p></div></div>
      {error && <p role="alert" className="la-error">{error}</p>}
      <div className="la-choices">
        <button className="la-choice" onClick={() => fileInput.current?.click()}><IconCamera size={30} stroke={1.4} /><strong>{c.upload}</strong><small>{c.uploadHint}</small></button>
        <button className="la-choice" onClick={() => setTyping(true)}><IconKeyboard size={30} stroke={1.4} /><strong>{c.type}</strong><small>{c.typeHint}</small></button>
      </div>
      <input ref={fileInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx" capture="environment" onChange={event => { startWithFile(event.target.files?.[0]); event.target.value = ""; }} />
      {typing && <div className="la-card"><label>{c.letterText}<textarea rows={10} value={pasted} onChange={event => setPasted(event.target.value)} placeholder={c.letterPlaceholder} /></label>
        <div className="la-actions"><button className="desk-button solid" disabled={pasted.trim().length < 20} onClick={startWithText}>{c.analyse}<IconArrowRight size={17} /></button><button className="desk-link" onClick={() => setTyping(false)}>{c.cancel}</button></div></div>}
      {followCase && <p className="la-more"><button className="desk-link" onClick={() => setFollowCase(null)}>{c.cancel}</button></p>}
      {!followCase && openDeadlines.length > 0 && <div className="la-card"><h3><IconCalendarDue size={19} />{c.open}</h3><p className="field-help">{c.openHint}</p>
        <ul className="la-followups">{openDeadlines.map(row => { const over = row.due_on < today; return <li key={row.id} className={over ? "over" : row.due_on <= today ? "due" : ""}>
          <button className="desk-link la-followup-title" onClick={() => open(row.caseItem.id, "tasks")}><strong>{dateLabel(row.due_on, lang)}</strong> {row.title}<small>{row.caseItem.title}</small></button>
          <span className="la-followup-actions"><button className="desk-button" onClick={() => complete(row)}><IconCheck size={15} />{c.done}</button><button className="desk-button" onClick={() => followUp(row)}><IconMailForward size={15} />{c.newLetter}</button>
            {over && <button className="desk-link" onClick={() => setMissed({ ...missed, [row.id]: !missed[row.id] })}>{c.nothing}</button>}</span>
          {missed[row.id] && <p className="la-warning"><IconAlertTriangle size={17} />{row.kind === "notfrist" ? c.missedStrict : c.missedSoft}</p>}</li>; })}</ul></div>}
      <ReminderToggle lang={lang} />
      <p className="la-more"><button className="desk-link" onClick={onShowAll}>{c.allFeatures}</button></p>
    </>}

    {(step === "reading" || step === "evaluating") && <div className="la-card la-busy" role="status"><IconLoader2 className="la-spin" size={30} />{step === "reading" ? progress : c.evaluating}</div>}

    {step === "confirm" && <form className={preview ? "la-card la-with-preview" : "la-card"} onSubmit={confirm}>
      <div>
        <p className="la-step">{c.step1}</p><h2>{c.confirmTitle}</h2><p>{c.confirmText}</p>
        {error && <p role="alert" className="la-error">{error}</p>}
        <label>{c.kind}<select value={kind} onChange={event => { setKind(event.target.value); setLegalArea(kinds.find(item => item.id === event.target.value)?.legal_area || ""); }}>{kinds.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <div className="la-grid">{Object.entries(c.fields).map(([id, label]) => <label key={id}>{label}<input type={FIELD_TYPES[id] || "text"} step={id === "amount" ? "0.01" : undefined} min={id === "amount" ? 0 : undefined} value={fields[id] ?? ""} onChange={event => setFields({ ...fields, [id]: event.target.value })} /></label>)}
          <label>{c.state}<select value={state} onChange={event => setState(event.target.value)}><option value="">{c.stateNone}</option>{STATES.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label></div>
        {text && <details className="la-text"><summary>{c.showText}</summary><pre>{text}</pre></details>}
        <div className="la-actions"><button className="desk-button solid"><IconCheck size={17} />{c.yes}</button><button type="button" className="desk-link" onClick={reset}>{c.cancel}</button></div>
      </div>
      {preview && <a className="la-preview" href={preview} target="_blank" rel="noreferrer"><img src={preview} alt={c.upload} /></a>}
    </form>}

    {step === "questions" && question && <div className="la-card">
      <p className="la-step">{c.question(questionIndex + 1, questions.length)}</p>
      <div className="la-progress"><span style={{ width: `${((questionIndex + 1) / questions.length) * 100}%` }} /></div>
      <h2>{question.label}</h2>{question.help && <p className="field-help">{question.help}</p>}
      {error && <p role="alert" className="la-error">{error}</p>}
      {question.type === "date" ? <div className="la-date"><input type="date" max={question.id === "received_on" ? today : undefined} value={answers[question.id] || ""} onChange={event => answer(question.id, event.target.value)} />
        {question.id === "received_on" && <button type="button" className="desk-link" onClick={() => answer(question.id, today)}>{c.today}</button>}</div>
        : <div className="la-options">{question.options.map(([value, label]) => <button key={value} type="button" className={answers[question.id] === value ? "la-option chosen" : "la-option"} onClick={() => answer(question.id, value)}>{label}</button>)}</div>}
      <div className="la-actions"><button className="desk-link" onClick={() => questionIndex ? setQuestionIndex(questionIndex - 1) : setStep("confirm")}><IconArrowLeft size={16} />{c.back}</button>
        <button className="desk-button solid" disabled={!answered} onClick={nextQuestion}>{questionIndex + 1 < questions.length ? c.next : c.show}<IconArrowRight size={17} /></button></div>
    </div>}

    {step === "result" && result && <div className="la-result">
      <div className="la-card"><p className="la-step">{c.step3}</p><h2>{result.kind.label}</h2><p>{result.summary}</p>{fields.amount ? <p><strong>{c.amount}:</strong> {euro(fields.amount)}</p> : null}</div>
      {result.deadline ? <div className={`la-deadline ${result.urgency}`}><IconCalendarDue size={34} stroke={1.4} /><div>
        <span>{result.deadline.label}{result.deadline.strict ? c.statutory : ""}</span>
        <strong>{dateLabel(result.deadline.date, lang)}</strong>
        <small>{result.deadline.days_left < 0 ? c.overdue(-result.deadline.days_left) : result.deadline.days_left === 0 ? c.todayLeft : c.left(result.deadline.days_left)} · {result.deadline.norm}</small>
        <p>{result.deadline.basis}</p></div></div>
        : <div className="la-card"><p><IconCalendarDue size={18} /> {c.noDeadline}</p></div>}
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
