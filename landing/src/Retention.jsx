import { useEffect, useState } from "react";
import { IconArchive, IconFileTypePdf, IconTrash } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";
import { dateLabel } from "./workbench.js";
import { DateInput } from "./DateInput";
import "./tools.css";

const ERRORS = { retention_period_running: "Die Aufbewahrungsfrist läuft noch.", case_reference_confirmation_required: "Zur Bestätigung genau das Aktenzeichen eingeben.",
  workspace_owner_required_for_deletion: "Nur die Kanzleiinhaberin / der Kanzleiinhaber darf Akten vernichten.", implausible_end_date: "Das Datum darf nicht in der Zukunft liegen." };

// Archived files with their retention period (§ 50 Abs. 1 BRAO) and destruction with a protocol.
export function Retention({ onChanged, canDelete }) {
  const [data, setData] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(""), [editing, setEditing] = useState(null), [confirming, setConfirming] = useState(null);
  const load = () => request("/retention").then(setData).catch(() => setError("Übersicht konnte nicht geladen werden."));
  useEffect(() => { load(); }, []);
  const act = async (id, work) => {
    setBusy(id); setError("");
    try { await work(); await load(); setEditing(null); setConfirming(null); }
    catch (failure) { setError(ERRORS[failure.detail] || "Aktion fehlgeschlagen."); }
    finally { setBusy(""); }
  };
  if (!data) return <section className="desk-panel">{error ? <p className="storage-error" role="alert">{error}</p> : <p role="status">Wird geladen …</p>}</section>;
  const ready = data.items.filter(item => item.destroyable).length;

  return <section className="desk-panel tool-panel">
    <div className="desk-panel-heading"><div><h2><IconArchive size={18} /> Aufbewahrung &amp; Aktenvernichtung</h2>
      <p>Handakten sind {data.years} Jahre nach Ablauf des Kalenderjahres aufzubewahren, in dem der Auftrag beendet wurde (§ 50 Abs. 1 BRAO). Als Ende gilt das Archivierungsdatum, wenn kein anderes Datum eingetragen ist.</p></div>
      <a className="desk-button" href={`${API_BASE}/api/retention/protocol.pdf`}><IconFileTypePdf size={16} />Vernichtungsprotokoll</a></div>
    {ready > 0 && <p className="storage-notice">{ready} {ready === 1 ? "Akte darf" : "Akten dürfen"} vernichtet werden.</p>}
    {error && <p className="storage-error" role="alert">{error}</p>}
    {data.items.length === 0 ? <p className="desk-empty">Keine archivierten Akten. Akten erscheinen hier, sobald sie archiviert sind.</p> :
      <div className="desk-table-scroll"><table className="desk-table retention-table"><thead><tr><th>Akte</th><th>Mandat beendet</th><th>Aufbewahren bis</th><th>Status</th><th></th></tr></thead><tbody>
        {data.items.map(item => <tr key={item.case_id}>
          <td><strong>{item.reference}</strong><small>{item.title}{item.client_name ? ` · ${item.client_name}` : ""}</small><small>{item.documents} Dokumente{item.open_tasks ? ` · ${item.open_tasks} offene Aufgaben` : ""}{item.invoices ? ` · ${item.invoices} Rechnungen (bleiben erhalten)` : ""}</small></td>
          <td>{editing === item.case_id ? <form className="invoice-inline" onSubmit={event => { event.preventDefault(); const value = new FormData(event.currentTarget).get("ended_on"); act(item.case_id, () => request(`/retention/${item.case_id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ended_on: value }) })); }}>
              <DateInput name="ended_on" required defaultValue={item.ended_on} /><button className="desk-button" disabled={busy === item.case_id}>OK</button><button type="button" className="desk-link" onClick={() => setEditing(null)}>Abbrechen</button></form>
            : <>{dateLabel(item.ended_on, "de")}<small>{item.ended_manually ? "eingetragen" : "Archivierung"} · <button className="desk-link" onClick={() => setEditing(item.case_id)}>ändern</button></small></>}</td>
          <td>{dateLabel(item.retained_until, "de")}</td>
          <td><span className={`retention-status ${item.destroyable ? "ready" : "running"}`}>{item.destroyable ? "Vernichtung möglich" : "Frist läuft"}</span></td>
          <td>{item.destroyable && canDelete && (confirming === item.case_id
            ? <form className="invoice-inline" onSubmit={event => { event.preventDefault(); const confirm = new FormData(event.currentTarget).get("confirm"); act(item.case_id, async () => { await request(`/retention/${item.case_id}/destroy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm }) }); onChanged?.(); }); }}>
                <input name="confirm" required placeholder={`${item.reference} eingeben`} aria-label="Aktenzeichen zur Bestätigung" /><button className="desk-button danger" disabled={busy === item.case_id}>Endgültig vernichten</button><button type="button" className="desk-link" onClick={() => setConfirming(null)}>Abbrechen</button></form>
            : <button className="desk-link desk-delete" onClick={() => setConfirming(item.case_id)}><IconTrash size={15} />Vernichten</button>)}</td>
        </tr>)}</tbody></table></div>}
    <p className="field-help">Beim Vernichten werden Akte, Dokumente, Entwürfe, Fristen und Notizen endgültig gelöscht; das lässt sich nicht rückgängig machen. Im Protokoll bleiben nur Aktenzeichen, Bezeichnung, Daten und Anzahl der Dokumente. Rechnungen und Buchungen werden nicht gelöscht (Aufbewahrung bis zu 10 Jahre nach § 147 AO).</p>
    {data.log.length > 0 && <><h3 className="retention-log-title">Bereits vernichtet</h3><ul className="form-list">{data.log.map(entry => <li key={entry.reference + entry.destroyed_at}><div><strong>{entry.reference} · {entry.title}</strong><small>vernichtet am {dateLabel(entry.destroyed_at, "de")} · aufbewahrt bis {dateLabel(entry.retained_until, "de")} · {entry.documents} Dokumente</small></div></li>)}</ul></>}
  </section>;
}
