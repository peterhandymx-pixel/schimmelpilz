import { lazy, Suspense, useEffect, useState } from "react";
import { IconDownload, IconX } from "@tabler/icons-react";
import { API_BASE } from "./useCaseStorage.js";

const PdfPreview = lazy(() => import("./PdfPreview.jsx"));
const IMAGE = /\.(png|jpe?g)$/i;

// Shows an uploaded original as it is: PDFs page by page, photos as images. Word files are only offered for download.
export function DocumentViewer({ lang = "de", caseId, document, onClose }) {
  const de = lang === "de";
  const [url, setUrl] = useState(""), [error, setError] = useState("");
  const pdf = /\.pdf$/i.test(document.original_name) || document.content_type === "application/pdf";
  const image = IMAGE.test(document.original_name);
  const downloadUrl = `${API_BASE}/api/cases/${caseId}/documents/${document.id}/download`;
  useEffect(() => {
    if (!pdf && !image) return undefined;
    let objectUrl = "", alive = true;
    fetch(downloadUrl, { credentials: "include", headers: { "X-Schimmelpilz-Request": "1" } })
      .then(response => { if (!response.ok) throw new Error(); return response.blob(); })
      .then(blob => { if (!alive) return; objectUrl = URL.createObjectURL(pdf ? new Blob([blob], { type: "application/pdf" }) : blob); setUrl(objectUrl); })
      .catch(() => alive && setError(de ? "Das Dokument konnte nicht geladen werden." : "Could not load the document."));
    return () => { alive = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [downloadUrl]);
  return <section className="document-viewer" aria-label={document.original_name}>
    <div className="document-viewer-head"><strong>{document.original_name}</strong>
      <span><a className="desk-link" href={downloadUrl} download><IconDownload size={15} />{de ? "Herunterladen" : "Download"}</a>
        {onClose && <button type="button" className="desk-link" onClick={onClose}><IconX size={15} />{de ? "Schließen" : "Close"}</button>}</span></div>
    {error ? <p className="storage-error">{error}</p>
      : !pdf && !image ? <p className="field-help">{de ? "Für diese Dateiart gibt es keine Vorschau. Bitte herunterladen und öffnen." : "No preview for this file type. Please download and open it."}</p>
      : !url ? <p role="status">{de ? "Dokument wird geladen …" : "Loading document …"}</p>
      : pdf ? <Suspense fallback={<p role="status">{de ? "Vorschau wird geladen …" : "Loading preview …"}</p>}><PdfPreview src={url} lang={lang} title={document.original_name} /></Suspense>
      : <img className="document-viewer-image" src={url} alt={document.original_name} />}
  </section>;
}
