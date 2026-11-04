import { useEffect, useMemo, useState } from "react";
import { IconDownload, IconFileInvoice, IconPlus, IconTrash } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";
import { dateLabel, localToday } from "./workbench.js";
import { DateInput } from "./DateInput.jsx";
import "./invoicing.css";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const euro = value => Number(value).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
const cents = minor => euro(minor / 100);
// German input: "10.000,50" or "1,3"; a lone dot with up to two decimals ("1.3") is read as a decimal point.
const decimal = value => { const text = String(value || "").trim(); return text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : /^\d+\.\d{1,2}$/.test(text) ? text : text.replace(/\./g, ""); };
const STATUS = { open: "offen", paid: "bezahlt", cancelled: "storniert" };
const KINDS = { rvg: "RVG-Rechnung", advance: "Vorschussrechnung (§ 9 RVG)", time: "Rechnung nach Zeitaufwand" };
const ERRORS = { value_outside_table: "Gegenstandswert außerhalb der RVG-Tabelle (bis 500.000 EUR).", no_unbilled_time: "Für diese Akte gibt es keine abzurechnenden Zeiten.", invoice_cancelled: "Die Rechnung ist storniert." };
const failure = error => ERRORS[error.detail] || (error.status === 422 ? "Eingaben prüfen: Beträge ohne Tausenderpunkt, Gebührensätze im zulässigen Rahmen." : "Aktion fehlgeschlagen.");
// Office details for the invoice footer stay in this browser only.
const remembered = key => { try { return localStorage.getItem("schimmelpilz-" + key) || ""; } catch { return ""; } };
const remember = (key, value) => { try { localStorage.setItem("schimmelpilz-" + key, value); } catch { /* storage unavailable */ } };

function InvoiceList({ cases, reloadKey }) {
  const [filter, setFilter] = useState("open"), [data, setData] = useState(null), [error, setError] = useState(""), [paying, setPaying] = useState(null), [busy, setBusy] = useState(false);
  const load = () => request(`/invoices?status=${filter}`).then(setData).catch(e => setError(failure(e)));
  useEffect(() => { load(); }, [filter, reloadKey]);
  const act = async work => { setBusy(true); setError(""); try { await work(); await load(); setPaying(null); } catch (e) { setError(failure(e)); } finally { setBusy(false); } };
  if (!data) return error ? <p role="alert" className="storage-error">{error}</p> : <p role="status">Rechnungen werden geladen …</p>;
  return <>
    <div className="eakte-filter"><label>Anzeigen<select value={filter} onChange={e => setFilter(e.target.value)}><option value="open">Offene Posten</option><option value="all">Alle Rechnungen</option><option value="paid">Bezahlt</option><option value="cancelled">Storniert</option></select></label>
      <span>Offen gesamt: <strong>{cents(data.open_total_minor)}</strong></span>
      <a className="desk-button" href={`${API_BASE}/api/invoices.csv`}><IconDownload size={16} />CSV</a></div>
    {error && <p role="alert" className="storage-error">{error}</p>}
    {data.invoices.length ? <div className="desk-table-scroll"><table className="desk-table invoice-table"><thead><tr><th>Nr.</th><th>Datum</th><th>Akte / Empfänger</th><th>Art</th><th>Betrag</th><th>Offen</th><th>Status</th><th></th></tr></thead><tbody>
      {data.invoices.map(item => <tr key={item.id} className={item.status === "cancelled" ? "invoice-cancelled" : ""}>
        <td><strong>{item.number}</strong></td><td>{dateLabel(item.issued_on, "de")}</td>
        <td>{item.case_reference}<small>{item.recipient.split("\n")[0]}</small></td><td>{KINDS[item.kind].split(" (")[0]}</td>
        <td>{cents(item.payable_minor)}</td><td>{item.status === "cancelled" ? "—" : cents(item.open_minor)}</td>
        <td><span className={`invoice-status ${item.status}`}>{STATUS[item.status]}</span>{item.payments.map((p, i) => <small key={i}>{dateLabel(p.paid_on, "de")}: {cents(p.amount_minor)}</small>)}{item.cancel_reason && <small>{item.cancel_reason}</small>}</td>
        <td className="invoice-actions"><a className="desk-link" href={`${API_BASE}/api/invoices/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF</a>
          {item.status === "open" && <button className="desk-link" onClick={() => setPaying({ id: item.id, amount: (item.open_minor / 100).toFixed(2).replace(".", ","), paid_on: localToday(), mode: "pay" })}>Zahlung erfassen</button>}
          {item.status !== "cancelled" && <button className="desk-link desk-delete" onClick={() => setPaying({ id: item.id, mode: "cancel", reason: "" })}>Stornieren</button>}
          {paying?.id === item.id && paying.mode === "pay" && <form className="invoice-inline" onSubmit={e => { e.preventDefault(); act(() => request(`/invoices/${item.id}/payments`, json("POST", { paid_on: paying.paid_on, amount: decimal(paying.amount), note: "" }))); }}>
            <DateInput value={paying.paid_on} onChange={e => setPaying({ ...paying, paid_on: e.target.value })} /><input aria-label="Betrag" value={paying.amount} onChange={e => setPaying({ ...paying, amount: e.target.value })} /><button className="desk-button solid" disabled={busy}>Buchen</button><button type="button" className="desk-link" onClick={() => setPaying(null)}>Abbrechen</button></form>}
          {paying?.id === item.id && paying.mode === "cancel" && <form className="invoice-inline" onSubmit={e => { e.preventDefault(); act(() => request(`/invoices/${item.id}/cancel`, json("POST", { reason: paying.reason }))); }}>
            <input required minLength={5} placeholder="Grund der Stornierung" value={paying.reason} onChange={e => setPaying({ ...paying, reason: e.target.value })} /><button className="desk-button danger" disabled={busy}>Stornieren</button><button type="button" className="desk-link" onClick={() => setPaying(null)}>Abbrechen</button></form>}
        </td></tr>)}
    </tbody></table></div> : <p className="desk-empty">Keine Rechnungen in dieser Auswahl.</p>}
    <p className="field-help">Stornierte Rechnungen behalten ihre Nummer und bleiben für die Buchhaltung erhalten. Bereits verrechnete Vorschüsse werden durch eine Stornierung wieder frei.</p>
  </>;
}

function NewInvoice({ cases, selectedCase, onCreated }) {
  const active = cases.filter(item => !item.archived_at);
  const [caseId, setCaseId] = useState(selectedCase?.id && active.some(c => c.id === selectedCase.id) ? selectedCase.id : active[0]?.id || "");
  const item = active.find(c => c.id === caseId);
  const [catalogue, setCatalogue] = useState(null);
  const [kind, setKind] = useState("rvg"), [issuedOn, setIssuedOn] = useState(localToday()), [period, setPeriod] = useState(""), [taxId, setTaxId] = useState(remembered("tax-id"));
  const [recipient, setRecipient] = useState(""), [value, setValue] = useState(""), [fees, setFees] = useState([{ code: "2300", rate: "1,3", value: "" }]);
  const [credit, setCredit] = useState(null), [flatRate, setFlatRate] = useState(true), [expenses, setExpenses] = useState([]), [advance, setAdvance] = useState(""), [vat, setVat] = useState("19"), [note, setNote] = useState("");
  const [result, setResult] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false), [created, setCreated] = useState(null);
  useEffect(() => { request("/invoices/catalogue").then(setCatalogue).catch(() => {}); }, []);
  useEffect(() => {
    const d = item?.details || {};
    setRecipient([d.client_name, d.client_address].filter(Boolean).join("\n"));
    setValue(d.dispute_value != null ? String(d.dispute_value).replace(".", ",") : "");
    setResult(null); setCreated(null);
  }, [caseId]);
  const payload = useMemo(() => ({ case_id: caseId, kind, recipient, issued_on: issuedOn, period, issuer_tax_id: taxId, note, vat_rate: vat, deduct_advances: true, flat_rate: flatRate,
    ...(kind === "rvg" ? { value: decimal(value), fees: fees.map(f => ({ code: f.code, rate: decimal(f.rate), ...(f.value.trim() ? { value: decimal(f.value) } : {}) })), credit: credit ? { rate: decimal(credit.rate), value: decimal(credit.value || value) } : null, expenses: expenses.map(x => ({ code: x.code, description: x.description, amount: decimal(x.amount) })) } : {}),
    ...(kind === "advance" ? { advance_net: decimal(advance) } : {}) }), [caseId, kind, recipient, issuedOn, period, taxId, note, vat, flatRate, value, fees, credit, expenses, advance]);
  useEffect(() => { setResult(null); }, [payload]);
  const fee = code => catalogue?.fees.find(f => f.code === code);
  const calculate = async () => { setBusy(true); setError(""); try { setResult(await request("/invoices/calculate", json("POST", payload))); } catch (e) { setError(failure(e)); } finally { setBusy(false); } };
  const create = async () => { setBusy(true); setError(""); try { remember("tax-id", taxId); const invoice = await request("/invoices", json("POST", payload)); setCreated(invoice); onCreated(); } catch (e) { setError(failure(e)); } finally { setBusy(false); } };
  if (!active.length) return <p className="desk-empty">Zuerst eine Akte anlegen.</p>;

  return <div className="invoice-form">
    <div className="cost-form-grid">
      <label>Akte<select value={caseId} onChange={e => setCaseId(e.target.value)}>{active.map(c => <option key={c.id} value={c.id}>{c.reference} · {c.title}</option>)}</select></label>
      <label>Rechnungsart<select value={kind} onChange={e => setKind(e.target.value)}>{Object.entries(KINDS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>Rechnungsdatum<DateInput value={issuedOn} onChange={e => setIssuedOn(e.target.value)} /></label>
      <label>Leistungszeitraum<input value={period} onChange={e => setPeriod(e.target.value)} placeholder="z. B. 09/2026 – 11/2026" /></label>
      <label>Steuernummer / USt-IdNr.<input value={taxId} onChange={e => setTaxId(e.target.value)} /></label>
      <label>Umsatzsteuer<select value={vat} onChange={e => setVat(e.target.value)}><option value="19">19 %</option><option value="7">7 %</option><option value="0">0 % (Kleinunternehmer / steuerfrei)</option></select></label>
    </div>
    <label>Rechnungsempfänger *<textarea rows={3} value={recipient} onChange={e => setRecipient(e.target.value)} /></label>

    {kind === "rvg" && <>
      <label className="invoice-value">Gegenstandswert EUR *<input inputMode="decimal" value={value} onChange={e => setValue(e.target.value)} placeholder="z. B. 10.000" /></label>
      <h3>Gebühren</h3>
      {fees.map((row, index) => <div className="invoice-fee" key={index}>
        <select aria-label="Gebührentatbestand" value={row.code} onChange={e => { const next = [...fees]; next[index] = { ...row, code: e.target.value, rate: (fee(e.target.value)?.rate || "1.0").replace(".", ",") }; setFees(next); }}>{catalogue?.fees.map(f => <option key={f.code} value={f.code}>Nr. {f.code} – {f.name}</option>)}</select>
        <label>Satz<input inputMode="decimal" value={row.rate} onChange={e => { const next = [...fees]; next[index] = { ...row, rate: e.target.value }; setFees(next); }} /></label>
        <label>Abweichender Wert<input inputMode="decimal" value={row.value} placeholder="wie oben" onChange={e => { const next = [...fees]; next[index] = { ...row, value: e.target.value }; setFees(next); }} /></label>
        <button type="button" className="desk-link desk-delete" aria-label="Gebühr entfernen" onClick={() => setFees(fees.filter((_, i) => i !== index))}><IconTrash size={16} /></button>
        {fee(row.code) && fee(row.code).min !== fee(row.code).max && <small>Rahmen {fee(row.code).min.replace(".", ",")} – {fee(row.code).max.replace(".", ",")}</small>}
      </div>)}
      <button type="button" className="desk-link" onClick={() => setFees([...fees, { code: "3100", rate: "1,3", value: "" }])}><IconPlus size={16} />Gebühr hinzufügen</button>
      <label className="desk-checkbox"><input type="checkbox" checked={Boolean(credit)} onChange={e => setCredit(e.target.checked ? { rate: "1,3", value: "" } : null)} />Geschäftsgebühr anrechnen (Vorbem. 3 Abs. 4 VV RVG – zur Hälfte, höchstens 0,75)</label>
      {credit && <div className="invoice-fee"><label>Satz der Geschäftsgebühr<input inputMode="decimal" value={credit.rate} onChange={e => setCredit({ ...credit, rate: e.target.value })} /></label><label>Wert, der übergeht<input inputMode="decimal" value={credit.value} placeholder="wie oben" onChange={e => setCredit({ ...credit, value: e.target.value })} /></label></div>}
      <label className="desk-checkbox"><input type="checkbox" checked={flatRate} onChange={e => setFlatRate(e.target.checked)} />Pauschale für Post und Telekommunikation Nr. 7002 VV RVG (20 %, höchstens 20 EUR)</label>
      <h3>Weitere Auslagen</h3>
      {expenses.map((row, index) => <div className="invoice-fee" key={index}>
        <select aria-label="Auslage" value={row.code} onChange={e => { const next = [...expenses]; next[index] = { ...row, code: e.target.value }; setExpenses(next); }}>{catalogue?.expenses.map(x => <option key={x.code} value={x.code}>{x.code === "other" ? "" : `Nr. ${x.code} – `}{x.name}</option>)}</select>
        <label>Beschreibung<input value={row.description} onChange={e => { const next = [...expenses]; next[index] = { ...row, description: e.target.value }; setExpenses(next); }} placeholder="z. B. 120 km Fahrt zum ArbG" /></label>
        <label>Betrag netto<input inputMode="decimal" value={row.amount} onChange={e => { const next = [...expenses]; next[index] = { ...row, amount: e.target.value }; setExpenses(next); }} /></label>
        <button type="button" className="desk-link desk-delete" aria-label="Auslage entfernen" onClick={() => setExpenses(expenses.filter((_, i) => i !== index))}><IconTrash size={16} /></button>
      </div>)}
      <button type="button" className="desk-link" onClick={() => setExpenses([...expenses, { code: "7003", description: "", amount: "" }])}><IconPlus size={16} />Auslage hinzufügen</button>
    </>}
    {kind === "advance" && <label className="invoice-value">Vorschuss netto EUR *<input inputMode="decimal" value={advance} onChange={e => setAdvance(e.target.value)} /></label>}
    {kind === "time" && <p className="field-help">Abgerechnet werden alle noch nicht abgerechneten Zeiten der Akte aus dem Reiter Zeiterfassung (Vergütungsvereinbarung nach § 3a RVG erforderlich).</p>}
    <label>Hinweis auf der Rechnung<textarea rows={2} value={note} onChange={e => setNote(e.target.value)} placeholder="z. B. Zahlbar innerhalb von 14 Tagen ohne Abzug." /></label>

    {error && <p role="alert" className="storage-error">{error}</p>}
    <div className="sample-actions"><button className="desk-button" disabled={busy || !caseId} onClick={calculate}>Berechnen</button><button className="desk-button solid" disabled={busy || !result} onClick={create}><IconFileInvoice size={17} />Rechnung erstellen</button></div>
    {result && <div className="invoice-result"><table className="desk-table"><tbody>
      {result.lines.map((line, i) => <tr key={i}><td>{line.text}{line.detail && <small>{line.detail}</small>}</td><td className="num">{euro(line.amount)}</td></tr>)}
      <tr className="sum"><td>Summe netto</td><td className="num">{euro(result.net)}</td></tr>
      <tr><td>Umsatzsteuer {result.vat_rate} % (Nr. 7008 VV RVG)</td><td className="num">{euro(result.vat)}</td></tr>
      <tr className="sum"><td>Gesamtbetrag</td><td className="num">{euro(result.gross)}</td></tr>
      {result.advances.map(a => <tr key={a.number}><td>abzüglich gezahlter Vorschuss (Rechnung {a.number})</td><td className="num">−{euro(a.amount)}</td></tr>)}
      <tr className="sum total"><td>Zu zahlen</td><td className="num">{euro(result.payable)}</td></tr>
    </tbody></table><p className="field-help">Rechenhilfe nach der RVG-Tabelle (BGBl. 2025 I Nr. 109). Gebührentatbestände, Sätze und Anrechnung im Einzelfall prüfen; die Rechnung ist nach § 10 RVG zu unterschreiben.</p></div>}
    {created && <p role="status" className="storage-notice">Rechnung {created.number} erstellt. <a className="desk-link" href={`${API_BASE}/api/invoices/${created.id}/pdf`} target="_blank" rel="noreferrer">PDF öffnen</a></p>}
  </div>;
}

function TimeRecording({ cases, selectedCase }) {
  const active = cases.filter(item => !item.archived_at);
  const [caseId, setCaseId] = useState(selectedCase?.id && active.some(c => c.id === selectedCase.id) ? selectedCase.id : active[0]?.id || "");
  const [entries, setEntries] = useState([]), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const [day, setDay] = useState(localToday()), [minutes, setMinutes] = useState("30"), [activity, setActivity] = useState(""), [rate, setRate] = useState(remembered("hourly-rate") || "200");
  const load = () => caseId && request(`/cases/${caseId}/time-entries`).then(setEntries).catch(e => setError(failure(e)));
  useEffect(() => { load(); }, [caseId]);
  const add = async event => { event.preventDefault(); setBusy(true); setError(""); try { remember("hourly-rate", rate); setEntries(await request(`/cases/${caseId}/time-entries`, json("POST", { day, minutes: Number(minutes), activity, hourly_rate: decimal(rate) }))); setActivity(""); } catch (e) { setError(failure(e)); } finally { setBusy(false); } };
  const remove = async id => { setBusy(true); try { await request(`/cases/${caseId}/time-entries/${id}`, { method: "DELETE" }); await load(); } catch (e) { setError(failure(e)); } finally { setBusy(false); } };
  const open = entries.filter(e => !e.invoice_id);
  const total = open.reduce((sum, e) => sum + Number(e.hourly_rate) * e.minutes / 60, 0);
  return <>
    <div className="eakte-filter"><label>Akte<select value={caseId} onChange={e => setCaseId(e.target.value)}>{active.map(c => <option key={c.id} value={c.id}>{c.reference} · {c.title}</option>)}</select></label>
      <span>Nicht abgerechnet: <strong>{Math.round(open.reduce((s, e) => s + e.minutes, 0) / 6) / 10} Std. · {euro(total)} netto</strong></span></div>
    <form className="cost-form-grid" onSubmit={add}>
      <label>Datum<DateInput value={day} onChange={e => setDay(e.target.value)} /></label>
      <label>Minuten<input type="number" min={1} max={1440} required value={minutes} onChange={e => setMinutes(e.target.value)} /></label>
      <label>Tätigkeit *<input required minLength={3} maxLength={300} value={activity} onChange={e => setActivity(e.target.value)} placeholder="z. B. Besprechung mit Mandantin" /></label>
      <label>Stundensatz EUR<input inputMode="decimal" value={rate} onChange={e => setRate(e.target.value)} /></label>
      <div className="court-actions"><button className="desk-button solid" disabled={busy || !caseId}><IconPlus size={16} />Zeit erfassen</button></div>
    </form>
    {error && <p role="alert" className="storage-error">{error}</p>}
    {entries.length ? <table className="desk-table"><thead><tr><th>Datum</th><th>Tätigkeit</th><th>Minuten</th><th>Betrag</th><th>Rechnung</th><th></th></tr></thead><tbody>
      {entries.map(e => <tr key={e.id}><td>{dateLabel(e.day, "de")}</td><td>{e.activity}</td><td>{e.minutes}</td><td>{euro(Number(e.hourly_rate) * e.minutes / 60)}</td><td>{e.invoice_number || "offen"}</td><td>{!e.invoice_id && <button className="desk-link desk-delete" disabled={busy} onClick={() => remove(e.id)}>Löschen</button>}</td></tr>)}
    </tbody></table> : <p className="desk-empty">Noch keine Zeiten erfasst.</p>}
  </>;
}

export function Invoicing({ cases, selectedCase }) {
  const [tab, setTab] = useState("list"), [reloadKey, setReloadKey] = useState(0);
  return <section className="desk-panel invoicing">
    <div className="desk-panel-heading"><div><h2>Abrechnung</h2><p>RVG-Rechnungen, Vorschüsse, Zeiterfassung und offene Posten</p></div></div>
    <div className="cal-views invoice-tabs">{[["list", "Rechnungen & offene Posten"], ["new", "Neue Rechnung"], ["time", "Zeiterfassung"]].map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
    {tab === "list" && <InvoiceList cases={cases} reloadKey={reloadKey} />}
    {tab === "new" && <NewInvoice cases={cases} selectedCase={selectedCase} onCreated={() => setReloadKey(k => k + 1)} />}
    {tab === "time" && <TimeRecording cases={cases} selectedCase={selectedCase} />}
  </section>;
}
