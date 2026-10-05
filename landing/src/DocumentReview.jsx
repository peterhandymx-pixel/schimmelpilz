import { useEffect, useRef, useState } from "react";
import { IconX, IconFileText, IconCheck } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";

export function DocumentReview({ document, lang, onClose, onChanged }) {
  const dialog = useRef(null), [data, setData] = useState(null), [index, setIndex] = useState(0);
  const [text, setText] = useState(""), [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(true), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const de = lang === "de", base = `/cases/${document.caseItem.id}/documents/${document.id}`;
  const unit = data?.units[index], page = data?.extraction?.unit_kind === "page";
  useEffect(() => {
    if (!dialog.current.open) dialog.current.showModal();
    const pending = new AbortController();
    request(base + "/text", { signal: pending.signal }).then(setData).catch(failure => { if (failure.name !== "AbortError") setError(de ? "Text konnte nicht geladen werden." : "Could not load document text."); }).finally(() => { if (!pending.signal.aborted) setBusy(false); });
    return () => pending.abort();
  }, [base]);
  useEffect(() => { setText(unit?.reviewed_text ?? unit?.original_text ?? ""); setReviewed(Boolean(unit?.reviewed_at)); }, [unit]);
  const extract = async () => {
    setBusy(true); setError("");
    try { setData(await request(base + "/extract", { method: "POST" })); onChanged?.(); }
    catch (failure) { setError(failure.status === 429 ? (de ? "Eine andere Datei wird gerade ausgelesen. Bitte erneut versuchen." : "Another file is being extracted. Please retry.") : (de ? "Auslesen fehlgeschlagen. Die Originaldatei bleibt erhalten." : "Extraction failed. The original file is retained.")); }
    finally { setBusy(false); }
  };
  const save = async event => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      setData(await request(base + `/text/${unit.unit_no}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, reviewed }) }));
      setNotice(de ? "Text und Prüfstatus gespeichert." : "Text and review status saved."); onChanged?.();
    } catch { setError(de ? "Speichern fehlgeschlagen. Ihre Eingabe bleibt erhalten." : "Save failed. Your input is retained."); }
    finally { setBusy(false); }
  };
  const status = data?.extraction?.status;
  return <dialog ref={dialog} className="document-review" aria-labelledby="document-review-title" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <header><div><span className="desk-eyebrow">{de ? "DOKUMENTTEXT PRÜFEN" : "REVIEW DOCUMENT TEXT"}</span><h2 id="document-review-title">{document.original_name}</h2><p>{document.caseItem.reference}</p></div><button className="desk-link" aria-label={de ? "Textprüfung schließen" : "Close text review"} onClick={onClose} disabled={busy}><IconX size={21} /></button></header>
    <div className="document-review-body"><p className="document-review-note">{de ? "Vergleichen Sie den Text mit der Originaldatei. Geprüft bedeutet: Textübertragung kontrolliert – keine Bestätigung der Tatsachen oder rechtliche Freigabe. Nur geprüfte Stellen können Sie für die KI auswählen." : "Compare the text with the original file. Reviewed means transcription checked, not confirmation of facts or legal approval. Only reviewed passages can be selected for AI."}</p>
      <a className="desk-link" href={`${API_BASE}/api${base}/download`}>{de ? "Originaldatei herunterladen" : "Download original file"}</a>
      {busy && <p role="status">{de ? "Dokument wird verarbeitet …" : "Processing document …"}</p>}
      {data && !data.extraction && <div className="document-extract-intro"><IconFileText size={32} /><h3>{de ? "Text lokal auslesen" : "Extract text locally"}</h3><p>{de ? "PDFs mit Textschicht und DOCX-Haupttext. Scans, Bilder und alte DOC-Dateien benötigen OCR oder eine andere Aufbereitung. DOCX-Stellen sind Abschnitte, keine Seiten." : "PDF text layers and DOCX body text. Scans, images and legacy DOC files require OCR or another preparation method. DOCX locations are sections, not pages."}</p><button className="desk-button solid" onClick={extract} disabled={busy}>{de ? "Text auslesen" : "Extract text"}</button></div>}
      {status === "no_text" && <p className="storage-notice">{de ? "Keine Textschicht gefunden. OCR erforderlich; sie ist noch nicht angebunden. Sie können den Text dieser Seite aus dem Original manuell übertragen." : "No text layer found. OCR is required and is not connected yet. You can transcribe this page manually from the original."}</p>}
      {status === "unsupported" && <p className="storage-notice">{de ? "Dieses Format wird noch nicht ausgelesen. Verwenden Sie eine PDF-Datei mit Textschicht oder DOCX." : "This format cannot be extracted yet. Use a text-layer PDF or DOCX."}</p>}
      {status === "failed" && <p className="storage-error">{data.extraction.error_code === "encrypted" ? (de ? "Diese PDF-Datei ist verschlüsselt. Laden Sie eine lesbare Kopie hoch." : "This PDF is encrypted. Upload a readable copy.") : (de ? "Datei nicht lesbar oder Verarbeitungsgrenze erreicht. Laden Sie eine kleinere, gültige PDF-/DOCX-Datei hoch." : "Unreadable file or processing limit reached. Upload a smaller valid PDF/DOCX file.")}</p>}
      {Boolean(data?.extraction?.truncated) && <p className="storage-notice">{de ? "Der Text wurde begrenzt ausgelesen. Es wurden höchstens 80 Seiten/Abschnitte, 12.000 Zeichen je Stelle und 120.000 Zeichen insgesamt übernommen. Prüfen Sie fehlende Stellen im Original." : "Extraction was limited to 80 pages/sections, 12,000 characters per location and 120,000 characters total. Check missing passages in the original."}</p>}
      {unit && <form onSubmit={save}><fieldset disabled={busy}><label>{page ? (de ? "PDF-Seite" : "PDF page") : (de ? "DOCX-Abschnitt" : "DOCX section")}<select value={index} onChange={event => setIndex(Number(event.target.value))}>{data.units.map((entry, position) => <option key={entry.unit_no} value={position}>{entry.unit_no} · {entry.reviewed_at ? (de ? "Geprüft" : "Reviewed") : (de ? "Ungeprüft" : "Not reviewed")}</option>)}</select></label><details><summary>{de ? "Ursprünglich ausgelesenen Text anzeigen" : "Show original extracted text"}</summary><pre>{unit.original_text || (de ? "Keine Textschicht." : "No text layer.")}</pre></details><label>{de ? "Text dieser Stelle" : "Text at this location"}<textarea rows={12} maxLength={12000} value={text} onChange={event => { setText(event.target.value); setReviewed(false); }} /></label><label className="document-review-check"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />{de ? "Ich habe den Text mit dem Original abgeglichen." : "I have compared the text with the original."}</label><div className="document-review-actions"><span>{reviewed ? (de ? "Nach dem Speichern für die KI auswählbar" : "Selectable for AI after saving") : (de ? "Nicht für die KI freigegeben" : "Not available to AI")}</span><button className="desk-button solid" disabled={reviewed && !text.trim()}><IconCheck size={16} />{de ? "Text & Prüfstatus speichern" : "Save text & review status"}</button></div></fieldset></form>}
      {notice && <p className="storage-notice" role="status">{notice}</p>}{error && <p className="storage-error" role="alert">{error}</p>}
    </div>
  </dialog>;
}
