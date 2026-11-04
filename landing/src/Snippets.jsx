import { useEffect, useState } from "react";
import { IconPlus } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const PLACEHOLDERS = [["{mandant}", "Name der eigenen Partei"], ["{gegner}", "Name der Gegenseite"], ["{aktenzeichen}", "unser Aktenzeichen"], ["{az_gericht}", "gerichtliches Aktenzeichen"], ["{gericht}", "Gericht"], ["{angelegenheit}", "Bezeichnung der Akte"], ["{datum}", "heutiges Datum"]];

// Placeholders in a text block, filled from the case; unknown values stay visible as [..] for review.
export function fillSnippet(body, item) {
  const d = item?.details || {};
  const values = { mandant: d.client_name, gegner: d.opponent_name, aktenzeichen: item?.reference, az_gericht: d.court_reference, gericht: d.court?.split(",")[0], angelegenheit: item?.title, datum: new Date().toLocaleDateString("de-DE") };
  return body.replace(/\{(mandant|gegner|aktenzeichen|az_gericht|gericht|angelegenheit|datum)\}/g, (_, key) => values[key] || `[${key}]`);
}

// Drop-down in the draft editor: inserts a text block at the cursor.
export function SnippetInsert({ caseItem, onInsert, disabled }) {
  const [items, setItems] = useState([]);
  useEffect(() => { request("/snippets").then(setItems).catch(() => setItems([])); }, []);
  if (!items.length) return null;
  return <label className="snippet-insert">Textbaustein einfügen<select value="" disabled={disabled} onChange={event => { const item = items.find(s => s.id === event.target.value); if (item) onInsert(fillSnippet(item.body, caseItem)); }}>
    <option value="">— auswählen —</option>{items.map(s => <option key={s.id} value={s.id}>{s.category ? `${s.category}: ` : ""}{s.title}</option>)}</select></label>;
}

// Managing the office's own text blocks.
export function SnippetManager() {
  const [items, setItems] = useState([]), [form, setForm] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => { request("/snippets").then(setItems).catch(() => setError("Textbausteine nicht erreichbar.")); }, []);
  const save = async event => {
    event.preventDefault(); setBusy(true); setError("");
    try { setItems(await request(form.id ? `/snippets/${form.id}` : "/snippets", json(form.id ? "PUT" : "POST", { title: form.title, category: form.category, body: form.body }))); setForm(null); }
    catch { setError("Speichern fehlgeschlagen: Titel und Text brauchen mindestens 2 Zeichen."); } finally { setBusy(false); }
  };
  const remove = async id => { setBusy(true); try { await request(`/snippets/${id}`, { method: "DELETE" }); setItems(items.filter(s => s.id !== id)); } finally { setBusy(false); } };
  return <section className="desk-panel snippet-manager">
    <div className="desk-panel-heading"><div><h2>Eigene Textbausteine</h2><p>Einmal anlegen, im Schriftsatz-Editor per Auswahl einfügen</p></div>
      {!form && <button className="desk-button solid" onClick={() => setForm({ title: "", category: "", body: "" })}><IconPlus size={16} />Neuer Textbaustein</button>}</div>
    {form && <form className="admin-card" onSubmit={save}>
      <div className="cost-form-grid"><label>Titel *<input required minLength={2} maxLength={120} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="z. B. Schlussformel Klage" /></label>
        <label>Gruppe<input maxLength={60} value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} placeholder="z. B. Arbeitsrecht" /></label></div>
      <label>Text *<textarea required rows={6} maxLength={10000} value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} /></label>
      <p className="field-help">Platzhalter: {PLACEHOLDERS.map(([key, label]) => <span key={key}><code>{key}</code> {label}; </span>)}</p>
      {error && <p role="alert" className="storage-error">{error}</p>}
      <div className="sample-actions"><button className="desk-button solid" disabled={busy}>Speichern</button><button type="button" className="desk-link" onClick={() => setForm(null)}>Abbrechen</button></div>
    </form>}
    {items.length ? <ul className="admin-list">{items.map(s => <li key={s.id}><strong>{s.category ? `${s.category}: ` : ""}{s.title}</strong><small>{s.body.slice(0, 140)}{s.body.length > 140 ? " …" : ""}</small>
      <button className="desk-link" onClick={() => setForm(s)}>Bearbeiten</button> <button className="desk-link desk-delete" disabled={busy} onClick={() => remove(s.id)}>Löschen</button></li>)}</ul>
      : !form && <p className="desk-empty">Noch keine eigenen Textbausteine.</p>}
  </section>;
}
