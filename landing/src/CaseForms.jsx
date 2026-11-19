import { useState } from "react";
import { IconFileDownload, IconFiles } from "@tabler/icons-react";
import { API_BASE } from "./useCaseStorage.js";
import { downloadBlob } from "./pdfExport.js";
import "./tools.css";

const FORMS = [
  ["vollmacht", "Vollmacht", "Prozess- und Verfahrensvollmacht zum Unterschreiben"],
  ["mandatsbestaetigung", "Mandatsbestätigung", "Schreiben an den Mandanten: Mandat übernommen, Unterlagen anfordern"],
  ["kostenhinweis", "Hinweis zur Vergütung", "§ 49b Abs. 5 BRAO, bei Arbeitssachen mit Hinweis auf § 12a ArbGG"],
  ["datenschutz", "Datenschutzhinweise", "Informationen nach Art. 13 DSGVO für Mandanten"],
  ["schweigepflicht", "Schweigepflichtentbindung", "für Ärzte, Kliniken, Behörden und Versicherungen"],
];
const PACKAGE = ["vollmacht", "kostenhinweis", "datenschutz"];

// Standard client forms, filled from the case particulars and printed on the firm's letterhead.
export function CaseForms({ item }) {
  const [busy, setBusy] = useState(""), [error, setError] = useState("");
  const d = item.details || {};
  const missing = [!d.client_name && "Name des Mandanten", !d.client_address && "Anschrift des Mandanten"].filter(Boolean);
  const fetchForm = async kind => {
    const response = await fetch(`${API_BASE}/api/cases/${item.id}/forms/${kind}.pdf`, { credentials: "include", headers: { "X-Schimmelpilz-Request": "1" } });
    if (!response.ok) throw new Error(String(response.status));
    const title = FORMS.find(([id]) => id === kind)[1];
    downloadBlob(await response.blob(), `${title} ${item.reference.replace(/[\\/]/g, "-")}.pdf`);
  };
  const run = async (kinds, label) => {
    setBusy(label); setError("");
    try { for (const kind of kinds) await fetchForm(kind); }
    catch { setError("Formular konnte nicht erstellt werden."); }
    finally { setBusy(""); }
  };
  return <section className="desk-panel tool-panel">
    <div className="desk-panel-heading"><div><h2><IconFiles size={18} /> Formulare</h2>
      <p>Mit den Daten dieser Akte ausgefüllt, auf Ihrem Briefkopf (falls eingerichtet). Fehlende Angaben stehen als [Platzhalter] im Formular.</p></div>
      <button className="desk-button solid" disabled={Boolean(busy)} onClick={() => run(PACKAGE, "package")}><IconFileDownload size={17} />{busy === "package" ? "Wird erstellt …" : "Mandantenpaket (Vollmacht, Vergütung, Datenschutz)"}</button></div>
    {missing.length > 0 && <p className="storage-notice">Noch nicht erfasst: {missing.join(", ")}. Über „Aktenstammdaten bearbeiten“ ergänzen, dann sind die Formulare vollständig.</p>}
    {error && <p className="storage-error" role="alert">{error}</p>}
    <ul className="form-list">{FORMS.map(([id, title, hint]) => <li key={id}>
      <div><strong>{title}</strong><small>{hint}</small></div>
      <button className="desk-button" disabled={Boolean(busy)} onClick={() => run([id], id)}><IconFileDownload size={16} />{busy === id ? "…" : "PDF"}</button>
    </li>)}</ul>
  </section>;
}
