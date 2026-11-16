import { useEffect, useState } from "react";
import { IconPhoneIncoming, IconPhoneOutgoing, IconUsers, IconVideo, IconNote, IconTrash } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { DateInput } from "./DateInput";
import "./tools.css";

const KINDS = [["call_in", "Anruf eingehend", IconPhoneIncoming], ["call_out", "Anruf ausgehend", IconPhoneOutgoing], ["meeting", "Besprechung", IconUsers], ["video", "Videogespräch", IconVideo], ["other", "Notiz", IconNote]];
const pad = value => String(value).padStart(2, "0");
const nowLocal = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const when = value => new Date(value).toLocaleString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

// Telephone and meeting notes: quick to record, listed newest first, optionally with a follow-up date.
export function CaseNotes({ item, onChanged, canDelete = false }) {
  const d = item.details || {};
  const [notes, setNotes] = useState([]), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const empty = { kind: "call_in", person: d.client_name || "", happened_at: nowLocal(), minutes: "", note: "", follow_up_on: "", follow_up_title: "" };
  const [form, setForm] = useState(empty);
  const set = (key, value) => setForm(previous => ({ ...previous, [key]: value }));
  useEffect(() => { request(`/cases/${item.id}/notes`).then(setNotes).catch(() => setError("Notizen konnten nicht geladen werden.")); }, [item.id]);
  const people = [...new Set([d.client_name, d.opponent_name, d.opponent_lawyer, d.court].filter(Boolean))];

  const save = async event => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const payload = { kind: form.kind, person: form.person, happened_at: form.happened_at, minutes: form.minutes ? Number(form.minutes) : null, note: form.note, follow_up_on: form.follow_up_on || null, follow_up_title: form.follow_up_title };
      setNotes(await request(`/cases/${item.id}/notes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }));
      setForm({ ...empty, happened_at: nowLocal() });
      if (payload.follow_up_on) onChanged?.();
    } catch { setError("Notiz konnte nicht gespeichert werden. Mindestens 3 Zeichen Text und gültige Zeit angeben."); }
    finally { setBusy(false); }
  };
  const remove = async note => {
    if (!window.confirm("Diese Notiz endgültig löschen?")) return;
    try { await request(`/cases/${item.id}/notes/${note.id}`, { method: "DELETE" }); setNotes(notes.filter(entry => entry.id !== note.id)); }
    catch { setError("Notiz konnte nicht gelöscht werden."); }
  };

  return <section className="desk-panel tool-panel">
    <div className="desk-panel-heading"><div><h2><IconPhoneIncoming size={18} /> Gesprächsnotizen</h2>
      <p>Telefonate und Besprechungen festhalten. Notizen erscheinen im Aktenverlauf und in der Volltextsuche.</p></div></div>
    <form className="note-form" onSubmit={save}><fieldset disabled={busy}>
      <div className="note-kinds" role="group" aria-label="Art">{KINDS.map(([id, label, Icon]) => <button key={id} type="button" aria-pressed={form.kind === id} className={form.kind === id ? "active" : ""} onClick={() => set("kind", id)}><Icon size={16} />{label}</button>)}</div>
      <div className="note-grid">
        <label>Gesprächspartner<input list={`people-${item.id}`} value={form.person} maxLength={200} onChange={event => set("person", event.target.value)} placeholder="Name" /><datalist id={`people-${item.id}`}>{people.map(name => <option key={name} value={name} />)}</datalist></label>
        <label>Zeitpunkt<input type="datetime-local" required value={form.happened_at} onChange={event => set("happened_at", event.target.value)} /></label>
        <label>Dauer (Min.)<input type="number" min={1} max={600} value={form.minutes} onChange={event => set("minutes", event.target.value)} /></label>
      </div>
      <label>Inhalt *<textarea required minLength={3} maxLength={10000} rows={4} value={form.note} onChange={event => set("note", event.target.value)} placeholder="Was wurde besprochen, was ist zu tun?" /></label>
      <div className="note-grid">
        <label>Wiedervorlage am (optional)<DateInput value={form.follow_up_on} onChange={event => set("follow_up_on", event.target.value)} /></label>
        {form.follow_up_on && <label className="span-two">Bezeichnung der Wiedervorlage<input value={form.follow_up_title} maxLength={200} onChange={event => set("follow_up_title", event.target.value)} placeholder="z. B. Unterlagen vom Mandanten da?" /></label>}
      </div>
      <button className="desk-button solid">{busy ? "…" : "Notiz speichern"}</button>
    </fieldset></form>
    {error && <p className="storage-error" role="alert">{error}</p>}
    {notes.length === 0 ? <p className="desk-empty">Noch keine Notizen in dieser Akte.</p> : <ol className="note-list">{notes.map(note => {
      const Icon = (KINDS.find(([id]) => id === note.kind) || KINDS[4])[2];
      return <li key={note.id}><span className="note-icon"><Icon size={17} /></span><div>
        <div className="note-meta"><strong>{note.kind_label}{note.person ? ` · ${note.person}` : ""}</strong><span>{when(note.happened_at)}{note.minutes ? ` · ${note.minutes} Min.` : ""}</span>
          {canDelete && <button className="note-delete" aria-label="Notiz löschen" onClick={() => remove(note)}><IconTrash size={15} /></button>}</div>
        <p>{note.note}</p></div></li>;
    })}</ol>}
  </section>;
}
