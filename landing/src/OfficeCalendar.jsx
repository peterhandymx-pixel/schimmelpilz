import { useEffect, useMemo, useState } from "react";
import { IconChevronLeft, IconChevronRight, IconCalendarPlus, IconFileTypePdf, IconCalendarDown, IconAlertTriangle } from "@tabler/icons-react";
import { API_BASE, request, readPreference, writePreference } from "./useCaseStorage.js";
import { localToday, taskRows } from "./workbench.js";
import { TASK_KINDS } from "./DeskComponents.jsx";
import "./tools.css";

const STATE_KEY = "schimmelpilz.deadlineState";
const STATES = [["BW", "Baden-Württemberg"], ["BY", "Bayern"], ["BE", "Berlin"], ["BB", "Brandenburg"], ["HB", "Bremen"], ["HH", "Hamburg"], ["HE", "Hessen"], ["MV", "Mecklenburg-Vorpommern"], ["NI", "Niedersachsen"], ["NW", "Nordrhein-Westfalen"], ["RP", "Rheinland-Pfalz"], ["SL", "Saarland"], ["SN", "Sachsen"], ["ST", "Sachsen-Anhalt"], ["SH", "Schleswig-Holstein"], ["TH", "Thüringen"]];
const KINDS = ["notfrist", "deadline", "pre", "appointment", "resubmission", "task"];
const ORDER = Object.fromEntries(KINDS.map((kind, index) => [kind, index]));
const WEEKDAYS = { de: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] };

const iso = day => `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
const parse = value => new Date(value + "T12:00:00");
const shift = (value, days) => { const day = parse(value); day.setDate(day.getDate() + days); return iso(day); };
const monday = value => shift(value, -((parse(value).getDay() + 6) % 7));
const firstOfMonth = value => value.slice(0, 8) + "01";
const addMonths = (value, months) => { const day = parse(firstOfMonth(value)); day.setMonth(day.getMonth() + months); return iso(day); };
// ISO 8601 calendar week: the week with the year's first Thursday is week 1.
const isoWeek = value => { const day = parse(value); day.setDate(day.getDate() + 3 - ((day.getDay() + 6) % 7)); const first = new Date(day.getFullYear(), 0, 4, 12); return 1 + Math.round(((day - first) / 864e5 - 3 + ((first.getDay() + 6) % 7)) / 7); };

// Office calendar: every dated entry of all case files, with pre-deadlines and public holidays.
export function OfficeCalendar({ cases, lang, open, saveTask }) {
  const de = lang === "de", today = localToday(), locale = de ? "de-DE" : "en-GB";
  const [view, setView] = useState(() => readPreference("schimmelpilz.calendarView") || "month");
  const [anchor, setAnchor] = useState(today), [selected, setSelected] = useState(today);
  const [hidden, setHidden] = useState(() => new Set()), [showDone, setShowDone] = useState(false);
  const [state, setState] = useState(() => readPreference(STATE_KEY) || "");
  const [holidays, setHolidays] = useState({});
  const kindName = kind => kind === "pre" ? (de ? "Vorfrist" : "Pre-deadline") : TASK_KINDS[lang][kind];
  const changeView = id => { setView(id); writePreference("schimmelpilz.calendarView", id); };

  const active = cases.filter(item => !item.archived_at);
  const entries = useMemo(() => {
    const list = [];
    for (const row of taskRows(active)) {
      if (!row.due_on || (row.completed && !showDone)) continue;
      const kind = row.kind || "task";
      list.push({ key: row.id, day: row.due_on, time: row.due_time || "", kind, title: row.title, reference: row.caseItem.reference, caseId: row.caseItem.id, done: row.completed });
      if (row.pre_due_on && !row.completed) list.push({ key: "pre-" + row.id, day: row.pre_due_on, time: "", kind: "pre", title: row.title, reference: row.caseItem.reference, caseId: row.caseItem.id, due: row.due_on });
    }
    for (const item of active) {
      if (item.details?.deadline && item.details.status !== "closed") list.push({ key: "case-" + item.id, day: item.details.deadline, time: "", kind: "deadline", title: item.details.deadline_note || (de ? "Aktenfrist" : "Case deadline"), reference: item.reference, caseId: item.id });
    }
    return list;
  }, [cases, showDone, de]);
  const visible = entries.filter(entry => !hidden.has(entry.kind));
  const byDay = useMemo(() => {
    const map = {};
    for (const entry of visible) (map[entry.day] ||= []).push(entry);
    for (const list of Object.values(map)) list.sort((a, b) => ORDER[a.kind] - ORDER[b.kind] || (a.time || "99").localeCompare(b.time || "99"));
    return map;
  }, [visible]);

  // Visible days for each view.
  const monthStart = firstOfMonth(anchor);
  const days = view === "month" ? Array.from({ length: 42 }, (_, index) => shift(monday(monthStart), index))
    : view === "week" ? Array.from({ length: 7 }, (_, index) => shift(monday(anchor), index))
    : Array.from({ length: 31 }, (_, index) => shift(anchor, index));
  const first = days[0], last = days[days.length - 1];
  const years = [...new Set([first.slice(0, 4), last.slice(0, 4)])].join(",");

  useEffect(() => {
    let alive = true;
    Promise.all(years.split(",").map(year => request(`/deadlines/holidays?year=${year}${state ? `&state=${state}` : ""}`).catch(() => [])))
      .then(lists => { if (alive) setHolidays(Object.fromEntries(lists.flat().map(item => [item.date, item.name]))); });
    return () => { alive = false; };
  }, [years, state]);

  const step = direction => {
    if (view === "month") setAnchor(addMonths(anchor, direction));
    else setAnchor(shift(anchor, direction * (view === "week" ? 7 : 31)));
  };
  const goToday = () => { setAnchor(today); setSelected(today); };
  const title = view === "month" ? parse(monthStart).toLocaleDateString(locale, { month: "long", year: "numeric" })
    : view === "week" ? `${de ? "KW" : "Week"} ${isoWeek(first)} · ${parse(first).toLocaleDateString(locale, { day: "2-digit", month: "2-digit" })} – ${parse(last).toLocaleDateString(locale)}`
    : `${parse(first).toLocaleDateString(locale)} – ${parse(last).toLocaleDateString(locale)}`;
  const overdue = entries.filter(entry => entry.day < today && !entry.done && entry.kind !== "pre").length;
  const late = visible.filter(entry => entry.day < today && !entry.done && entry.kind !== "pre").sort((a, b) => a.day.localeCompare(b.day));
  const soon = entries.filter(entry => ["notfrist", "deadline"].includes(entry.kind) && !entry.done && entry.day >= today && entry.day <= shift(today, 7)).length;
  const bookRange = view === "month" ? [monthStart, shift(addMonths(monthStart, 1), -1)] : [first, last];

  const toggle = kind => setHidden(current => { const next = new Set(current); next.has(kind) ? next.delete(kind) : next.add(kind); return next; });
  const pick = day => { setSelected(day); if (view === "month" && day.slice(0, 7) !== monthStart.slice(0, 7)) setAnchor(day); };
  const dayClass = day => ["cal2-day", day === today && "today", day === selected && "selected", day < today && "past", holidays[day] && "holiday",
    [0, 6].includes(parse(day).getDay()) && "weekend", view === "month" && day.slice(0, 7) !== monthStart.slice(0, 7) && "outside"].filter(Boolean).join(" ");
  const chip = entry => <button key={entry.key} type="button" className={`cal2-chip kind-${entry.kind}${entry.done ? " done" : ""}`} title={`${kindName(entry.kind)} · ${entry.reference} · ${entry.title}${entry.due ? ` · ${de ? "Fristablauf" : "expires"} ${parse(entry.due).toLocaleDateString(locale)}` : ""}`}
    onClick={event => { event.stopPropagation(); open(entry.caseId, "tasks"); }}>{entry.time && <b>{entry.time}</b>}{entry.title}</button>;

  return <section className="desk-panel cal2">
    <header className="cal2-head">
      <div className="cal2-title"><h2>{title}</h2>
        <p>{de ? "Fristen, Termine und Wiedervorlagen aller Akten" : "Deadlines, appointments and follow-ups across all files"}
          {overdue > 0 && <span className="cal2-alert"><IconAlertTriangle size={14} />{overdue} {de ? "überfällig" : "overdue"}</span>}
          {soon > 0 && <span className="cal2-soon">{soon} {de ? "Fristen in 7 Tagen" : "deadlines within 7 days"}</span>}</p></div>
      <div className="cal2-nav">
        <button className="cal2-icon" aria-label={de ? "Zurück" : "Back"} onClick={() => step(-1)}><IconChevronLeft size={18} /></button>
        <button className="cal2-today" onClick={goToday}>{de ? "Heute" : "Today"}</button>
        <button className="cal2-icon" aria-label={de ? "Weiter" : "Next"} onClick={() => step(1)}><IconChevronRight size={18} /></button>
        <div className="cal2-views" role="group" aria-label={de ? "Ansicht" : "View"}>{[["month", de ? "Monat" : "Month"], ["week", de ? "Woche" : "Week"], ["agenda", de ? "Liste" : "List"]].map(([id, label]) =>
          <button key={id} aria-pressed={view === id} className={view === id ? "active" : ""} onClick={() => changeView(id)}>{label}</button>)}</div>
      </div>
    </header>

    <div className="cal2-toolbar">
      <div className="cal2-legend">{KINDS.map(kind => <button key={kind} type="button" aria-pressed={!hidden.has(kind)} className={`cal2-filter kind-${kind}${hidden.has(kind) ? " off" : ""}`} onClick={() => toggle(kind)}><i />{kindName(kind)}</button>)}</div>
      <div className="cal2-options">
        <label className="desk-checkbox"><input type="checkbox" checked={showDone} onChange={event => setShowDone(event.target.checked)} />{de ? "Erledigte" : "Completed"}</label>
        <select aria-label={de ? "Feiertage" : "Holidays"} value={state} onChange={event => { setState(event.target.value); writePreference(STATE_KEY, event.target.value); }}>
          <option value="">{de ? "Feiertage: bundesweit" : "Holidays: nationwide"}</option>{STATES.map(([id, name]) => <option key={id} value={id}>{de ? "Feiertage: " : "Holidays: "}{name}</option>)}</select>
        <a className="desk-button" href={`${API_BASE}/api/tasks/deadline-book.pdf?start=${bookRange[0]}&end=${bookRange[1]}`}><IconFileTypePdf size={16} />{de ? "Fristenbuch" : "Deadline book"}</a>
        <a className="desk-button" href={`${API_BASE}/api/tasks/calendar.ics?lang=${lang}&alarm_days=1`} title={de ? "Für Outlook, Google- oder Handy-Kalender" : "For Outlook, Google or phone calendar"}><IconCalendarDown size={16} />.ics</a>
      </div>
    </div>

    <div className={`cal2-body${view === "agenda" ? " agenda" : ""}`}>
      {view !== "agenda" && <div className={`cal2-grid ${view}`}>
        <div className="cal2-weekdays"><span className="cal2-kw">{de ? "KW" : "Wk"}</span>{WEEKDAYS[lang].map(name => <span key={name}>{name}</span>)}</div>
        {Array.from({ length: days.length / 7 }, (_, week) => <div className="cal2-week" key={days[week * 7]}>
          <span className="cal2-kw">{isoWeek(days[week * 7])}</span>
          {days.slice(week * 7, week * 7 + 7).map(day => {
            const list = byDay[day] || [], limit = view === "month" ? 3 : 50;
            return <div key={day} role="button" tabIndex={0} className={dayClass(day)} onClick={() => pick(day)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); pick(day); } }} aria-label={parse(day).toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" }) + (list.length ? `, ${list.length} ${de ? "Einträge" : "entries"}` : "")}>
              <div className="cal2-date"><span className="cal2-num">{parse(day).getDate()}</span>{holidays[day] && <span className="cal2-holiday">{holidays[day]}</span>}</div>
              <div className="cal2-chips">{list.slice(0, limit).map(chip)}{list.length > limit && <span className="cal2-more">+{list.length - limit} {de ? "weitere" : "more"}</span>}</div>
              {list.length > 0 && <div className="cal2-dots" aria-hidden="true">{list.slice(0, 5).map(entry => <i key={entry.key} className={`kind-${entry.kind}`} />)}</div>}
            </div>;
          })}
        </div>)}
      </div>}

      {view === "agenda" && <div className="cal2-agenda">{first === today && late.length > 0 && <div className="cal2-agenda-day late">
          <div className="cal2-agenda-date"><strong>!</strong><span>{de ? "überfällig" : "overdue"}</span></div>
          <div>{late.map(entry => <button key={entry.key} className={`cal2-row kind-${entry.kind}`} onClick={() => open(entry.caseId, "tasks")}>
            <span className="cal2-row-kind">{kindName(entry.kind)} · {parse(entry.day).toLocaleDateString(locale)}</span><span className="cal2-row-title">{entry.title}</span><small>{entry.reference}</small></button>)}</div>
        </div>}{days.filter(day => byDay[day] || holidays[day]).length === 0 && <p className="desk-empty">{de ? "Keine Einträge in den nächsten 31 Tagen." : "No entries in the next 31 days."}</p>}
        {days.filter(day => byDay[day] || holidays[day]).map(day => <div key={day} className={`cal2-agenda-day${day === today ? " today" : ""}`}>
          <div className="cal2-agenda-date"><strong>{parse(day).getDate()}</strong><span>{parse(day).toLocaleDateString(locale, { weekday: "short" })} · {parse(day).toLocaleDateString(locale, { month: "short" })}</span></div>
          <div>{holidays[day] && <span className="cal2-holiday">{holidays[day]}</span>}{(byDay[day] || []).map(entry => <button key={entry.key} className={`cal2-row kind-${entry.kind}${entry.done ? " done" : ""}`} onClick={() => open(entry.caseId, "tasks")}>
            <span className="cal2-row-kind">{entry.time ? entry.time + " · " : ""}{kindName(entry.kind)}</span><span className="cal2-row-title">{entry.title}</span><small>{entry.reference}{entry.due ? ` · ${de ? "Fristablauf" : "expires"} ${parse(entry.due).toLocaleDateString(locale)}` : ""}</small></button>)}</div>
        </div>)}</div>}

      <DayPanel day={selected} list={byDay[selected] || []} holiday={holidays[selected]} lang={lang} locale={locale} cases={active} saveTask={saveTask} open={open} kindName={kindName} today={today} />
    </div>
  </section>;
}

function DayPanel({ day, list, holiday, lang, locale, cases, saveTask, open, kindName, today }) {
  const de = lang === "de";
  const [caseId, setCaseId] = useState(cases[0]?.id || ""), [kind, setKind] = useState("appointment"), [title, setTitle] = useState(""), [time, setTime] = useState("09:00");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const weekend = [0, 6].includes(parse(day).getDay());
  const save = async event => {
    event.preventDefault();
    if (!caseId || title.trim().length < 3) return;
    setBusy(true); setMessage("");
    try {
      await saveTask(caseId, { title: title.trim(), note: "", due_on: day, priority: ["deadline", "notfrist"].includes(kind) ? "high" : "normal", kind, due_time: kind === "appointment" ? time : null, pre_days: null });
      setTitle(""); setMessage(de ? "Eingetragen." : "Saved.");
    } catch { setMessage(de ? "Konnte nicht gespeichert werden." : "Could not save."); }
    finally { setBusy(false); }
  };
  return <aside className="cal2-panel" aria-live="polite">
    <h3>{parse(day).toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</h3>
    {day === today && <span className="cal2-badge">{de ? "Heute" : "Today"}</span>}
    {holiday && <p className="cal2-panel-holiday">{de ? "Feiertag" : "Holiday"}: {holiday}</p>}
    {(holiday || weekend) && <p className="field-help">{de ? "Fällt ein Fristende auf diesen Tag, verschiebt es sich auf den nächsten Werktag (§ 193 BGB, § 222 Abs. 2 ZPO)." : "A deadline ending on this day moves to the next working day."}</p>}
    {list.length ? <ul className="cal2-panel-list">{list.map(entry => <li key={entry.key}><button className={`cal2-row kind-${entry.kind}${entry.done ? " done" : ""}`} onClick={() => open(entry.caseId, "tasks")}>
      <span className="cal2-row-kind">{entry.time ? entry.time + " · " : ""}{kindName(entry.kind)}</span><span className="cal2-row-title">{entry.title}</span><small>{entry.reference}{entry.due ? ` · ${de ? "Fristablauf" : "expires"} ${parse(entry.due).toLocaleDateString(locale)}` : ""}</small></button></li>)}</ul>
      : <p className="desk-empty">{de ? "Keine Einträge." : "No entries."}</p>}
    {saveTask && cases.length > 0 && <form className="cal2-add" onSubmit={save}><fieldset disabled={busy}>
      <h4><IconCalendarPlus size={16} />{de ? "Eintragen" : "Add"}</h4>
      <label>{de ? "Akte" : "File"}<select value={caseId} onChange={event => setCaseId(event.target.value)}>{cases.map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>
      <div className="cal2-add-row"><label>{de ? "Art" : "Type"}<select value={kind} onChange={event => setKind(event.target.value)}>{["appointment", "deadline", "notfrist", "resubmission", "task"].map(id => <option key={id} value={id}>{kindName(id)}</option>)}</select></label>
        {kind === "appointment" && <label>{de ? "Uhrzeit" : "Time"}<input type="time" value={time} required onChange={event => setTime(event.target.value)} /></label>}</div>
      <label>{de ? "Bezeichnung" : "Title"}<input value={title} minLength={3} maxLength={200} required placeholder={de ? "z. B. Termin Landgericht Köln" : "e.g. court hearing"} onChange={event => setTitle(event.target.value)} /></label>
      {["deadline", "notfrist"].includes(kind) && <p className="field-help">{de ? "Vorfrist: automatisch 7 Tage vorher (auf Werktag)." : "Pre-deadline: automatically 7 days earlier."}</p>}
      <button className="desk-button solid" disabled={busy || title.trim().length < 3}>{busy ? "…" : (de ? "Speichern" : "Save")}</button>
      {message && <p className="storage-notice">{message}</p>}
    </fieldset></form>}
  </aside>;
}
