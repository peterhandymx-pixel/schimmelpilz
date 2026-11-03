import { IconFileSpreadsheet, IconFileTypeDocx, IconFileTypePdf } from "@tabler/icons-react";
import { API_BASE } from "./useCaseStorage.js";

// Plain links: downloads are GET requests authorised by the session cookie, like the ZIP and calendar exports.
export function SpreadsheetLinks({ path, lang, label, query = "" }) {
  const de = lang === "de", sep = query ? "&" : "?";
  return <span className="export-links" aria-label={label || (de ? "Liste exportieren" : "Export list")}><IconFileSpreadsheet size={16} aria-hidden="true" />{label || (de ? "Exportieren" : "Export")}:<a className="desk-link" href={`${API_BASE}${path}.csv${query}${sep}lang=${lang}`} download>CSV</a><a className="desk-link" href={`${API_BASE}${path}.xlsx${query}${sep}lang=${lang}`} download>Excel</a></span>;
}

export function DocumentLinks({ path, lang, query = "", label }) {
  const de = lang === "de", sep = query ? "&" : "?";
  return <span className="export-links" aria-label={label || (de ? "Dokument exportieren" : "Export document")}>{label && <>{label}:</>}<a className="desk-link" href={`${API_BASE}${path}.pdf${query}${sep}lang=${lang}`} download><IconFileTypePdf size={16} aria-hidden="true" />PDF</a><a className="desk-link" href={`${API_BASE}${path}.docx${query}${sep}lang=${lang}`} download><IconFileTypeDocx size={16} aria-hidden="true" />Word</a></span>;
}
