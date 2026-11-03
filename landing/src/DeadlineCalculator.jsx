import { useState } from "react";
import { IconCalculator } from "@tabler/icons-react";
import { request, readPreference, writePreference } from "./useCaseStorage.js";
import { dateLabel, localToday } from "./workbench.js";
import "./account-settings.css";

import { DateInput } from "./DateInput";
const STATES = [["BW", "Baden-Württemberg"], ["BY", "Bayern"], ["BE", "Berlin"], ["BB", "Brandenburg"], ["HB", "Bremen"], ["HH", "Hamburg"], ["HE", "Hessen"], ["MV", "Mecklenburg-Vorpommern"], ["NI", "Niedersachsen"], ["NW", "Nordrhein-Westfalen"], ["RP", "Rheinland-Pfalz"], ["SL", "Saarland"], ["SN", "Sachsen"], ["ST", "Sachsen-Anhalt"], ["SH", "Schleswig-Holstein"], ["TH", "Thüringen"]];
const STATE_KEY = "schimmelpilz.deadlineState";

const copy = {
  de: {
    title: "Fristenrechner", intro: "Rechenhilfe nach §§ 187, 188 BGB mit Verschiebung auf den nächsten Werktag (§ 193 BGB, § 222 Abs. 2 ZPO). Welche Frist gilt, wann sie beginnt und ob Zustellungsfiktionen greifen, prüfen Sie selbst.",
    start: "Fristauslösendes Ereignis / Beginn *", amount: "Dauer *", unit: "Einheit", units: { days: "Tage", weeks: "Wochen", months: "Monate", years: "Jahre" },
    type: "Fristbeginn", event: "Ereignis im Laufe des Tages (z. B. Zustellung) – § 187 Abs. 1", dayStart: "Beginn eines Tages zählt mit – § 187 Abs. 2",
    state: "Bundesland für Feiertage (Ort des Gerichts / der Leistung)", federal: "Nur bundesweite Feiertage", shift: "Ende an Wochenende/Feiertag auf nächsten Werktag verschieben",
    calculate: "Berechnen", result: "Fristende", raw: "Rechnerisches Ende", first: "Erster Tag der Frist", moved: "Verschoben wegen", notMoved: "Keine Verschiebung nötig",
    task: "Als Aufgabe übernehmen", taskTitle: "Fristablauf", caseLabel: "Akte", saved: "Aufgabe angelegt.", failed: "Berechnung nicht möglich (unterstützt: 2015–2035).", saveFailed: "Aufgabe konnte nicht gespeichert werden.",
    limits: "Nicht berücksichtigt: rückwärts laufende Fristen, Stundenfristen, nur örtliche Feiertage (z. B. Augsburger Friedensfest, Mariä Himmelfahrt in Teilen Bayerns, Fronleichnam in Teilen Sachsens/Thüringens), gerichtliche Sondertage und Zustellungsfiktionen. Ergebnis immer selbst prüfen; Vorfrist einplanen.",
  },
  en: {
    title: "Deadline calculator", intro: "Calculation aid under §§ 187, 188 BGB with shifting to the next working day (§ 193 BGB, § 222(2) ZPO). Check yourself which period applies, when it starts and whether service fictions apply.",
    start: "Triggering event / start *", amount: "Duration *", unit: "Unit", units: { days: "days", weeks: "weeks", months: "months", years: "years" },
    type: "Period start", event: "Event during the day (e.g. service) – § 187(1)", dayStart: "Beginning of a day counts – § 187(2)",
    state: "State for public holidays (place of court / performance)", federal: "Nationwide holidays only", shift: "Move an end on a weekend/holiday to the next working day",
    calculate: "Calculate", result: "Period ends", raw: "Arithmetic end", first: "First day of the period", moved: "Moved because of", notMoved: "No shift needed",
    task: "Add as task", taskTitle: "Deadline expires", caseLabel: "Case", saved: "Task created.", failed: "Cannot calculate (supported: 2015–2035).", saveFailed: "Could not save the task.",
    limits: "Not covered: periods counted backwards, hour periods, local-only holidays (e.g. Augsburg peace festival, Assumption in parts of Bavaria, Corpus Christi in parts of Saxony/Thuringia), court closures and service fictions. Always check the result yourself and plan a preliminary deadline.",
  },
};

export function DeadlineCalculator({ lang, cases, caseId = "", saveTask }) {
  const c = copy[lang];
  const [result, setResult] = useState(null), [input, setInput] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [targetCase, setTargetCase] = useState(caseId || cases[0]?.id || "");
  const submit = async event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const payload = { start_date: values.start_date, amount: Number(values.amount), unit: values.unit, start_type: values.start_type, state: values.state || null, shift_non_working_days: values.shift === "on" };
    writePreference(STATE_KEY, values.state || "");
    setBusy(true); setError(""); setNotice("");
    try { setResult(await request("/deadlines/calculate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })); setInput(payload); }
    catch { setResult(null); setError(c.failed); }
    finally { setBusy(false); }
  };
  const addTask = async () => {
    if (!result || !targetCase) return;
    setBusy(true); setError(""); setNotice("");
    const note = `${input.amount} ${c.units[input.unit]} ab ${dateLabel(result.start, lang)} · ${result.start_rule}, ${result.rule}${result.shifted ? ` · ${c.moved}: ${result.skipped.map(item => item.reason).join(", ")}` : ""} · ${result.state_name} · ${lang === "de" ? "Rechenhilfe, selbst geprüft?" : "calculation aid, checked yourself?"}`;
    try { await saveTask(targetCase, { title: c.taskTitle, note: note.slice(0, 2000), due_on: result.end, priority: "high" }); setNotice(c.saved); }
    catch { setError(c.saveFailed); }
    finally { setBusy(false); }
  };
  return <section className="desk-panel deadline-calculator"><div className="desk-panel-heading"><div><h2><IconCalculator size={18} /> {c.title}</h2><p>{c.intro}</p></div></div>
    <form className="desk-task-form" onSubmit={submit}><fieldset disabled={busy}><div className="desk-form-grid">
      <label>{c.start}<DateInput name="start_date" required defaultValue={localToday()} /></label>
      <label>{c.amount}<input name="amount" type="number" min={1} max={1000} required defaultValue={2} /></label>
      <label>{c.unit}<select name="unit" defaultValue="weeks">{Object.entries(c.units).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>{c.type}<select name="start_type" defaultValue="event"><option value="event">{c.event}</option><option value="day_start">{c.dayStart}</option></select></label>
      <label>{c.state}<select name="state" defaultValue={readPreference(STATE_KEY) || ""}><option value="">{c.federal}</option>{STATES.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
    </div><label className="desk-checkbox"><input type="checkbox" name="shift" defaultChecked />{c.shift}</label>
    <div className="desk-form-actions"><button className="desk-button solid">{c.calculate}</button></div></fieldset></form>
    {error && <p className="storage-error" role="alert">{error}</p>}
    {result && <div className="deadline-result" role="status"><p><strong>{c.result}: {dateLabel(result.end, lang)}</strong> ({new Date(result.end + "T12:00:00").toLocaleDateString(lang === "de" ? "de-DE" : "en-GB", { weekday: "long" })})</p>
      <ul><li>{c.first}: {dateLabel(result.first_day, lang)} · {result.start_rule}</li><li>{c.raw}: {dateLabel(result.raw_end, lang)} · {result.rule}</li><li>{result.shifted ? `${c.moved}: ${result.skipped.map(item => `${dateLabel(item.date, lang)} ${item.reason}`).join(", ")}` : c.notMoved}</li><li>{result.state_name}</li></ul>
      {saveTask && cases.length > 0 && <div className="cost-actions">{!caseId && <label>{c.caseLabel}<select value={targetCase} onChange={event => setTargetCase(event.target.value)}>{cases.map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>}<button className="desk-button" disabled={busy || !targetCase} onClick={addTask}>{c.task}</button></div>}
      {notice && <p className="storage-notice">{notice}</p>}</div>}
    <p className="field-help">{c.limits}</p>
  </section>;
}
