import { useEffect, useState } from "react";
import { IconExternalLink, IconFileText, IconPlus } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";
import { dateLabel, localToday } from "./workbench.js";
import { DateInput } from "./DateInput.jsx";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const euro = value => Number(value).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
const decimal = value => { const text = String(value || "").trim(); return text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : /^\d+\.\d{1,2}$/.test(text) ? text : text.replace(/\./g, ""); };
const MODES = { consumer: "5 %-Punkte über Basiszins (Verbraucher, § 288 Abs. 1 BGB)", business: "9 %-Punkte über Basiszins (Unternehmer, § 288 Abs. 2 BGB)", fixed: "Fester Zinssatz", none: "Keine Zinsen" };

// Claim account of one case: items, payments, § 367 BGB crediting and the statement for enforcement.
export function ClaimAccount({ cases, selectedCase }) {
  const active = cases.filter(item => !item.archived_at);
  const [caseId, setCaseId] = useState(selectedCase?.id && active.some(c => c.id === selectedCase.id) ? selectedCase.id : active[0]?.id || "");
  const [asOf, setAsOf] = useState(localToday()), [data, setData] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [item, setItem] = useState({ kind: "principal", description: "", amount: "", booked_on: localToday(), interest_mode: "consumer", interest_rate: "", interest_from: localToday() });
  const [payment, setPayment] = useState({ paid_on: localToday(), amount: "", note: "" });
  const load = () => caseId && request(`/cases/${caseId}/claim?as_of=${asOf}`).then(setData).catch(() => setError("Forderungskonto nicht erreichbar."));
  useEffect(() => { setData(null); load(); }, [caseId, asOf]);
  const act = async work => { setBusy(true); setError(""); try { await work(); await load(); return true; } catch (e) { setError(e.status === 422 ? "Eingaben prüfen: Betrag, Datum und bei Zinsen das Datum „Zinsen ab“." : "Speichern fehlgeschlagen."); return false; } finally { setBusy(false); } };
  const addItem = async event => { event.preventDefault(); if (await act(() => request(`/cases/${caseId}/claim/items`, json("POST", { ...item, amount: decimal(item.amount), interest_rate: item.interest_mode === "fixed" ? decimal(item.interest_rate) : null, interest_from: item.interest_mode === "none" ? null : item.interest_from })))) setItem({ ...item, description: "", amount: "" }); };
  const addPayment = async event => { event.preventDefault(); if (await act(() => request(`/cases/${caseId}/claim/payments`, json("POST", { ...payment, amount: decimal(payment.amount) })))) setPayment({ ...payment, amount: "", note: "" }); };
  const remove = (kind, id) => act(() => request(`/cases/${caseId}/claim/${kind}/${id}`, { method: "DELETE" }));
  const s = data?.statement;
  if (!active.length) return <section className="desk-panel"><p className="desk-empty">Zuerst eine Akte anlegen.</p></section>;

  return <section className="desk-panel claim-account">
    <div className="desk-panel-heading"><div><h2>Forderungskonto</h2><p>Hauptforderung, Kosten, Verzugszinsen und Zahlungen – verrechnet nach § 367 BGB</p></div></div>
    <div className="eakte-filter"><label>Akte<select value={caseId} onChange={e => setCaseId(e.target.value)}>{active.map(c => <option key={c.id} value={c.id}>{c.reference} · {c.title}</option>)}</select></label>
      <label>Stand<DateInput value={asOf} onChange={e => setAsOf(e.target.value || localToday())} /></label>
      {s && <a className="desk-button" href={`${API_BASE}/api/cases/${caseId}/claim/report.pdf?as_of=${asOf}`} target="_blank" rel="noreferrer"><IconFileText size={16} />Forderungsaufstellung (PDF)</a>}</div>
    {error && <p role="alert" className="storage-error">{error}</p>}
    {s && <div className="admin-tiles claim-totals">
      <div><strong>{euro(s.principal)}</strong><span>Hauptforderung</span></div>
      <div><strong>{euro(s.interest)}</strong><span>Zinsen bis {dateLabel(s.as_of, "de")}</span></div>
      <div><strong>{euro(s.costs)}</strong><span>Kosten</span></div>
      <div className="claim-sum"><strong>{euro(s.total)}</strong><span>Gesamtforderung</span></div>
      <div><strong>{euro(s.daily_interest)}</strong><span>Zinsen je weiterem Tag</span></div>
    </div>}
    {s?.rate_warning && <p className="storage-notice">Der Basiszinssatz ist nur bis {dateLabel(s.rate_table_until, "de")} hinterlegt; für spätere Zeiträume wird der letzte Wert ({s.base_rate_now.replace(".", ",")} %) angesetzt. Der neue Wert wird automatisch bei der Bundesbank abgerufen, sobald er veröffentlicht ist (in der Regel Ende Dezember bzw. Ende Juni).</p>}

    <div className="admin-columns">
      <form className="admin-card" onSubmit={addItem}><h3>Forderung oder Kosten erfassen</h3>
        <div className="cost-form-grid">
          <label>Art<select value={item.kind} onChange={e => setItem({ ...item, kind: e.target.value, interest_mode: e.target.value === "cost" ? "none" : item.interest_mode })}><option value="principal">Hauptforderung</option><option value="cost">Kosten (Mahn-, Inkasso-, Gerichts-, Anwaltskosten)</option></select></label>
          <label>Bezeichnung *<input required minLength={2} value={item.description} onChange={e => setItem({ ...item, description: e.target.value })} placeholder="z. B. Rechnung Nr. 4711" /></label>
          <label>Betrag EUR *<input required inputMode="decimal" value={item.amount} onChange={e => setItem({ ...item, amount: e.target.value })} /></label>
          <label>Datum / fällig am<DateInput value={item.booked_on} onChange={e => setItem({ ...item, booked_on: e.target.value })} /></label>
          <label className="claim-wide">Zinsen<select value={item.interest_mode} onChange={e => setItem({ ...item, interest_mode: e.target.value })}>{Object.entries(MODES).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
          {item.interest_mode === "fixed" && <label>Zinssatz % p. a.<input inputMode="decimal" value={item.interest_rate} onChange={e => setItem({ ...item, interest_rate: e.target.value })} /></label>}
          {item.interest_mode !== "none" && <label>Zinsen ab<DateInput value={item.interest_from} onChange={e => setItem({ ...item, interest_from: e.target.value })} /></label>}
        </div>
        <button className="desk-button solid" disabled={busy}><IconPlus size={16} />Erfassen</button></form>
      <form className="admin-card" onSubmit={addPayment}><h3>Zahlung des Schuldners erfassen</h3>
        <div className="cost-form-grid">
          <label>Eingang am<DateInput value={payment.paid_on} onChange={e => setPayment({ ...payment, paid_on: e.target.value })} /></label>
          <label>Betrag EUR *<input required inputMode="decimal" value={payment.amount} onChange={e => setPayment({ ...payment, amount: e.target.value })} /></label>
          <label>Vermerk<input value={payment.note} onChange={e => setPayment({ ...payment, note: e.target.value })} placeholder="z. B. Rate 1" /></label>
        </div>
        <button className="desk-button solid" disabled={busy}><IconPlus size={16} />Zahlung buchen</button>
        <p className="field-help">Verrechnung nach § 367 Abs. 1 BGB: zuerst Kosten, dann Zinsen, dann Hauptforderung.</p></form>
    </div>

    {s && <section className="admin-card"><h3>Kontoverlauf</h3>
      {s.entries.length ? <table className="desk-table"><thead><tr><th>Datum</th><th>Vorgang</th><th className="num">Betrag</th><th></th></tr></thead><tbody>
        {s.entries.map((entry, index) => <tr key={index}><td>{dateLabel(entry.day, "de")}</td><td>{entry.text}</td><td className="num">{euro(entry.amount)}</td><td></td></tr>)}
      </tbody></table> : <p className="desk-empty">Noch keine Forderungen erfasst.</p>}
      {data.items.length > 0 && <details><summary>Einträge bearbeiten / löschen</summary><ul className="admin-list">
        {data.items.map(row => <li key={row.id}>{row.kind === "principal" ? "Hauptforderung" : "Kosten"}: {row.description} – {euro(row.amount_minor / 100)} <button className="desk-link desk-delete" disabled={busy} onClick={() => remove("items", row.id)}>Löschen</button></li>)}
        {data.payments.map(row => <li key={row.id}>Zahlung {dateLabel(row.paid_on, "de")} – {euro(row.amount_minor / 100)} <button className="desk-link desk-delete" disabled={busy} onClick={() => remove("payments", row.id)}>Löschen</button></li>)}
      </ul></details>}
    </section>}

    <section className="admin-card"><h3>Zwangsvollstreckung</h3>
      <p>Für den Pfändungs- und Überweisungsbeschluss und den Vollstreckungsauftrag an den Gerichtsvollzieher sind die amtlichen Formulare Pflicht (ZVFV, GVFV). Die Forderungsaufstellung oben ist die passende Anlage dazu; Schuldner- und Gläubigerdaten stehen in der Akte.</p>
      <a className="desk-link" href="https://justiz.de/formulare/index.php" target="_blank" rel="noreferrer">Amtliche Formulare der Justiz <IconExternalLink size={14} /></a>
    </section>
    <p className="field-help">Zinsen taggenau (Tage/365), ohne Zinseszins (§ 289 BGB); Basiszinssatz nach § 247 BGB laut Bundesbank. Rechenhilfe – Ergebnis vor Verwendung prüfen.</p>
  </section>;
}
