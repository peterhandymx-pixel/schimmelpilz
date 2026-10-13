import {useEffect, useRef, useState, lazy, Suspense} from 'react';
import {pdfRequest, downloadBlob} from './pdfExport.js';
const PdfPreview = lazy(() => import('./PdfPreview.jsx'));

export function DraftPdfPreview({lang, caseId, draftId, body, useCurrentLetterhead}) {
  const de = lang === 'de';
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [url, setUrl] = useState('');
  const objectUrl = useRef('');
  const clear = () => { if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); objectUrl.current = ''; setUrl(''); };
  useEffect(() => { clear(); return () => { if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); }; }, [body, draftId, caseId, useCurrentLetterhead]);
  const generate = async (download, format='pdf') => {
    setBusy(true); setError('');
    try {
      const blob = await pdfRequest(`/cases/${caseId}/drafts/${format==='docx'?'export-docx':'preview-pdf'}`, {body, draft_id:draftId, use_current_letterhead:useCurrentLetterhead});
      if (download) downloadBlob(blob, `Schimmelpilz-Entwurf.${format}`);
      else { clear(); const value = URL.createObjectURL(blob); objectUrl.current = value; setUrl(value); }
    } catch { setError(de ? 'Datei konnte nicht erstellt werden. Prüfen Sie Text, Briefkopf und Schreibbereich im Kontoprofil.' : 'Could not create file. Check text, letterhead and writing area in your profile.'); }
    finally { setBusy(false); }
  };
  return <div className="draft-pdf-export"><p className="field-help">{de ? 'PDF-Ausgabe mit dem hinterlegten Briefpapier. Die Vorschau verwendet den aktuellen Editorinhalt; sie speichert oder versendet den Entwurf nicht.' : 'PDF output using your configured letter paper. Preview uses the current editor text; it does not save or send the draft.'}</p><div className="draft-pdf-actions"><button className="secondary-button" type="button" disabled={busy || !body.trim()} onClick={() => generate(false)}>{de ? 'PDF-Vorschau mit Briefkopf' : 'PDF preview with letterhead'}</button><button className="secondary-button" type="button" disabled={busy || !body.trim()} onClick={() => generate(true)}>{busy ? '…' : de ? 'PDF herunterladen' : 'Download PDF'}</button><button className="secondary-button" type="button" disabled={busy || !body.trim()} onClick={() => generate(true, "docx")}>{de ? "Word herunterladen" : "Download Word"}</button></div><p className="field-help">{de ? "Word: bearbeitbarer Text mit Briefpapier als festem Hintergrundbild. Darstellung und Seitenumbrüche können sich in Word ändern; die PDF-Ausgabe erhält das Originalbriefpapier. Änderungen in Word haben keine Freigabe aus diesem System." : "Word: editable text with letter paper as a fixed background image. Layout and page breaks may change in Word; PDF preserves the original letter paper. Word edits have no approval from this system."}</p>{url && <><Suspense fallback={<p role="status">…</p>}><PdfPreview src={url} lang={lang} title={de ? 'Schriftsatz mit Briefkopf' : 'Draft with letterhead'} /></Suspense><a className="text-link" href={url} target="_blank" rel="noreferrer">{de ? 'Vorschau in groß öffnen' : 'Open full preview'} ↗</a></>}{error && <p className="storage-error" role="alert">{error}</p>}</div>;
}
