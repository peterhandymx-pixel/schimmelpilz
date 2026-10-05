import { useEffect, useRef, useState, lazy, Suspense } from 'react';
import { API_BASE, request } from './useCaseStorage.js';
import { pdfRequest } from './pdfExport.js';
import { authRequest } from './useAuth.js';

const defaults = {top_mm:70, bottom_mm:30, left_mm:25, right_mm:25, font_size:11};
const PdfPreview = lazy(() => import('./PdfPreview.jsx'));

export function LetterheadSetup({lang, onReady, onboarding = false}) {
  const de = lang === 'de';
  const [active, setActive] = useState(null), [candidate, setCandidate] = useState(null), [layout, setLayout] = useState(defaults);
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [preview, setPreview] = useState(''), [confirmed, setConfirmed] = useState(false);
  const previewRef = useRef('');
  const clearPreview = () => { if (previewRef.current) URL.revokeObjectURL(previewRef.current); previewRef.current = ''; setPreview(''); setConfirmed(false); };
  useEffect(() => {
    const pending = new AbortController();
    request('/auth/letterheads', {signal:pending.signal}).then(data => {
      if (pending.signal.aborted) return;
      const current = data.items.find(item => item.id === data.active_id) || null;
      setActive(current);
      const pendingTemplate = data.items.find(item => !item.confirmed_at && (!current || item.created_at > current.created_at));
      if (pendingTemplate) { setCandidate(pendingTemplate); setLayout(pendingTemplate.layout); }
    }).catch(failure => { if (failure.name !== 'AbortError') setError(de ? 'Briefkopf konnte nicht geladen werden.' : 'Could not load letterhead.'); }).finally(() => { if (!pending.signal.aborted) setLoading(false); });
    return () => { pending.abort(); if (previewRef.current) URL.revokeObjectURL(previewRef.current); };
  }, []);
  const upload = async event => {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form);
    const file = data.get('file');
    if (!file?.size) return;
    if (file.size > 10 * 1024 * 1024) { setError(de ? 'Maximal 10 MB.' : 'Maximum 10 MB.'); return; }
    setBusy(true); setError(''); setNotice(''); clearPreview();
    try { const result = await request('/auth/letterheads', {method:'POST', body:data}); setCandidate(result); setLayout(result.layout); form.reset(); }
    catch (failure) { setError(failure.status === 503 ? (de ? 'Die Word-Umwandlung ist nicht erreichbar. Laden Sie den Briefkopf als PDF hoch.' : 'Word conversion is unavailable. Upload the letterhead as PDF.') : failure.status === 429 ? (de ? 'Eine andere Vorlage wird gerade verarbeitet. Bitte erneut versuchen.' : 'Another template is being processed. Please retry.') : (de ? 'Bitte eine gültige, unverschlüsselte PDF-, DOC- oder DOCX-Briefpapiervorlage mit einer oder zwei gleich großen Hochformatseiten verwenden. PDF-Vorlagen müssen ohne Formularfelder, Links und Seitenbeschnitt sein.' : 'Use a valid, unencrypted PDF, DOC or DOCX letter-paper template with one or two matching portrait pages. PDF templates must have no form fields, links or cropped pages.')); }
    finally { setBusy(false); }
  };
  const showPreview = async () => {
    setBusy(true); setError(''); clearPreview();
    try { const blob = await pdfRequest(`/auth/letterheads/${candidate.id}/preview`, layout); const url = URL.createObjectURL(blob); previewRef.current = url; setPreview(url); }
    catch { setError(de ? 'Vorschau fehlgeschlagen. Prüfen Sie den verfügbaren Schreibbereich.' : 'Preview failed. Check the available writing area.'); }
    finally { setBusy(false); }
  };
  const activate = async () => {
    setBusy(true); setError('');
    try { const result = await request(`/auth/letterheads/${candidate.id}/activate`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...layout, confirmed})}); setActive(result); setCandidate(null); clearPreview(); setNotice(de ? 'Briefkopf für alle neuen Schriftsätze gespeichert.' : 'Letterhead saved for all new drafts.'); onReady?.(await authRequest('me')); }
    catch { setError(de ? 'Briefkopf konnte nicht aktiviert werden. Bitte erneut versuchen.' : 'Could not activate letterhead. Please retry.'); }
    finally { setBusy(false); }
  };
  const skip = async () => {
    setBusy(true); setError('');
    try { onReady(await authRequest('me')); }
    catch { setError(de ? 'Der Arbeitsbereich konnte nicht geöffnet werden. Bitte erneut versuchen.' : 'Could not open the workspace. Please retry.'); }
    finally { setBusy(false); }
  };
  return <section className="letterhead-setup"><header><span className="desk-eyebrow">{onboarding ? (de ? 'SCHRITT 2 · BRIEFPAPIER' : 'STEP 2 · LETTER PAPER') : (de ? 'IHR BRIEFPAPIER' : 'YOUR LETTER PAPER')}</span><h2>{de ? 'Ihr Briefkopf. In jedem Schriftsatz.' : 'Your letterhead. In every document.'}</h2><p>{de ? 'Laden Sie leeres Briefpapier hoch, ohne Empfänger oder alten Brieftext. Eine Seite wird auf allen Seiten wiederholt; bei zwei Seiten gilt Seite 1 für den Anfang und Seite 2 für alle Folgeseiten.' : 'Upload blank letter paper without recipient or old letter text. One page repeats throughout; with two pages, page 1 is the first page and page 2 is used for all continuation pages.'}</p></header>
    {onboarding && <p className="storage-notice">{de ? 'Ihr Konto wurde angelegt. Richten Sie jetzt das Briefpapier ein oder ergänzen Sie es später im Kontoprofil.' : 'Your account was created. Set up letter paper now or add it later in your profile.'}</p>}
    {loading && <p role="status">{de ? 'Briefpapier wird geladen …' : 'Loading letter paper …'}</p>}
    {active && <p className="letterhead-active"><strong>{de ? 'Aktiver Briefkopf: ' : 'Active letterhead: '}{active.original_name}</strong><a className="desk-link" href={`${API_BASE}/api/auth/letterheads/${active.id}/pdf`} target="_blank" rel="noreferrer">{de ? 'Vorlage ansehen' : 'View template'} ↗</a></p>}
    <form onSubmit={upload}><fieldset disabled={busy || loading}><label>{de ? 'Briefkopf als PDF, DOC oder DOCX (max. 10 MB)' : 'Letterhead as PDF, DOC or DOCX (max. 10 MB)'}<input name="file" type="file" accept=".pdf,.doc,.docx" required /></label><p className="field-help">{de ? 'PDF erhält das Layout ohne Skalierung. Word-Dateien werden lokal in PDF umgewandelt; prüfen Sie dabei Schriften und Umbrüche in der Vorschau.' : 'PDF preserves layout without scaling. Word files are converted locally to PDF; check fonts and line breaks in the preview.'}</p><button className="desk-button" type="submit">{busy ? (de ? 'Wird verarbeitet …' : 'Processing …') : (de ? 'Briefkopf hochladen' : 'Upload letterhead')}</button></fieldset></form>
    {candidate && <div className="letterhead-candidate"><h3>{candidate.original_name}</h3><p>{candidate.geometry.width_mm} × {candidate.geometry.height_mm} mm · {candidate.geometry.pages} {de ? 'Vorlagenseite(n)' : 'template page(s)'}</p><a className="desk-link" href={`${API_BASE}/api/auth/letterheads/${candidate.id}/pdf`} target="_blank" rel="noreferrer">{de ? 'Umgewandeltes Briefpapier öffnen' : 'Open converted letter paper'} ↗</a><fieldset disabled={busy} className="letterhead-layout"><legend>{de ? 'Freien Schreibbereich einstellen' : 'Set the clear writing area'}</legend>{[['top_mm', de ? 'Abstand oben (mm)' : 'Top margin (mm)'], ['bottom_mm', de ? 'Abstand unten (mm)' : 'Bottom margin (mm)'], ['left_mm', de ? 'Abstand links (mm)' : 'Left margin (mm)'], ['right_mm', de ? 'Abstand rechts (mm)' : 'Right margin (mm)'], ['font_size', de ? 'Textgröße (pt)' : 'Text size (pt)']].map(([key,label]) => <label key={key}>{label}<input type="number" min={key === 'font_size' ? 8 : 5} max={key === 'font_size' ? 16 : 160} step="1" value={layout[key]} onChange={event => { setLayout(current => ({...current,[key]:Number(event.target.value)})); clearPreview(); }} /></label>)}</fieldset><button className="desk-button" onClick={showPreview} disabled={busy}>{de ? 'Vorschau mit Mustertext erstellen' : 'Create sample-text preview'}</button>{preview && <><Suspense fallback={<p role="status">…</p>}><PdfPreview src={preview} lang={lang} title={de ? 'Briefkopf mit Mustertext' : 'Letterhead with sample text'} /></Suspense><a className="desk-link" href={preview} target="_blank" rel="noreferrer">{de ? 'Vorschau in groß öffnen' : 'Open full preview'} ↗</a><label className="desk-checkbox"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={busy} />{de ? 'Das Briefpapier entspricht meinem Original; der Text überdeckt weder Briefkopf noch Fußzeile.' : 'The letter paper matches my original; text covers neither the header nor footer.'}</label><button className="desk-button solid" onClick={activate} disabled={busy || !confirmed}>{de ? 'Für neue Schriftsätze verwenden' : 'Use for new drafts'}</button></>}</div>}
    {error && <p role="alert" className="storage-error">{error}</p>}{notice && <p role="status" className="storage-notice">{notice}</p>}{onboarding && <button className="text-link" type="button" disabled={busy} onClick={skip}>{de ? 'Später einrichten · zum Arbeitsbereich' : 'Set up later · open workspace'}</button>}<p className="desk-footnote">{de ? 'Der bestätigte PDF-Briefkopf wird unverändert als Hintergrund eingefügt. Der Schreibbereich gilt für alle Seiten. Gespeicherte Entwürfe behalten ihre Briefkopfversion; eine neue Vorlage gilt für danach neu angelegte Entwürfe. Textdateien enthalten keinen grafischen Briefkopf.' : 'The confirmed PDF letterhead is inserted unchanged as the background. The writing area applies to all pages. Saved drafts retain their letterhead version; a new template applies to subsequently created drafts. Text files do not contain graphic letterheads.'}</p>
  </section>;
}
