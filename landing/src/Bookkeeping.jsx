import { useEffect, useState } from "react";
import { IconDownload, IconPlus } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";
import { dateLabel, localToday } from "./workbench.js";
import { DateInput } from "./DateInput.jsx";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const cents = minor => (minor / 100).toLocaleString("de-DE", { style: "currency", currency: "EUR" });
const decimal = value => { const text = String(value || "").trim(); return text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : /^\d+\.\d{1,2}$/.test(text) ? text : text.replace(/\./g, ""); };
const ERRORS = {
  client_money_insufficient: "Für diese Akte ist nicht genug Fremdgeld vorhanden.", client_money_only_on_trust_account: "Fremdgeld nur auf dem Anderkonto buchen.",
  office_booking_on_trust_account: "Auf dem Anderkonto nur Fremdgeld buchen.", invoice_of_other_case: "Die Rechnung gehört zu einer anderen Akte.", already_reversed: "Bereits storniert.", invalid_transfer: "Umbuchung zwischen Anderkonto und Geschäftskonto nur mit Akte.",
};
const failure = e => ERRORS[e.detail] || (e.status === 422 ? "Eingaben prüfen: Betrag, Akte (bei Fremdgeld) und Rechnung (bei Verrechnung)." : "Buchung fehlgeschlagen.");
const KIND_CATEGORIES = { office: ["fee_income", "other_income", "expense", "private", "transfer"], cash: ["fee_income", "other_income", "expense", "private", "transfer"], trust: ["trust_in", "trust_out", "trust_to_fees", "transfer"] };
const DIRECTION = { fee_income: "in", other_income: "in", expense: "out", trust_in: "in", trust_out: "out", trust_to_fees: "out" };
const DATEV_LABELS = { bank: "Bank (Geschäftskonto)", trust: "Anderkonto", cash: "Kasse", revenue_19: "Erlöse 19 %", revenue_7: "Erlöse 7 %", revenue_0: "Erlöse steuerfrei", expense: "Aufwand", private: "Privat", client_money: "Fremdgeld / Verbindlichkeit Mandanten", other_income: "Sonstige Erträge" };

function Accounts({ cases, data, reload }) {
  const [form, setForm] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false), [reverse, setReverse] = useState(null);
  const active = cases.filter(c => !c.archived_at);
  const start = account => setForm({ account_id: account.id, kind: account.kind, day: localToday(), category: KIND_CATEGORIES[account.kind][0], direction: "in", amount: "", case_id: "", invoice_id: "", counter_account_id: "", counterparty: "", text: "", vat_rate: account.kind === "trust" ? "0" : "19" });
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError("");
    const direction = DIRECTION[form.category] || form.direction;
    try {
      await request("/ledger/entries", json("POST", { account_id: form.account_id, day: form.day, direction, amount: decimal(form.amount), category: form.category, case_id: form.case_id || null, invoice_id: form.invoice_id || null, counter_account_id: form.counter_account_id || null, counterparty: form.counterparty, text: form.text, vat_rate: form.category === "fee_income" && form.invoice_id ? "0" : form.vat_rate }));
      setForm(null); await reload();
    } catch (e) { setError(failure(e)); } finally { setBusy(false); }
  };
  const doReverse = async event => { event.preventDefault(); setBusy(true); try { await request(`/ledger/entries/${reverse.id}/reverse`, json("POST", { reason: reverse.reason })); setReverse(null); await reload(); } catch (e) { setError(failure(e)); } finally { setBusy(false); } };
  const invoicesForCase = data.open_invoices.filter(i => !form?.case_id || i.case_id === form.case_id);
  return <>
    <div className="admin-tiles">{data.accounts.map(a => <div key={a.id}><strong>{cents(a.balance_minor)}</strong><span>{a.name}</span><button className="desk-link" onClick={() => start(a)}><IconPlus size={14} />Buchen</button></div>)}</div>
    {form && <form className="admin-card ledger-form" onSubmit={submit}><h3>Buchung: {data.accounts.find(a => a.id === form.account_id)?.name}</h3>
      <div className="cost-form-grid">
        <label>Art<select value={form.category} onChange={e => setForm({ ...form, category: e.target.value, invoice_id: "" })}>{KIND_CATEGORIES[form.kind].map(id => <option key={id} value={id}>{data.categories[id]}</option>)}</select></label>
        {!DIRECTION[form.category] && <label>Richtung<select value={form.direction} onChange={e => setForm({ ...form, direction: e.target.value })}><option value="in">Eingang</option><option value="out">Ausgang</option></select></label>}
        <label>Datum<DateInput value={form.day} onChange={e => setForm({ ...form, day: e.target.value })} /></label>
        <label>Betrag brutto EUR *<input required inputMode="decimal" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} /></label>
        <label>Akte{form.kind === "trust" ? " *" : ""}<select value={form.case_id} required={form.kind === "trust"} onChange={e => setForm({ ...form, case_id: e.target.value, invoice_id: "" })}><option value="">—</option>{active.map(c => <option key={c.id} value={c.id}>{c.reference} · {c.title}</option>)}</select></label>
        {(form.category === "fee_income" || form.category === "trust_to_fees") && <label>Rechnung{form.category === "trust_to_fees" ? " *" : ""}<select value={form.invoice_id} required={form.category === "trust_to_fees"} onChange={e => setForm({ ...form, invoice_id: e.target.value })}><option value="">{form.category === "fee_income" ? "ohne Rechnung" : "—"}</option>{invoicesForCase.map(i => <option key={i.id} value={i.id}>{i.number} · offen {cents(i.open_minor)}</option>)}</select></label>}
        {form.category === "transfer" && <label>Auf Konto *<select required value={form.counter_account_id} onChange={e => setForm({ ...form, counter_account_id: e.target.value })}><option value="">—</option>{data.accounts.filter(a => a.id !== form.account_id).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>}
        {["fee_income", "other_income", "expense"].includes(form.category) && !form.invoice_id && <label>Umsatzsteuer<select value={form.vat_rate} onChange={e => setForm({ ...form, vat_rate: e.target.value })}><option value="19">19 %</option><option value="7">7 %</option><option value="0">0 %</option></select></label>}
        <label>Zahler / Empfänger<input value={form.counterparty} onChange={e => setForm({ ...form, counterparty: e.target.value })} /></label>
        <label>Buchungstext *<input required minLength={2} value={form.text} onChange={e => setForm({ ...form, text: e.target.value })} placeholder="z. B. Zahlung Gegner lt. Kontoauszug" /></label>
      </div>
      {error && <p role="alert" className="storage-error">{error}</p>}
      <div className="sample-actions"><button className="desk-button solid" disabled={busy}>Buchen</button><button type="button" className="desk-link" onClick={() => setForm(null)}>Abbrechen</button></div>
    </form>}
    {!form && error && <p role="alert" className="storage-error">{error}</p>}
    <section className="admin-card"><h3>Buchungen</h3>
      {data.entries.length ? <div className="desk-table-scroll"><table className="desk-table"><thead><tr><th>Datum</th><th>Konto</th><th>Art</th><th>Text</th><th>Akte</th><th className="num">Betrag</th><th className="num">USt</th><th></th></tr></thead><tbody>
        {data.entries.map(e => <tr key={e.id} className={e.reversed_by || e.reverses ? "invoice-cancelled" : ""}><td>{dateLabel(e.day, "de")}</td><td>{e.account_name}</td><td>{e.category_name}</td><td>{e.text}{e.counterparty && <small>{e.counterparty}</small>}</td><td>{e.case_reference}</td><td className="num">{cents(e.amount_minor)}</td><td className="num">{e.vat_minor ? cents(e.vat_minor) : ""}</td>
          <td>{!e.reversed_by && !e.reverses && <button className="desk-link desk-delete" onClick={() => setReverse({ id: e.id, reason: "" })}>Storno</button>}
            {reverse?.id === e.id && <form className="invoice-inline" onSubmit={doReverse}><input required minLength={5} placeholder="Grund" value={reverse.reason} onChange={ev => setReverse({ ...reverse, reason: ev.target.value })} /><button className="desk-button danger" disabled={busy}>Stornieren</button></form>}</td></tr>)}
      </tbody></table></div> : <p className="desk-empty">Noch keine Buchungen.</p>}
      <p className="field-help">Buchungen werden nie geändert oder gelöscht; eine Stornierung bucht den Gegenbetrag. Zahlungen aus „Abrechnung“ erscheinen hier automatisch als Honorareingang.</p>
    </section>
  </>;
}

function ClientMoney({ data }) {
  return <section className="admin-card"><h3>Fremdgeld je Akte</h3>
    {data.trust.length ? <table className="desk-table"><thead><tr><th>Akte</th><th className="num">Bestand</th><th>Letzter Eingang</th><th>Hinweis</th></tr></thead><tbody>
      {data.trust.map(t => <tr key={t.case_id}><td>{t.case_reference}</td><td className="num">{cents(t.balance_minor)}</td><td>{dateLabel(t.held_since, "de")} ({t.days} Tage)</td><td>{t.overdue ? <span className="invoice-status open">länger als {data.trust_limit_days} Tage – unverzüglich weiterleiten</span> : "—"}</td></tr>)}
    </tbody></table> : <p className="desk-empty">Derzeit kein Fremdgeld im Bestand.</p>}
    <p className="field-help">Fremdgeld ist unverzüglich an den Berechtigten weiterzuleiten oder auf ein Anderkonto zu nehmen (§ 43a Abs. 5 BRAO, § 4 BORA). Je Akte kann nie mehr ausgezahlt werden, als eingegangen ist.</p>
  </section>;
}

function VatReturn() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear()), [period, setPeriod] = useState(`Q${Math.floor(now.getMonth() / 3) + 1}`), [data, setData] = useState(null);
  useEffect(() => { request(`/ledger/vat?year=${year}&period=${period}`).then(setData).catch(() => setData(null)); }, [year, period]);
  return <section className="admin-card"><h3>Umsatzsteuer-Voranmeldung</h3>
    <div className="eakte-filter"><label>Jahr<input type="number" min={2020} max={2100} value={year} onChange={e => setYear(Number(e.target.value))} /></label>
      <label>Zeitraum<select value={period} onChange={e => setPeriod(e.target.value)}>{["Q1", "Q2", "Q3", "Q4", ...Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"))].map(p => <option key={p} value={p}>{p.startsWith("Q") ? `${p[1]}. Quartal` : `Monat ${p}`}</option>)}</select></label></div>
    {data && <table className="desk-table"><tbody>
      <tr><td>Kz. 81 – Umsätze 19 % (Bemessungsgrundlage)</td><td className="num">{cents(data.kz81_minor)}</td></tr>
      <tr><td>Kz. 86 – Umsätze 7 % (Bemessungsgrundlage)</td><td className="num">{cents(data.kz86_minor)}</td></tr>
      <tr><td>Umsatzsteuer darauf</td><td className="num">{cents(data.output_vat_minor)}</td></tr>
      <tr><td>Kz. 66 – Vorsteuer</td><td className="num">{cents(data.kz66_minor)}</td></tr>
      <tr className="sum"><td>Kz. 83 – Vorauszahlung / Erstattung</td><td className="num">{cents(data.kz83_minor)}</td></tr>
    </tbody></table>}
    <p className="field-help">{data?.basis}. Werte in ELSTER übertragen; eine direkte Übermittlung ist nicht eingebaut (ELSTER-Zertifikat nötig). Mit dem Steuerberater abstimmen.</p>
  </section>;
}

function Datev() {
  const [year, setYear] = useState(new Date().getFullYear()), [numbers, setNumbers] = useState(null), [notice, setNotice] = useState("");
  useEffect(() => { request("/ledger/datev-settings").then(setNumbers).catch(() => {}); }, []);
  const save = async event => { event.preventDefault(); try { setNumbers(await request("/ledger/datev-settings", json("PUT", { accounts: numbers }))); setNotice("Kontenzuordnung gespeichert."); } catch { setNotice("Kontonummern: 3 bis 8 Ziffern."); } };
  return <section className="admin-card"><h3>DATEV-Export</h3>
    <div className="eakte-filter"><label>Jahr<input type="number" min={2020} max={2100} value={year} onChange={e => setYear(Number(e.target.value))} /></label>
      <a className="desk-button solid" href={`${API_BASE}/api/ledger/datev.csv?year=${year}`}><IconDownload size={16} />Buchungsstapel (CSV)</a></div>
    {numbers && <form onSubmit={save}><div className="cost-form-grid">{Object.entries(DATEV_LABELS).map(([key, label]) => <label key={key}>{label}<input value={numbers[key] || ""} onChange={e => setNumbers({ ...numbers, [key]: e.target.value.replace(/\D/g, "") })} /></label>)}</div>
      <button className="desk-button">Kontenzuordnung speichern</button>{notice && <span className="field-help"> {notice}</span>}</form>}
    <p className="field-help">Felder im Aufbau des DATEV-Buchungsstapels (Umsatz, Soll/Haben, Konto, Gegenkonto, BU-Schlüssel, Belegdatum, Belegfeld, Buchungstext) für den ASCII-Import. Vorgabe SKR04 – Kontenrahmen und Import mit dem Steuerberater abstimmen.</p>
  </section>;
}

function Statistics() {
  const [year, setYear] = useState(new Date().getFullYear()), [data, setData] = useState(null);
  useEffect(() => { request(`/ledger/statistics?year=${year}`).then(setData).catch(() => setData(null)); }, [year]);
  if (!data) return null;
  const max = Math.max(1, ...data.fees_by_month.map(m => m.net_minor));
  const AREAS = { general: "Allgemein", consumer: "Verbraucher", tenancy: "Miete", contract: "Vertrag/Zivil", commercial: "Handel/Gesellschaft", employment: "Arbeit", family: "Familie", social: "Sozial", administrative: "Verwaltung", tax: "Steuer", criminal: "Straf" };
  const STATES = { active: "In Bearbeitung", waiting: "Wartet", closed: "Abgeschlossen", archived: "Archiv" };
  return <>
    <div className="eakte-filter"><label>Jahr<input type="number" min={2020} max={2100} value={year} onChange={e => setYear(Number(e.target.value))} /></label></div>
    <div className="admin-tiles"><div><strong>{cents(data.fees_total_minor)}</strong><span>Honorare netto {year}</span></div><div><strong>{data.open_count}</strong><span>offene Rechnungen</span></div><div><strong>{cents(data.open_minor)}</strong><span>offene Posten</span></div><div><strong>{data.overdue_count}</strong><span>älter als 30 Tage</span></div></div>
    <div className="admin-columns">
      <section className="admin-card"><h3>Honorareingänge je Monat (netto)</h3><div className="admin-bars">{data.fees_by_month.map(m => <div key={m.month} title={cents(m.net_minor)}><span className="bar-paid" style={{ height: `${m.net_minor / max * 100}%` }} /><small>{m.month}</small></div>)}</div></section>
      <section className="admin-card"><h3>Aktenbestand</h3><ul className="admin-facts">{Object.entries(data.cases_by_status).map(([k, v]) => <li key={k}>{STATES[k] || k}: <strong>{v}</strong></li>)}</ul>
        <h4>Nach Rechtsgebiet (aktiv)</h4><ul className="admin-facts">{Object.entries(data.cases_by_area).sort((a, b) => b[1] - a[1]).map(([k, v]) => <li key={k}>{AREAS[k] || k}: <strong>{v}</strong></li>)}</ul></section>
    </div>
  </>;
}

export function Bookkeeping({ cases }) {
  const [tab, setTab] = useState("accounts"), [data, setData] = useState(null), [error, setError] = useState("");
  const load = () => request("/ledger").then(setData).catch(() => setError("Buchhaltung nicht erreichbar."));
  useEffect(() => { load(); }, []);
  return <section className="desk-panel bookkeeping">
    <div className="desk-panel-heading"><div><h2>Buchhaltung</h2><p>Geschäftskonto, Fremdgeld, Umsatzsteuer, DATEV und Auswertungen</p></div></div>
    <div className="cal-views invoice-tabs">{[["accounts", "Konten & Buchungen"], ["trust", "Fremdgeld"], ["vat", "Umsatzsteuer"], ["datev", "DATEV"], ["stats", "Auswertungen"]].map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} aria-pressed={tab === id} onClick={() => { setTab(id); load(); }}>{label}{id === "trust" && data?.trust.some(t => t.overdue) ? " ⚠" : ""}</button>)}</div>
    {error && <p role="alert" className="storage-error">{error}</p>}
    {data && tab === "accounts" && <Accounts cases={cases} data={data} reload={load} />}
    {data && tab === "trust" && <ClientMoney data={data} />}
    {tab === "vat" && <VatReturn />}
    {tab === "datev" && <Datev />}
    {tab === "stats" && <Statistics />}
  </section>;
}
