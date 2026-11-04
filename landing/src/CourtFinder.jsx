import { useState } from "react";
import { IconBuildingBank, IconCheck, IconExternalLink, IconSearch } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";

// Matters, the places a court can be chosen by (with their norms) and which court of the directory's list hears it.
const MATTERS = {
  civil: { label: "Zivilrechtliche Forderung", area: "zivil", bases: [
    ["Wohnsitz / Sitz der beklagten Partei", "§§ 12, 13, 17 ZPO – allgemeiner Gerichtsstand"],
    ["Erfüllungsort der streitigen Verpflichtung", "§ 29 ZPO – wahlweise"],
    ["Ort der unerlaubten Handlung", "§ 32 ZPO – wahlweise"]],
    pick: value => value > 10000 ? ["Landgericht", "Streitwert über 10.000 EUR: Landgericht (§§ 23 Nr. 1, 71 Abs. 1 GVG), Anwaltszwang (§ 78 ZPO)"] : ["Amtsgericht", "Streitwert bis 10.000 EUR: Amtsgericht (§ 23 Nr. 1 GVG)"] },
  tenancy: { label: "Wohnraummiete", area: "zivil", bases: [["Lage der Wohnung", "§ 29a ZPO – ausschließlich"]],
    pick: () => ["Amtsgericht", "Wohnraummiete: immer Amtsgericht, unabhängig vom Streitwert (§ 23 Nr. 2 a GVG)"] },
  employment: { label: "Arbeitsrecht", area: "arbeit", bases: [
    ["Ort, an dem gewöhnlich gearbeitet wird / wurde", "§ 48 Abs. 1a ArbGG – wahlweise"],
    ["Sitz des Arbeitgebers", "§ 46 Abs. 2 ArbGG i. V. m. §§ 12, 17 ZPO"]],
    pick: () => ["Arbeitsgericht", "Streit aus dem Arbeitsverhältnis: Arbeitsgericht (§ 2 ArbGG)"] },
  social: { label: "Sozialrecht", area: "sozial", bases: [["Wohnsitz der klagenden Person", "§ 57 Abs. 1 SGG"]],
    pick: () => ["Sozialgericht", "Sozialrechtliche Angelegenheit: Sozialgericht (§ 51 SGG)"] },
  administrative: { label: "Verwaltungsrecht", area: "verwaltung", bases: [
    ["Sitz der Behörde, die den Bescheid erlassen hat", "§ 52 Nr. 3 VwGO – Anfechtungs- und Verpflichtungsklagen"],
    ["Lage des Grundstücks", "§ 52 Nr. 1 VwGO – ortsgebundene Rechte"],
    ["Wohnsitz der klagenden Person", "§ 52 Nr. 5 VwGO – übrige Fälle"]],
    pick: () => ["Verwaltungsgericht", "Öffentlich-rechtliche Streitigkeit: Verwaltungsgericht (§ 40 VwGO)"] },
  family: { label: "Familiensache", area: "familie", bases: [
    ["Gewöhnlicher Aufenthalt des Kindes", "§ 152 Abs. 2 FamFG – Kindschaftssachen"],
    ["Aufenthalt der Ehegatten mit gemeinsamen Kindern", "§ 122 FamFG – Ehesachen"]],
    pick: () => ["Amtsgericht", "Familiensache: Amtsgericht – Familiengericht (§ 23a GVG)"], suffix: " – Familiengericht –" },
  inheritance: { label: "Nachlasssache", area: "nachlass", bases: [["Letzter gewöhnlicher Aufenthalt der verstorbenen Person", "§ 343 FamFG"]],
    pick: () => ["Amtsgericht", "Nachlasssache: Amtsgericht – Nachlassgericht (§ 23a Abs. 2 Nr. 2 GVG)"], suffix: " – Nachlassgericht –" },
  tax: { label: "Steuerrecht", area: "finanz", bases: [["Sitz des Finanzamts", "§ 38 FGO"]],
    pick: () => ["Finanzgericht", "Steuersache: Finanzgericht (§ 33 FGO)"] },
  dunning: { label: "Gerichtliches Mahnverfahren", area: "mahn", bases: [["Wohnsitz / Sitz der antragstellenden Partei", "§ 689 Abs. 2 ZPO – zentrales Mahngericht"]],
    pick: () => ["", "Mahnverfahren: zentrales Mahngericht des Bundeslandes der antragstellenden Partei; Antrag nur über das amtliche Online-Formular"] },
};
// The case's legal area decides which matter the finder starts with.
const FROM_AREA = { tenancy: "tenancy", employment: "employment", family: "family", social: "social", administrative: "administrative" };
const ERRORS = { directory_unavailable: "Das amtliche Gerichtsverzeichnis ist gerade nicht erreichbar. Bitte später erneut versuchen.", place_required: "Bitte Postleitzahl und Ort eingeben." };

// One line per address part, joined with commas for the case's court field (the templates turn it back into lines).
const address = court => [(court.postal.length ? court.postal : court.street).join(", "), court.phone && `Tel. ${court.phone}`, court.xjustiz_id && `XJustiz-ID ${court.xjustiz_id}`].filter(Boolean).join(" · ");
const courtText = (court, suffix) => [court.name + (suffix || ""), ...(court.postal.length ? court.postal : court.street)].join(", ").slice(0, 160);

export function CourtFinder({ item, category, onChanged }) {
  const d = item.details || {};
  const [matter, setMatter] = useState(FROM_AREA[category] || "civil"), [basis, setBasis] = useState(0);
  const [plz, setPlz] = useState(""), [ort, setOrt] = useState(""), [value, setValue] = useState(d.dispute_value != null ? String(d.dispute_value) : "");
  const [result, setResult] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState("");
  const config = MATTERS[matter];
  const [level, reason] = config.pick(Number(String(value).replace(",", ".")) || 0);
  const recommended = result?.courts.find(court => level && court.name.startsWith(level)) || (result?.courts.length && !level ? result.courts[0] : null);

  const search = async choice => {
    setBusy(true); setError(""); setSaved("");
    try {
      const query = new URLSearchParams({ area: config.area, plz, ort, ...(choice ? { choice } : {}) });
      setResult(await request(`/courts/lookup?${query}`));
    } catch (failure) { setResult(null); setError(ERRORS[failure.detail] || "Suche nicht möglich. Bitte Postleitzahl (5 Ziffern) und Ort prüfen."); }
    finally { setBusy(false); }
  };
  const adopt = async court => {
    setBusy(true); setError("");
    try {
      const text = courtText(court, config.suffix);
      await request(`/cases/${item.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: item.title, description: item.description, language: item.language || "de", details: { ...d, court: text } }) });
      setSaved(text); onChanged?.();
    } catch { setError("Das Gericht konnte nicht in die Akte übernommen werden."); }
    finally { setBusy(false); }
  };

  return <section className="desk-panel court-finder">
    <div className="desk-panel-heading"><div><h2><IconBuildingBank size={20} /> Zuständiges Gericht ermitteln</h2>
      <p>Aus Sachgebiet, Gerichtsstand und Ort – nach dem amtlichen Orts- und Gerichtsverzeichnis der Justiz.</p></div></div>
    {d.court && <p className="court-current">In der Akte eingetragen: <strong>{d.court}</strong></p>}
    <form className="cost-form-grid" onSubmit={event => { event.preventDefault(); search(); }}>
      <label>Angelegenheit<select value={matter} onChange={event => { setMatter(event.target.value); setBasis(0); setResult(null); }}>{Object.entries(MATTERS).map(([id, entry]) => <option key={id} value={id}>{entry.label}</option>)}</select></label>
      <label>Gerichtsstand<select value={basis} onChange={event => setBasis(Number(event.target.value))}>{config.bases.map(([label, norm], index) => <option key={index} value={index}>{label} ({norm})</option>)}</select></label>
      {matter === "civil" && <label>Zuständigkeitsstreitwert EUR<input inputMode="decimal" value={value} onChange={event => setValue(event.target.value)} placeholder="z. B. 4500" /></label>}
      <label>Postleitzahl<input inputMode="numeric" pattern="\d{5}" maxLength={5} required value={plz} onChange={event => setPlz(event.target.value.replace(/\D/g, ""))} /></label>
      <label>Ort<input required maxLength={60} value={ort} onChange={event => setOrt(event.target.value)} /></label>
      <div className="court-actions"><button className="desk-button solid" disabled={busy}><IconSearch size={17} />{busy ? "Wird gesucht …" : "Gericht ermitteln"}</button></div>
    </form>
    <p className="field-help">Maßgeblicher Ort: <strong>{config.bases[basis][0]}</strong> – {config.bases[basis][1]}. {reason}. Übermittelt werden nur Sachgebiet, Postleitzahl und Ort.</p>
    {error && <p role="alert" className="storage-error">{error}</p>}
    {result && !result.courts.length && <div className="court-choices">
      {result.notice && <p>{result.notice}</p>}
      {result.choices?.length ? <><p><strong>Bitte die Straße bzw. den Ort auswählen:</strong></p><ul>{result.choices.map(choice => <li key={choice.query}><button type="button" className="desk-link" onClick={() => search(choice.query)}>{choice.label}</button></li>)}</ul></>
        : <p>Für diese Angaben wurde kein Gericht gefunden. Bitte Postleitzahl und Ortsnamen prüfen.</p>}
    </div>}
    {result?.courts.length > 0 && <div className="court-results">
      {recommended ? <article className="court-card recommended">
        <span className="court-badge">Zuständig für diese Klage</span>
        <h3>{recommended.name}{config.suffix || ""}</h3>
        {recommended.remark && <small>{recommended.remark}</small>}
        <p>{address(recommended)}</p>
        <button type="button" className="desk-button solid" disabled={busy} onClick={() => adopt(recommended)}><IconCheck size={17} />Als Gericht in die Akte übernehmen</button>
      </article> : <p className="storage-notice">Das passende Gericht ist in der Antwort des Verzeichnisses nicht eindeutig. Bitte unten auswählen und prüfen.</p>}
      {/* The directory also lists the rest of the court hierarchy (appeal courts, public prosecutors). */}
      <details open={!recommended}><summary>Weitere Gerichte und Behörden im Bezirk ({result.courts.length - (recommended ? 1 : 0)})</summary>
        {result.courts.filter(court => court !== recommended).map(court => <article key={court.name} className="court-card">
          <h3>{court.name}</h3>{court.remark && <small>{court.remark}</small>}<p>{address(court)}</p>
          {!recommended && <button type="button" className="desk-button" disabled={busy} onClick={() => adopt(court)}>Dieses Gericht übernehmen</button>}
        </article>)}
      </details>
      <p className="field-help">Quelle: <a href={result.source} target="_blank" rel="noreferrer">Orts- und Gerichtsverzeichnis <IconExternalLink size={13} /></a>, abgerufen am {result.checked_at.split("-").reverse().join(".")}. Gerichtsstandsvereinbarungen, Sonderzuständigkeiten (z. B. Kammer für Handelssachen, Spezialkammern) und Konzentrationen nach Landesrecht im Einzelfall prüfen.</p>
    </div>}
    {saved && <p role="status" className="storage-notice">Übernommen: <strong>{saved}</strong>. Klagen und Anträge aus Musterbibliothek und Schriftverkehr setzen dieses Gericht jetzt als Empfänger ein.</p>}
  </section>;
}
