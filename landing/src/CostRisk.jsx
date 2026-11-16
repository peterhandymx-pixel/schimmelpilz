import { useEffect, useState } from "react";
import { IconScale, IconDownload } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { pdfRequest, downloadBlob } from "./pdfExport.js";
import "./tools.css";

const euro = value => new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(value));
const INSTANCES = [["civil_first", "Zivilgericht, 1. Instanz (AG/LG)"], ["civil_appeal", "Berufung"], ["labour_first", "Arbeitsgericht, 1. Instanz"]];

// Litigation cost risk from RVG/GKG tables – plain arithmetic on the server, PDF for the client.
export function CostRisk({ cases, selectedCase }) {
  const [caseId, setCaseId] = useState(selectedCase?.id || "");
  const current = cases.find(item => item.id === caseId);
  const [form, setForm] = useState({ value: selectedCase?.details?.dispute_value ? String(selectedCase.details.dispute_value) : "", instance: selectedCase?.details?.legal_area === "employment" ? "labour_first" : "civil_first", hearing: true, own_vat_deductible: false, opponent_vat_deductible: false, win_percent: 50 });
  const [result, setResult] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const set = (key, value) => setForm(previous => ({ ...previous, [key]: value }));
  // German input: "12.500,50"; plain "12500.5" (from the case particulars) keeps its decimal point.
  const raw = form.value.trim().replace(/\s|€/g, "");
  const amount = raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : /^\d+\.\d{1,2}$/.test(raw) ? raw : raw.replace(/\./g, "");
  const payload = { ...form, value: amount, win_percent: Number(form.win_percent), client_name: current?.details?.client_name || "", reference: current?.reference || "", matter: current?.title || "" };

  useEffect(() => {
    if (!amount || !(Number(amount) > 0)) { setResult(null); setError(""); return undefined; }
    const timer = setTimeout(async () => {
      try { setResult(await request("/cost-risk/calculate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })); setError(""); }
      catch { setResult(null); setError(Number(amount) > 500000 ? "Streitwerte über 500.000 € sind nicht abgedeckt." : "Bitte einen gültigen Streitwert eingeben."); }
    }, 250);
    return () => clearTimeout(timer);
  }, [amount, form.instance, form.hearing, form.own_vat_deductible, form.opponent_vat_deductible, form.win_percent]);

  const download = async () => {
    setBusy(true);
    try { downloadBlob(await pdfRequest("/cost-risk/report.pdf", payload), `Prozesskostenrisiko${current ? " " + current.reference.replace(/[\\/]/g, "-") : ""}.pdf`); }
    catch { setError("PDF konnte nicht erstellt werden."); }
    finally { setBusy(false); }
  };
  const pickCase = id => {
    setCaseId(id);
    const item = cases.find(entry => entry.id === id);
    const value = item?.details?.dispute_value;
    if (value) set("value", String(value));
    if (item) set("instance", item.details?.legal_area === "employment" ? "labour_first" : "civil_first");
  };

  return <section className="desk-panel tool-panel">
    <div className="desk-panel-heading"><div><h2><IconScale size={18} /> Prozesskostenrisiko</h2>
      <p>Was kostet der Prozess, wenn er verloren, gewonnen oder verglichen wird? Berechnung nach RVG und GKG (Tabellen 2025), als PDF für das Mandantengespräch.</p></div></div>
    <div className="tool-grid">
      <div className="tool-form">
        <label>Akte (optional, für das PDF)<select value={caseId} onChange={event => pickCase(event.target.value)}><option value="">– ohne Akte –</option>{cases.filter(item => !item.archived_at).map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>
        <label>Streitwert in € *<input inputMode="decimal" placeholder="z. B. 10.000" value={form.value} onChange={event => set("value", event.target.value)} /></label>
        <label>Verfahren<select value={form.instance} onChange={event => set("instance", event.target.value)}>{INSTANCES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label>Obsiegen bei Teilerfolg: <strong>{form.win_percent} %</strong><input type="range" min={0} max={100} step={5} value={form.win_percent} onChange={event => set("win_percent", event.target.value)} /></label>
        <label className="desk-checkbox"><input type="checkbox" checked={form.hearing} onChange={event => set("hearing", event.target.checked)} />Mündliche Verhandlung (Terminsgebühr)</label>
        <label className="desk-checkbox"><input type="checkbox" checked={form.own_vat_deductible} onChange={event => set("own_vat_deductible", event.target.checked)} />Mandant ist vorsteuerabzugsberechtigt</label>
        <label className="desk-checkbox"><input type="checkbox" checked={form.opponent_vat_deductible} onChange={event => set("opponent_vat_deductible", event.target.checked)} />Gegenseite ist vorsteuerabzugsberechtigt</label>
      </div>
      <div className="tool-result" aria-live="polite">
        {error && <p className="storage-error" role="alert">{error}</p>}
        {!result && !error && <p className="desk-empty">Streitwert eingeben – die Beträge erscheinen sofort.</p>}
        {result && <>
          <div className="risk-cards">{result.scenarios.map(item => <div key={item.id} className={`risk-card risk-${item.id}`}><span>{item.label}</span><strong>{euro(item.amount)}</strong></div>)}</div>
          {result.advance !== "0.00" && <p className="field-help">Gerichtskostenvorschuss bei Klageeinreichung: <strong>{euro(result.advance)}</strong> (§ 12 GKG)</p>}
          <details className="risk-details" open><summary>Aufstellung</summary>
            <table className="risk-table"><tbody>
              <tr className="risk-head"><th colSpan={2}>Eigene Anwaltskosten</th></tr>
              {result.own_lawyer.lines.map(line => <tr key={"o" + line.label}><td>{line.label}</td><td>{euro(line.amount)}</td></tr>)}
              <tr className="risk-sum"><td>Summe</td><td>{euro(result.own_lawyer.total)}</td></tr>
              <tr className="risk-head"><th colSpan={2}>Anwaltskosten der Gegenseite{!result.reimburse_lawyer && " (nicht erstattungsfähig, § 12a ArbGG)"}</th></tr>
              {result.other_lawyer.lines.map(line => <tr key={"g" + line.label}><td>{line.label}</td><td>{euro(line.amount)}</td></tr>)}
              <tr className="risk-sum"><td>Summe</td><td>{euro(result.other_lawyer.total)}</td></tr>
              <tr className="risk-head"><th colSpan={2}>Gerichtskosten</th></tr>
              <tr><td>{result.court.label}</td><td>{euro(result.court.amount)}</td></tr>
              <tr><td>{result.court.settled_label}</td><td>{euro(result.court.settled_amount)}</td></tr>
            </tbody></table>
            <p className="field-help">Wertstufe bis {euro(result.bracket)} · 1,0-Gebühr RVG {euro(result.base_fee_rvg)} · 1,0-Gebühr GKG {euro(result.base_fee_court)}</p>
          </details>
          {result.notes.map(note => <p key={note} className="field-help">{note}</p>)}
          <button className="desk-button solid" disabled={busy} onClick={download}><IconDownload size={17} />{busy ? "PDF wird erstellt …" : "PDF für den Mandanten"}</button>
        </>}
      </div>
    </div>
  </section>;
}
