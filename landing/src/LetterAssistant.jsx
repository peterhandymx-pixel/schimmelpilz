import { useEffect, useRef, useState } from "react";
import { IconMailOpened, IconCamera, IconKeyboard, IconArrowLeft, IconArrowRight, IconCheck, IconAlertTriangle, IconCalendarDue, IconEdit, IconScale, IconFolder, IconLoader2 } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { dateLabel, localToday, taskRows } from "./workbench.js";
import "./letter-assistant.css";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const FIELD_LABELS = [["sender", "Absender"], ["sender_address", "Anschrift des Absenders"], ["creditor", "Gegenseite / Gläubiger (falls nicht der Absender)"], ["letter_date", "Datum des Briefs", "date"], ["reference", "Aktenzeichen / Kundennummer"], ["amount", "Geforderter Betrag (€)", "number"], ["letter_deadline", "Im Brief genannte Frist", "date"]];
const FINISHED = ["done", "no_text", "failed", "ocr_unavailable", "interrupted"];
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const euro = value => Number(value).toLocaleString("de-DE", { style: "currency", currency: "EUR" });

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

// Guided path for people without legal training: letter in, confirmed data, a few questions, a dated next step.
export function LetterAssistant({ user, storage, onDraft, open, onShowAll }) {
  const [step, setStep] = useState("start");
  const [error, setError] = useState(""), [progress, setProgress] = useState("");
  const [pasted, setPasted] = useState(""), [typing, setTyping] = useState(false);
  const [kinds, setKinds] = useState([]);
  const [caseItem, setCaseItem] = useState(null);
  const [text, setText] = useState("");
  const [kind, setKind] = useState("sonstiges"), [fields, setFields] = useState({}), [legalArea, setLegalArea] = useState("");
  const [answers, setAnswers] = useState({}), [questionIndex, setQuestionIndex] = useState(0);
  const [result, setResult] = useState(null), [saved, setSaved] = useState(null), [samples, setSamples] = useState([]);
  const fileInput = useRef(null);
  const today = localToday();

  useEffect(() => { request("/letter-assistant/kinds").then(setKinds).catch(() => setKinds([])); }, []);
  const questions = kinds.find(item => item.id === kind)?.questions || [];
  const upcoming = taskRows(storage.cases).filter(row => !row.completed && row.due_on && !row.caseItem.archived_at).slice(0, 5);

  const reset = () => { setStep("start"); setError(""); setPasted(""); setTyping(false); setCaseItem(null); setText(""); setFields({}); setAnswers({}); setQuestionIndex(0); setResult(null); setSaved(null); };

  const analyze = async letterText => {
    if (letterText.trim().length < 20) {
      setFields({}); setKind("sonstiges");
      setError("Der Text des Briefs konnte nicht gelesen werden. Bitte tragen Sie die wichtigsten Angaben selbst ein.");
      setStep("confirm");
      return;
    }
    const analysis = await request("/letter-assistant/analyze", json("POST", { text: letterText.slice(0, 120000) }));
    setKind(analysis.kind.id); setLegalArea(analysis.kind.legal_area); setFields(analysis.fields);
    setStep("confirm");
  };

  const startWithFile = async file => {
    if (!file) return;
    setError(""); setStep("reading"); setProgress("Brief wird hochgeladen …");
    let createdCase = null;
    try {
      const created = await storage.createCase({ title: "Eingegangener Brief (in Prüfung)", description: "Über den Brief-Assistenten angelegt; die Angaben werden noch geprüft.", language: "de",
        details: { audience: user.audience, client_name: user.organisation || user.full_name, client_email: user.email, client_role: "respondent" } });
      createdCase = created; setCaseItem(created);
      const body = new FormData(); body.append("file", file);
      const document = await request(`/cases/${created.id}/documents`, { method: "POST", body });
      setProgress("Brief wird gelesen …");
      const letterText = await readUploadedText(created.id, document.id, attempt => setProgress(attempt < 5 ? "Brief wird gelesen …" : "Texterkennung läuft noch – Fotos brauchen etwas länger …"));
      setText(letterText);
      await analyze(letterText);
    } catch (problem) {
      setError(problem.status === 415 ? "Dieses Dateiformat wird nicht unterstützt. Bitte PDF, JPG oder PNG verwenden." : problem.status === 413 ? "Die Datei ist größer als 10 MB." : "Der Brief konnte nicht verarbeitet werden. Bitte versuchen Sie es erneut oder tippen Sie den Text ab.");
      setStep(createdCase ? "confirm" : "start");
    }
  };

  const startWithText = async () => {
    setError(""); setStep("reading"); setProgress("Brief wird ausgewertet …");
    try { setText(pasted); await analyze(pasted); } catch { setError("Die Auswertung ist gerade nicht erreichbar."); setStep("start"); }
  };

  const confirm = event => {
    event.preventDefault();
    setAnswers(current => ({ received_on: current.received_on || today, ...current }));
    setQuestionIndex(0); setStep(questions.length ? "questions" : "result");
    if (!questions.length) evaluate({ received_on: today });
  };

  const answer = (id, value) => setAnswers(current => ({ ...current, [id]: value }));
  const nextQuestion = () => { if (questionIndex + 1 < questions.length) setQuestionIndex(questionIndex + 1); else evaluate(answers); };

  const evaluate = async given => {
    setError(""); setStep("evaluating");
    try {
      const outcome = await request("/letter-assistant/evaluate", json("POST", { kind, fields: { ...fields, legal_area: legalArea, amount: fields.amount === "" ? null : fields.amount }, answers: given }));
      setResult(outcome); setStep("result");
      const { SAMPLES } = await import("./documentSamples.js");
      setSamples(outcome.samples.map(id => SAMPLES.find(sample => sample.id === id)).filter(Boolean));
      await save(outcome, given);
    } catch (problem) {
      setError(problem.status === 422 ? "Bitte prüfen Sie die eingetragenen Daten (Datum, Betrag)." : "Die Auswertung ist gerade nicht erreichbar.");
      setStep("questions");
    }
  };

  // Files the result in the person's case: title, opponent, dates and a deadline with reminder.
  const save = async (outcome, given) => {
    try {
      let target = caseItem;
      const kindLabel = outcome.kind.label;
      const title = `${kindLabel}${fields.creditor || fields.sender ? ` – ${fields.creditor || fields.sender}` : ""}`.slice(0, 120);
      const description = `${outcome.summary}\n\nAngelegt mit dem Brief-Assistenten.${text ? `\n\nBrieftext (Auszug):\n${text.slice(0, 2500)}` : ""}`.slice(0, 4000);
      // Post from a court or authority: the sender is the court, the opponent is the party behind the letter.
      const official = /gericht|mahngericht/i.test(fields.sender || "") || outcome.kind.stage === "court";
      const courtLine = official ? [fields.court || fields.sender, fields.sender_address].filter(Boolean).join(", ") : "";
      const details = {
        ...(target?.details || { audience: user.audience, client_name: user.organisation || user.full_name, client_email: user.email }),
        client_role: "respondent", opponent_name: (fields.creditor || (official ? "" : fields.sender) || "").slice(0, 160), opponent_address: (fields.creditor || official ? "" : fields.sender_address || "").slice(0, 500),
        opponent_reference: official ? "" : (fields.reference || "").slice(0, 100), court_reference: official ? (fields.reference || "").slice(0, 100) : (target?.details?.court_reference || ""), legal_area: outcome.kind.legal_area, stage: outcome.kind.stage,
        received_on: given.received_on || null, deadline: outcome.deadline?.date || null,
        deadline_note: outcome.deadline ? `${outcome.deadline.label} (${outcome.deadline.norm})`.slice(0, 300) : "",
        dispute_value: fields.amount ? Number(fields.amount) : null, court: official ? courtLine.slice(0, 160) : (target?.details?.court || ""),
        objective: outcome.steps[0]?.slice(0, 2000) || "",
      };
      target = target ? await storage.updateCase(target.id, { title, description, language: "de", details })
        : await storage.createCase({ title, description, language: "de", details });
      const deadlines = [outcome.deadline && { title: outcome.deadline.label, date: outcome.deadline.date, note: `${outcome.deadline.basis} ${outcome.deadline.norm}`, strict: outcome.deadline.strict }, ...outcome.extra_deadlines.map(item => ({ title: item.label, date: item.date, note: "", strict: false }))].filter(Boolean);
      for (const item of deadlines) {
        if (item.date < today) continue;
        const daysLeft = Math.round((new Date(item.date) - new Date(today)) / 86400000);
        target = await storage.saveTask(target.id, { title: item.title.slice(0, 200), note: item.note.slice(0, 2000), due_on: item.date, priority: "high", kind: item.strict ? "notfrist" : "deadline", pre_days: Math.max(0, Math.min(7, daysLeft - 1)) });
      }
      setCaseItem(target); setSaved(target);
    } catch {
      setError("Das Ergebnis wird angezeigt, konnte aber nicht in der Akte gespeichert werden.");
    }
  };

  const openSample = sample => import("./documentSamples.js").then(({ sampleContext }) => onDraft({ body: sample.body(sampleContext(saved || caseItem)), language: "de", kind: sample.kind, recipient: "" }, saved || caseItem));

  const question = questions[questionIndex];
  const answered = question && (question.optional || answers[question.id]);

  return <section className="letter-assistant">
    {step === "start" && <>
      <div className="la-hero"><IconMailOpened size={40} stroke={1.3} /><div><h2>Ich habe einen Brief bekommen</h2><p>Laden Sie den Brief hoch. Wir lesen die wichtigsten Angaben heraus, Sie bestätigen sie, beantworten ein paar Fragen – und erhalten die Frist, die nächsten Schritte und einen Antwortentwurf.</p></div></div>
      {error && <p role="alert" className="la-error">{error}</p>}
      <div className="la-choices">
        <button className="la-choice" onClick={() => fileInput.current?.click()}><IconCamera size={30} stroke={1.4} /><strong>Foto oder PDF hochladen</strong><small>Handyfoto genügt. JPG, PNG oder PDF bis 10 MB.</small></button>
        <button className="la-choice" onClick={() => setTyping(true)}><IconKeyboard size={30} stroke={1.4} /><strong>Text abtippen oder einfügen</strong><small>Wenn Sie den Brief als E-Mail oder Text haben.</small></button>
      </div>
      <input ref={fileInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={event => { startWithFile(event.target.files?.[0]); event.target.value = ""; }} />
      {typing && <div className="la-card"><label>Text des Briefs<textarea rows={10} value={pasted} onChange={event => setPasted(event.target.value)} placeholder="Absender, Datum, Betreff und den Text des Briefs hier einfügen …" /></label>
        <div className="la-actions"><button className="desk-button solid" disabled={pasted.trim().length < 20} onClick={startWithText}>Auswerten<IconArrowRight size={17} /></button><button className="desk-link" onClick={() => setTyping(false)}>Abbrechen</button></div></div>}
      {upcoming.length > 0 && <div className="la-card"><h3><IconCalendarDue size={19} />Ihre nächsten Fristen</h3><ul className="la-deadlines">{upcoming.map(row => <li key={row.id} className={row.due_on <= today ? "due" : ""}><button className="desk-link" onClick={() => open(row.caseItem.id, "tasks")}><strong>{dateLabel(row.due_on, "de")}</strong> {row.title} <small>{row.caseItem.title}</small></button></li>)}</ul></div>}
      <p className="la-more"><button className="desk-link" onClick={onShowAll}>Alle Funktionen anzeigen (Akten, Vorlagen, Recherche …)</button></p>
    </>}

    {(step === "reading" || step === "evaluating") && <div className="la-card la-busy" role="status"><IconLoader2 className="la-spin" size={30} />{step === "reading" ? progress : "Ergebnis wird berechnet …"}</div>}

    {step === "confirm" && <form className="la-card" onSubmit={confirm}>
      <p className="la-step">Schritt 1 von 3 · Angaben prüfen</p><h2>Stimmt das so?</h2>
      <p>Bitte prüfen Sie, was wir aus dem Brief gelesen haben, und korrigieren Sie es bei Bedarf.</p>
      {error && <p role="alert" className="la-error">{error}</p>}
      <label>Art des Schreibens<select value={kind} onChange={event => { setKind(event.target.value); setLegalArea(kinds.find(item => item.id === event.target.value)?.legal_area || ""); }}>{kinds.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <div className="la-grid">{FIELD_LABELS.map(([id, label, type]) => <label key={id}>{label}<input type={type || "text"} step={type === "number" ? "0.01" : undefined} min={type === "number" ? 0 : undefined} value={fields[id] ?? ""} onChange={event => setFields({ ...fields, [id]: event.target.value })} /></label>)}</div>
      {text && <details className="la-text"><summary>Erkannten Text anzeigen</summary><pre>{text}</pre></details>}
      <div className="la-actions"><button className="desk-button solid"><IconCheck size={17} />Ja, stimmt – weiter</button><button type="button" className="desk-link" onClick={reset}>Abbrechen</button></div>
    </form>}

    {step === "questions" && question && <div className="la-card">
      <p className="la-step">Schritt 2 von 3 · Frage {questionIndex + 1} von {questions.length}</p>
      <div className="la-progress"><span style={{ width: `${((questionIndex + 1) / questions.length) * 100}%` }} /></div>
      <h2>{question.label}</h2>{question.help && <p className="field-help">{question.help}</p>}
      {error && <p role="alert" className="la-error">{error}</p>}
      {question.type === "date" ? <div className="la-date"><input type="date" max={question.id === "received_on" ? today : undefined} value={answers[question.id] || ""} onChange={event => answer(question.id, event.target.value)} />
        {question.id === "received_on" && <button type="button" className="desk-link" onClick={() => answer(question.id, today)}>Heute</button>}</div>
        : <div className="la-options">{question.options.map(([value, label]) => <button key={value} type="button" className={answers[question.id] === value ? "la-option chosen" : "la-option"} onClick={() => answer(question.id, value)}>{label}</button>)}</div>}
      <div className="la-actions"><button className="desk-link" onClick={() => questionIndex ? setQuestionIndex(questionIndex - 1) : setStep("confirm")}><IconArrowLeft size={16} />Zurück</button>
        <button className="desk-button solid" disabled={!answered} onClick={nextQuestion}>{questionIndex + 1 < questions.length ? "Weiter" : "Ergebnis anzeigen"}<IconArrowRight size={17} /></button></div>
    </div>}

    {step === "result" && result && <div className="la-result">
      <div className="la-card"><p className="la-step">Schritt 3 von 3 · Ergebnis</p><h2>{result.kind.label}</h2><p>{result.summary}</p>{fields.amount ? <p><strong>Betrag:</strong> {euro(fields.amount)}</p> : null}</div>
      {result.deadline ? <div className={`la-deadline ${result.urgency}`}><IconCalendarDue size={34} stroke={1.4} /><div>
        <span>{result.deadline.label}{result.deadline.strict ? " · gesetzliche Frist" : ""}</span>
        <strong>{dateLabel(result.deadline.date, "de")}</strong>
        <small>{result.deadline.days_left < 0 ? `seit ${-result.deadline.days_left} Tagen abgelaufen – sofort handeln und Rat einholen` : result.deadline.days_left === 0 ? "heute!" : `noch ${result.deadline.days_left} Tage`} · {result.deadline.norm}</small>
        <p>{result.deadline.basis}</p></div></div>
        : <div className="la-card"><p><IconCalendarDue size={18} /> Für dieses Schreiben gibt es keine feste gesetzliche Frist. Reagieren Sie trotzdem zeitnah.</p></div>}
      {result.extra_deadlines.length > 0 && <div className="la-card"><h3>Weitere Termine</h3><ul className="la-deadlines">{result.extra_deadlines.map(item => <li key={item.label}><strong>{dateLabel(item.date, "de")}</strong> {item.label}</li>)}</ul></div>}
      <div className="la-card"><h3>Was Sie jetzt tun sollten</h3><ol className="la-steps">{result.steps.map(item => <li key={item}>{item}</li>)}</ol>
        {result.warnings.map(item => <p key={item} className="la-warning"><IconAlertTriangle size={18} />{item}</p>)}
        {result.lawyer && <p className="la-lawyer"><IconScale size={18} /><span><strong>Anwaltliche Hilfe:</strong> {result.lawyer}</span></p>}</div>
      {samples.length > 0 && <div className="la-card"><h3>Antwort vorbereiten</h3><p>Der Entwurf ist bereits mit Ihren Angaben ausgefüllt. Prüfen und ergänzen Sie die Stellen in [eckigen Klammern].</p>
        <div className="la-samples">{samples.map(sample => <button key={sample.id} className="desk-button" disabled={!saved && !caseItem} onClick={() => openSample(sample)}><IconEdit size={17} />{sample.title}</button>)}</div></div>}
      {error && <p role="alert" className="la-error">{error}</p>}
      <div className="la-card la-saved">{saved ? <p><IconFolder size={18} /> Gespeichert in der Akte <strong>{saved.title}</strong>{result.deadline && result.deadline.date >= today ? " – mit Frist und Erinnerung im Kalender." : "."}</p> : <p role="status">Wird in Ihrer Akte gespeichert …</p>}
        <div className="la-actions">{saved && <button className="desk-button" onClick={() => open(saved.id, "overview")}><IconFolder size={17} />Akte öffnen</button>}<button className="desk-button solid" onClick={reset}><IconMailOpened size={17} />Weiteren Brief prüfen</button></div></div>
      <p className="la-disclaimer">{result.disclaimer}</p>
    </div>}
  </section>;
}
