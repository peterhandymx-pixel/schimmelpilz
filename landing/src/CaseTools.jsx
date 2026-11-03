import { useState } from 'react';
import { IconArchive, IconDownload, IconTrash } from '@tabler/icons-react';
import { request, API_BASE } from './useCaseStorage.js';
import './account-settings.css';

export function CaseTools({ item, lang, onChanged, canDelete = false, onDeleted }) {
  const de=lang==='de';
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[confirm,setConfirm]=useState('');
  const remove=async event=>{
    event.preventDefault();if(busy)return;setBusy(true);setError('');
    try{await request(`/cases/${item.id}?confirm=${encodeURIComponent(confirm.trim())}`,{method:'DELETE'});onDeleted?.();}
    catch(failure){setError(failure.status===422?(de?'Das eingegebene Aktenzeichen stimmt nicht.':'The reference entered does not match.'):failure.status===403?(de?'Nur die Inhaberin / der Inhaber des Arbeitsbereichs kann Akten löschen.':'Only the workspace owner can delete cases.'):(de?'Löschen fehlgeschlagen.':'Deletion failed.'));setBusy(false);}
  };
  const toggle=async()=>{
    if(busy)return;setBusy(true);setError('');
    try{await request(`/cases/${item.id}/archive`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({archived:!item.archived_at,expected_version:item.archive_version||0})});await onChanged?.();}
    catch(failure){setError(failure.status===409?(de?'Archivstand wurde geändert. Bitte Akte neu laden.':'Archive state changed. Reload the case.'):(de?'Archivieren / Wiederherstellen fehlgeschlagen.':'Could not change archive state.'));}
    finally{setBusy(false);}
  };
  return <div className="case-tools"><div className="cost-actions"><button className="desk-button" disabled={busy} onClick={toggle}><IconArchive size={17}/>{item.archived_at?(de?'Aus Archiv wiederherstellen':'Restore from archive'):(de?'Akte archivieren':'Archive case')}</button><a className="desk-button" href={`${API_BASE}/api/cases/${item.id}/export.zip`}><IconDownload size={17}/>{de?'Akte als ZIP exportieren':'Export case as ZIP'}</a></div>{item.archived_at&&<p className="storage-notice">{de?'Archiviert. Originaldateien und Bearbeitungsverlauf bleiben erhalten; die Akte kann wiederhergestellt werden.':'Archived. Original files and activity remain; the case can be restored.'}</p>}<p className="field-help">{de?'ZIP enthält vertrauliche Akteninformationen, Originaldateien und gespeicherte Fassungen (bis 200 MB). Sicher aufbewahren. Archivieren löscht nichts.':'ZIP contains confidential case records, original files and saved versions (up to 200 MB). Keep it secure. Archiving deletes nothing.'}</p>{canDelete&&<details className="account-danger"><summary><IconTrash size={16}/> {de?'Akte endgültig löschen':'Permanently delete case'}</summary><p>{de?`Löscht die Akte ${item.reference} mit allen Dokumenten, Entwürfen, Fristen, Recherchen, Kostenprüfungen und dem Verlauf. Dateien aus dem Posteingang kehren in den Posteingang zurück. Laden Sie die Akte vorher als ZIP herunter, wenn Sie sie aufbewahren müssen.`:`Deletes case ${item.reference} with all documents, drafts, deadlines, research, cost reviews and activity. Inbox files return to the inbox. Export the case as ZIP first if you must keep it.`}</p><form className="account-form" onSubmit={remove}><label>{de?`Zur Bestätigung Aktenzeichen ${item.reference} eingeben`:`Type the reference ${item.reference} to confirm`}<input value={confirm} onChange={e=>setConfirm(e.target.value)} autoComplete="off" required/></label><button className="desk-button danger" disabled={busy||confirm.trim().toLowerCase()!==item.reference.toLowerCase()}>{de?'Akte endgültig löschen':'Permanently delete case'}</button></form></details>}{error&&<p role="alert" className="storage-error">{error}</p>}</div>;
}
