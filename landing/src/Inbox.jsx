import { useCallback, useEffect, useRef, useState } from 'react';
import { IconInbox, IconUpload, IconEdit } from '@tabler/icons-react';
import { request, API_BASE } from './useCaseStorage.js';
import { dateLabel, localToday, matches } from './workbench.js';
import { DocumentReview } from './DocumentReview.jsx';
import './inbox.css';

const fields = item => ({subject:item?.subject || '', sender:item?.sender || '',received_on:item?.received_on || localToday(),note:item?.note || ''});

function IncomingFields({ value, onChange, de }) {
  const set = (key,event) => onChange({...value,[key]:event.target.value});
  return <div className="intake-grid">
    <label>{de ? 'Betreff (optional)' : 'Subject (optional)'}<input maxLength={160} value={value.subject} onChange={e=>set('subject',e)}/></label>
    <label>{de ? 'Absender (optional)' : 'Sender (optional)'}<input maxLength={160} value={value.sender} onChange={e=>set('sender',e)}/></label>
    <label>{de ? 'Eingangsdatum (manuell) *' : 'Received date (manual) *'}<input type="date" required value={value.received_on} onChange={e=>set('received_on',e)}/></label>
    <label>{de ? 'Interner Vermerk (optional)' : 'Internal note (optional)'}<textarea rows={2} maxLength={2000} value={value.note} onChange={e=>set('note',e)}/></label>
  </div>;
}

export function Inbox({ lang, cases, query = '', open, onChanged }) {
  const de = lang === 'de', fileInput = useRef(null), lifetime = useRef(null);
  const [items,setItems] = useState([]), [loading,setLoading] = useState(true), [loadError,setLoadError] = useState(false);
  const [busy,setBusy] = useState(false), [error,setError] = useState(''), [notice,setNotice] = useState(''), [status,setStatus] = useState('pending');
  const [metadata,setMetadata] = useState(()=>fields()), [selectedFiles,setSelectedFiles] = useState([]);
  const [editing,setEditing] = useState(null), [editFields,setEditFields] = useState(null), [assignment,setAssignment] = useState(null), [target,setTarget] = useState('');
  const [review,setReview] = useState(null);
  const reload = useCallback(async signal => {
    signal = signal || lifetime.current?.signal;
    setLoading(true); setLoadError(false);
    try { const data = await request('/inbox',{signal}); if (!signal?.aborted) setItems(data); }
    catch (failure) { if (failure.name !== 'AbortError') setLoadError(true); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(()=>{ const controller=new AbortController();lifetime.current=controller;reload(controller.signal);return ()=>controller.abort(); },[reload]);
  const update = item => setItems(current=>[item,...current.filter(value=>value.id!==item.id)].sort((a,b)=>b.created_at.localeCompare(a.created_at)));
  const visible = items.filter(item=>(status==='all' || (status==='pending' ? !item.case_id : Boolean(item.case_id))) && matches(query,item.original_name,item.subject,item.sender,item.note,item.case_reference,item.case_title));
  const fail = failure => {
    if (failure.status===409) { reload(); return de ? 'Dieser Eingang wurde bereits geändert oder zugeordnet. Liste neu geladen; bitte den aktuellen Stand öffnen.' : 'This entry has changed or been assigned. List reloaded; open the current entry.'; }
    return failure.status===404 ? (de ? 'Datei oder ausgewählte Akte ist nicht verfügbar.' : 'File or selected case unavailable.') : (de ? 'Speichern fehlgeschlagen. Angaben und Verbindung prüfen.' : 'Could not save. Check the fields and connection.');
  };
  const upload = async event => {
    event.preventDefault(); if (busy || !selectedFiles.length) return;
    setBusy(true);setError('');setNotice('');
    const signal = lifetime.current.signal;
    let saved=0;const failures=[];
    for (const file of selectedFiles) {
      if (signal.aborted) return;
      if (file.size>10*1024*1024) { failures.push(`${file.name}: ${de ? 'größer als 10 MB' : 'exceeds 10 MB'}`); continue; }
      const body = new FormData(); body.append('file',file);Object.entries(metadata).forEach(([key,value])=>body.append(key,value));
      try { update(await request('/inbox',{method:'POST',body,signal}));saved++; }
      catch (failure) { if (failure.name==='AbortError') return; failures.push(`${file.name}: ${failure.status===415 ? (de ? 'Format nicht unterstützt' : 'unsupported type') : failure.status===413 ? (de ? 'größer als 10 MB' : 'exceeds 10 MB') : (de ? 'Upload fehlgeschlagen' : 'upload failed')}`); }
    }
    if (signal.aborted) return;
    setBusy(false); setSelectedFiles([]);if(fileInput.current) fileInput.current.value='';
    setStatus('pending');setNotice(`${saved} ${de ? 'Datei(en) im Posteingang gespeichert.' : 'file(s) saved in the inbox.'}`);setError(failures.join(' · '));
  };
  const saveMetadata = async event => {
    event.preventDefault(); if (busy) return;setBusy(true);setError('');setNotice('');
    try { update(await request(`/inbox/${editing.id}`,{method:'PUT',signal:lifetime.current.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({...editFields,expected_version:editing.version})}));setEditing(null);setNotice(de ? 'Eingangsdaten gespeichert.' : 'Incoming metadata saved.'); }
    catch (failure) { setError(fail(failure)); } finally { setBusy(false); }
  };
  const assign = async event => {
    event.preventDefault(); if (busy || !target) return;setBusy(true);setError('');setNotice('');
    try {
      const item = await request(`/inbox/${assignment.id}/assign`,{method:'POST',signal:lifetime.current.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:target,expected_version:assignment.version})});
      update(item);setAssignment(null);setTarget('');setNotice(de ? `Datei der Akte ${item.case_reference} zugeordnet. Unter „Zugeordnet“ können Sie den Text prüfen.` : `File assigned to ${item.case_reference}. Open “Assigned” to review its text.`);onChanged?.();
    } catch (failure) { setError(fail(failure)); } finally { setBusy(false); }
  };
  const begin = (item, mode) => { setError('');setNotice(''); if(mode==='edit') { setEditing(item);setEditFields(fields(item)); } else {setAssignment(item);setTarget('');} };
  const editingOpen = Boolean(editing || assignment);
  return <section className="desk-panel inbox-panel">
    <div className="desk-panel-heading"><div><h2>{de ? 'Posteingang & Aktenzuordnung' : 'Inbox & case assignment'}</h2><p>{de ? 'Dateien aufnehmen, Eingangsdaten erfassen und ausdrücklich einer Akte zuordnen.' : 'Receive files, record incoming details and explicitly assign a case.'}</p></div><IconInbox size={28} aria-hidden="true"/></div>
    <details className="inbox-upload" open><summary>{de ? 'Dokumente in den Posteingang hochladen' : 'Upload documents to the inbox'}</summary>
      <form onSubmit={upload}><fieldset disabled={busy || loading}><label>{de ? 'Dateien auswählen *' : 'Choose files *'}<input ref={fileInput} type="file" multiple required accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.zip" onChange={e=>setSelectedFiles(Array.from(e.target.files))}/></label><p className="field-help">{de ? 'PDF, DOC, DOCX, PNG, JPG oder ZIP · maximal 10 MB je Datei. Die folgenden Angaben gelten für alle ausgewählten Dateien und können vor der Zuordnung bearbeitet werden.' : 'PDF, DOC, DOCX, PNG, JPG or ZIP · up to 10 MB per file. These details apply to all selected files and can be edited before assignment.'}</p><IncomingFields value={metadata} onChange={setMetadata} de={de}/><div className="inbox-actions"><span>{selectedFiles.length} {de ? 'Datei(en) ausgewählt' : 'file(s) selected'}</span><button className="desk-button solid" disabled={busy || loading || !selectedFiles.length}><IconUpload size={17}/>{busy ? '…' : de ? 'Im Posteingang speichern' : 'Save to inbox'}</button></div></fieldset></form>
    </details>
    <div className="inbox-filters"><label>{de ? 'Ansicht' : 'View'}<select value={status} onChange={e=>setStatus(e.target.value)}><option value="pending">{de ? 'Ohne Aktenzuordnung' : 'Unassigned'}</option><option value="assigned">{de ? 'Zugeordnet' : 'Assigned'}</option><option value="all">{de ? 'Alle Eingänge' : 'All incoming files'}</option></select></label><span>{items.filter(item=>!item.case_id).length} {de ? 'ohne Aktenzuordnung' : 'unassigned'} · {items.filter(item=>item.case_id).length} {de ? 'zugeordnet' : 'assigned'}</span></div>
    {loading && <p role="status" className="desk-footnote">{de ? 'Posteingang wird geladen …' : 'Loading inbox …'}</p>}{loadError && <p role="alert" className="storage-error">{de ? 'Posteingang nicht erreichbar.' : 'Inbox unavailable.'} <button className="desk-link" onClick={()=>reload()}>{de ? 'Erneut versuchen' : 'Retry'}</button></p>}
    {notice && <p role="status" className="inbox-notice">{notice}</p>}{error && <p role="alert" className="inbox-error">{error}</p>}
    {editing && <form className="inbox-editor" onSubmit={saveMetadata}><h3>{de ? 'Eingangsdaten bearbeiten' : 'Edit incoming details'} · {editing.original_name}</h3><fieldset disabled={busy}><IncomingFields value={editFields} onChange={setEditFields} de={de}/></fieldset><div className="inbox-actions"><button type="button" className="desk-button" disabled={busy} onClick={()=>{setEditing(null);setError('');}}>{de ? 'Abbrechen' : 'Cancel'}</button><button className="desk-button solid" disabled={busy}>{de ? 'Eingangsdaten speichern' : 'Save incoming details'}</button></div></form>}
    {assignment && <form className="inbox-editor" onSubmit={assign}><h3>{de ? 'Datei einer Akte zuordnen' : 'Assign file to a case'}</h3><p><strong>{assignment.original_name}</strong> · {assignment.sender || '—'} · {dateLabel(assignment.received_on,lang)}</p><label>{de ? 'Zielakte auswählen *' : 'Select target case *'}<select required value={target} disabled={busy} onChange={e=>setTarget(e.target.value)}><option value="">{de ? 'Aktenzeichen und Angelegenheit auswählen …' : 'Choose reference and matter …'}</option>{cases.map(item=><option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label><p className="field-help">{de ? 'Bitte die Zielakte prüfen. Das Original bleibt erhalten; die Zuordnung bleibt anschließend an diese Akte gebunden. Datum und Vermerke erzeugen keine Frist.' : 'Check the target case. The original is retained; assignment then remains bound to this case. Dates and notes do not create a deadline.'}</p>{!cases.length && <p>{de ? 'Legen Sie zuerst über „Neue Akte“ eine Akte an.' : 'Create a case using “New case” first.'}</p>}<div className="inbox-actions"><button type="button" className="desk-button" disabled={busy} onClick={()=>{setAssignment(null);setError('');}}>{de ? 'Abbrechen' : 'Cancel'}</button><button className="desk-button solid" disabled={busy || !target}>{de ? 'Dieser Akte zuordnen' : 'Assign to this case'}</button></div></form>}
    {visible.length ? <div className="desk-table-scroll"><table className="desk-table"><thead><tr><th>{de ? 'Datei / Betreff' : 'File / subject'}</th><th>{de ? 'Absender / Eingang' : 'Sender / received'}</th><th>{de ? 'Akte / Status' : 'Case / status'}</th><th>{de ? 'Aktion' : 'Action'}</th></tr></thead><tbody>{visible.map(item=><tr key={item.id}><td><strong>{item.original_name}</strong><small>{item.subject}</small><small>{Math.max(1,Math.ceil(item.size_bytes/1024))} KB</small>{item.note && <details className="inbox-note"><summary>{de ? 'Interner Vermerk' : 'Internal note'}</summary><p>{item.note}</p></details>}</td><td>{item.sender || '—'}<small>{dateLabel(item.received_on,lang)}</small></td><td>{item.case_id ? <><button className="desk-link" onClick={()=>open(item.case_id,'documents')}>{item.case_reference}</button><small>{de ? 'Zugeordnet' : 'Assigned'} · {dateLabel(item.assigned_at,lang)}</small><small>{item.reviewed_units ? `${item.reviewed_units} ${de ? 'geprüfte Stellen' : 'reviewed passages'}` : de ? 'Text noch nicht geprüft' : 'Text not reviewed yet'}</small></> : <span className="desk-tag">{de ? 'Offen' : 'Unassigned'}</span>}</td><td><div className="inbox-row-actions"><a className="desk-link" href={`${API_BASE}/api/inbox/${item.id}/download`}>{de ? 'Original herunterladen' : 'Download original'}</a>{item.case_id ? <button className="desk-link" disabled={busy} onClick={()=>setReview({...item,id:item.document_id,caseItem:{id:item.case_id,reference:item.case_reference}})}>{de ? 'Text prüfen' : 'Review text'}</button> : <><button className="desk-link" disabled={busy || loading || editingOpen} onClick={()=>begin(item,'edit')}><IconEdit size={15}/>{de ? 'Eingangsdaten bearbeiten' : 'Edit incoming details'}</button><button className="desk-button" disabled={busy || loading || editingOpen} onClick={()=>begin(item,'assign')}>{de ? 'Akte zuordnen' : 'Assign case'}</button></>}</div></td></tr>)}</tbody></table></div> : !loading && !loadError && <p className="desk-empty">{de ? 'Keine Eingänge in dieser Auswahl. Dateien hochladen oder Ansicht ändern.' : 'No files in this view. Upload files or change the view.'}</p>}
    <p className="desk-footnote">{de ? 'Dateiupload als Posteingang; E-Mail-Postfächer sind noch nicht angebunden. Keine automatische Aktenzuordnung, Fristberechnung oder OCR. In der Akte geprüfte PDF-/DOCX-Stellen können Sie für die Recherche auswählen.' : 'File uploads act as incoming mail; email accounts are not connected. No automatic case assignment, deadline calculation or OCR. Select reviewed PDF/DOCX passages from the case for research.'}</p>
    {review && <DocumentReview key={review.id} document={review} lang={lang} onClose={()=>setReview(null)} onChanged={()=>{reload();onChanged?.();}}/>}
  </section>;
}
