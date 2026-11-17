import { useState } from "react";
import { IconGavel, IconPlus, IconTrash } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { DateInput } from "./DateInput";
import "./tools.css";

const euro = value => new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(value));
const decimal = text => { const raw = String(text || "").trim().replace(/\s|€/g, ""); return raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : /^\d+\.\d{1,2}$/.test(raw) ? raw : raw.replace(/\./g, ""); };

// Kostenfestsetzungsantrag: calculated on the server, opened as an editable draft (letterhead, PDF, sending as usual).
export function CostAssessment({ item, onDraft }) {
  const d = item.details || {};
  const [form, setForm] = useState({ value: d.dispute_value ? String(d.dispute_value) : "", instance: "civil_first", hearing: true, settlement: false, vat_deductible: false,
    business_fee_rate: "0", court_fees_paid: "", client_role: d.client_role === "respondent" ? "defendant" : "plaintiff", title_kind: "Urteil", title_date: "", cost_quota: 100 });
  const [extras, setExtras] = useState([]), [preview, setPreview] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const set = (key, value) => { setForm(previous => ({ ...previous, [key]: value })); setPreview(null); };
  const payload = () => ({ ...form, value: decimal(form.value), court_fees_paid: decimal(form.court_fees_paid) || "0", business_fee_rate: form.business_fee_rate,
    cost_quota: Number(form.cost_quota), title_date: form.title_date || null, extra_costs: extras.filter(entry => entry.label.trim() && decimal(entry.amount)).map(entry => ({ label: entry.label.trim(), amount: decimal(entry.amount) })) });
  const run = async open => {
    setBusy(true); setError("");
    try {
      const result = await request(`/cases/${item.id}/cost-assessment`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
      setPreview(result);
      if (open) onDraft({ body: result.body, recipient: result.recipient, kind: "application", language: "de" }, item);
    } catch { setError("Bitte Streitwert (bis 500.000 €) und Beträge prüfen."); }
    finally { setBusy(false); }
  };

  return <section className="desk-panel tool-panel">
    <div className="desk-panel-heading"><div><h2><IconGavel size={18} /> Kostenfestsetzungsantrag (§§ 103, 104 ZPO)</h2>
      <p>Nach Urteil oder Vergleich: Kosten berechnen und als Schriftsatz öffnen. Dort können Sie alles anpassen, mit Briefkopf als PDF speichern und versenden.</p></div></div>
    {!d.court && <p className="storage-notice">In den Stammdaten ist noch kein Gericht eingetragen; im Antrag steht dann [Gericht].</p>}
    <div className="tool-grid">
      <div className="tool-form">
        <label>Streitwert / Gegenstandswert in € *<input inputMode="decimal" value={form.value} onChange={event => set("value", event.target.value)} placeholder="z. B. 10.000" /></label>
        <label>Instanz<select value={form.instance} onChange={event => set("instance", event.target.value)}><option value="civil_first">1. Instanz (AG/LG)</option><option value="civil_appeal">Berufung</option></select></label>
        <label>Unser Mandant ist<select value={form.client_role} onChange={event => set("client_role", event.target.value)}><option value="plaintiff">Kläger/in</option><option value="defendant">Beklagte/r</option></select></label>
        <div className="note-grid"><label>Titel<select value={form.title_kind} onChange={event => set("title_kind", event.target.value)}>{["Urteil", "Versäumnisurteil", "Anerkenntnisurteil", "Beschluss", "Vergleich"].map(kind => <option key={kind}>{kind}</option>)}</select></label>
          <label className="span-two">vom<DateInput value={form.title_date} onChange={event => set("title_date", event.target.value)} /></label></div>
        <label>Kostenquote zulasten des Gegners: <strong>{form.cost_quota} %</strong><input type="range" min={5} max={100} step={5} value={form.cost_quota} onChange={event => set("cost_quota", event.target.value)} /></label>
        <label className="desk-checkbox"><input type="checkbox" checked={form.hearing} onChange={event => set("hearing", event.target.checked)} />Terminsgebühr (mündliche Verhandlung)</label>
        <label className="desk-checkbox"><input type="checkbox" checked={form.settlement} onChange={event => set("settlement", event.target.checked)} />Einigungsgebühr (Vergleich)</label>
        <label className="desk-checkbox"><input type="checkbox" checked={form.vat_deductible} onChange={event => set("vat_deductible", event.target.checked)} />Mandant ist vorsteuerabzugsberechtigt</label>
        <label>Vorgerichtliche Geschäftsgebühr (Anrechnung)<select value={form.business_fee_rate} onChange={event => set("business_fee_rate", event.target.value)} disabled={form.instance !== "civil_first"}>
          <option value="0">keine anzurechnen</option>{["0.5", "1.0", "1.3", "1.5", "1.8", "2.0", "2.5"].map(rate => <option key={rate} value={rate}>{rate.replace(".", ",")} – Anrechnung {String(Math.min(Number(rate) / 2, 0.75)).replace(".", ",")}</option>)}</select></label>
        <label>Eingezahlte Gerichtskosten in €<input inputMode="decimal" value={form.court_fees_paid} onChange={event => set("court_fees_paid", event.target.value)} placeholder={preview ? `laut GKG ${euro(preview.court_fee_hint)}` : "Betrag laut Kostenrechnung des Gerichts"} /></label>
        {preview && !form.court_fees_paid && <button type="button" className="desk-link" onClick={() => set("court_fees_paid", preview.court_fee_hint.replace(".", ","))}>Gerichtsgebühr laut GKG übernehmen ({euro(preview.court_fee_hint)})</button>}
        <fieldset className="extra-costs"><legend>Weitere Auslagen (z. B. Zeugenvorschuss, Reisekosten)</legend>
          {extras.map((entry, index) => <div key={index} className="extra-row">
            <input aria-label="Bezeichnung" value={entry.label} placeholder="Bezeichnung" onChange={event => { setExtras(extras.map((row, i) => i === index ? { ...row, label: event.target.value } : row)); setPreview(null); }} />
            <input aria-label="Betrag" inputMode="decimal" value={entry.amount} placeholder="€" onChange={event => { setExtras(extras.map((row, i) => i === index ? { ...row, amount: event.target.value } : row)); setPreview(null); }} />
            <button type="button" className="note-delete" aria-label="Entfernen" onClick={() => { setExtras(extras.filter((_, i) => i !== index)); setPreview(null); }}><IconTrash size={15} /></button></div>)}
          {extras.length < 10 && <button type="button" className="desk-link" onClick={() => setExtras([...extras, { label: "", amount: "" }])}><IconPlus size={15} />Position hinzufügen</button>}
        </fieldset>
      </div>
      <div className="tool-result">
        {error && <p className="storage-error" role="alert">{error}</p>}
        {preview ? <><table className="risk-table"><tbody>{preview.lines.map(line => <tr key={line.label}><td>{line.label}</td><td>{euro(line.amount)}</td></tr>)}
          <tr className="risk-sum"><td>Gesamtbetrag</td><td>{euro(preview.total)}</td></tr></tbody></table>
          <p className="field-help">Zinsen ab Eingang des Antrags: 5 Prozentpunkte über dem Basiszinssatz (§ 104 Abs. 1 Satz 2 ZPO).</p></>
          : <p className="desk-empty">Angaben links ausfüllen und „Berechnen“ wählen.</p>}
        <div className="cost-actions"><button className="desk-button" disabled={busy || !decimal(form.value)} onClick={() => run(false)}>Berechnen</button>
          <button className="desk-button solid" disabled={busy || !decimal(form.value)} onClick={() => run(true)}>Als Schriftsatz öffnen</button></div>
      </div>
    </div>
  </section>;
}
