import { useState } from "react";
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { localToday, taskRows } from "./workbench.js";
import { TASK_KINDS } from "./DeskComponents.jsx";

const VIEWS = { day: [1, "Tag", "Day"], week: [7, "Woche", "Week"], month: [28, "4 Wochen", "4 weeks"] };
const iso = day => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
const shift = (value, days) => { const day = new Date(value + "T12:00:00"); day.setDate(day.getDate() + days); return iso(day); };
// Weeks start on Monday.
const monday = value => { const day = new Date(value + "T12:00:00"); return shift(value, -((day.getDay() + 6) % 7)); };

// Office calendar: everything dated in the case files, with pre-deadlines, by day, week or four weeks.
export function OfficeCalendar({ cases, lang, open }) {
  const de = lang === "de", today = localToday();
  const [view, setView] = useState("week"), [anchor, setAnchor] = useState(today), [showDone, setShowDone] = useState(false);
  const [length] = VIEWS[view];
  const start = view === "day" ? anchor : monday(anchor);
  const days = Array.from({ length }, (_, index) => shift(start, index));
  const active = cases.filter(item => !item.archived_at);
  const entries = [];
  for (const row of taskRows(active)) {
    if (!row.due_on || (row.completed && !showDone)) continue;
    entries.push({ key: row.id, day: row.due_on, time: row.due_time || "", kind: row.kind || "task", title: row.title, reference: row.caseItem.reference, caseId: row.caseItem.id, done: row.completed });
    if (row.pre_due_on && !row.completed) entries.push({ key: "pre-" + row.id, day: row.pre_due_on, time: "", kind: "pre", title: row.title, reference: row.caseItem.reference, caseId: row.caseItem.id, due: row.due_on });
  }
  for (const item of active) {
    if (item.details?.deadline && item.details.status !== "closed") entries.push({ key: "case-" + item.id, day: item.details.deadline, time: "", kind: "deadline", title: item.details.deadline_note || (de ? "Aktenfrist" : "Case deadline"), reference: item.reference, caseId: item.id });
  }
  const order = { notfrist: 0, deadline: 1, pre: 2, appointment: 3, resubmission: 4, task: 5 };
  const byDay = day => entries.filter(entry => entry.day === day).sort((a, b) => (a.time || "99").localeCompare(b.time || "99") || order[a.kind] - order[b.kind]);
  const label = day => new Date(day + "T12:00:00").toLocaleDateString(de ? "de-DE" : "en-GB", { weekday: view === "month" ? "short" : "long", day: "2-digit", month: "2-digit" });
  const range = `${new Date(days[0] + "T12:00:00").toLocaleDateString(de ? "de-DE" : "en-GB")}${days.length > 1 ? ` – ${new Date(days[days.length - 1] + "T12:00:00").toLocaleDateString(de ? "de-DE" : "en-GB")}` : ""}`;
  const kindName = kind => kind === "pre" ? (de ? "Vorfrist" : "Pre-deadline") : TASK_KINDS[lang][kind];
  const overdue = entries.filter(entry => entry.day < today && !entry.done && entry.kind !== "pre").length;

  return <section className="desk-panel office-calendar">
    <div className="desk-panel-heading"><div><h2>{de ? "Kanzleikalender" : "Office calendar"}</h2><p>{de ? "Fristen, Notfristen, Vorfristen, Termine und Wiedervorlagen aller Akten" : "Deadlines, pre-deadlines, appointments and follow-ups across all cases"}{overdue ? <strong className="cal-overdue"> · {overdue} {de ? "überfällig" : "overdue"}</strong> : null}</p></div>
      <div className="cal-controls">
        <div className="cal-views">{Object.entries(VIEWS).map(([id, [, deLabel, enLabel]]) => <button key={id} className={view === id ? "active" : ""} aria-pressed={view === id} onClick={() => setView(id)}>{de ? deLabel : enLabel}</button>)}</div>
        <button className="desk-link" aria-label={de ? "Zurück" : "Back"} onClick={() => setAnchor(shift(anchor, -length))}><IconChevronLeft size={18} /></button>
        <button className="desk-button" onClick={() => setAnchor(today)}>{de ? "Heute" : "Today"}</button>
        <button className="desk-link" aria-label={de ? "Weiter" : "Next"} onClick={() => setAnchor(shift(anchor, length))}><IconChevronRight size={18} /></button>
        <span className="cal-range">{range}</span>
      </div></div>
    <label className="desk-checkbox"><input type="checkbox" checked={showDone} onChange={event => setShowDone(event.target.checked)} />{de ? "Erledigte anzeigen" : "Show completed"}</label>
    <div className={`cal-grid cal-view-${view}`}>
      {days.map(day => <div key={day} className={`cal-day${day === today ? " today" : ""}${day < today ? " past" : ""}${[0, 6].includes(new Date(day + "T12:00:00").getDay()) ? " weekend" : ""}`}>
        <div className="cal-date">{label(day)}</div>
        {byDay(day).map(entry => <button key={entry.key} className={`cal-entry kind-${entry.kind}${entry.done ? " done" : ""}`} onClick={() => open(entry.caseId, "tasks")} title={entry.kind === "pre" ? `${de ? "Fristablauf" : "Expires"} ${entry.due}` : ""}>
          <span className="cal-kind">{entry.time ? entry.time + " · " : ""}{kindName(entry.kind)}</span>
          <span className="cal-title">{entry.title}</span>
          <small>{entry.reference}</small>
        </button>)}
      </div>)}
    </div>
  </section>;
}
