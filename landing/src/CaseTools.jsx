import { useState } from 'react';
import { IconArchive, IconDownload } from '@tabler/icons-react';
import { request, API_BASE } from './useCaseStorage.js';

export function CaseTools({ item, lang, onChanged }) {
  const de=lang==='de';
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const toggle=async()=>{
    if(busy)return;setBusy(true);setError('');
    try{await request(`/cases/${item.id}/archive`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({archived:!item.archived_at,expected_version:item.archive_version||0})});await onChanged?.();}
    catch(failure){setError(failure.status===409?(de?'Archivstand wurde geändert. Bitte Akte neu laden.':'Archive state changed. Reload the case.'):(de?'Archivieren / Wiederherstellen fehlgeschlagen.':'Could not change archive state.'));}
    finally{setBusy(false);}
  };
  return <div className="case-tools"><div className="cost-actions"><button className="desk-button" disabled={busy} onClick={toggle}><IconArchive size={17}/>{item.archived_at?(de?'Aus Archiv wiederherstellen':'Restore from archive'):(de?'Akte archivieren':'Archive case')}</button><a className="desk-button" href={`${API_BASE}/api/cases/${item.id}/export.zip`}><IconDownload size={17}/>{de?'Akte als ZIP exportieren':'Export case as ZIP'}</a></div>{item.archived_at&&<p className="storage-notice">{de?'Archiviert. Originaldateien und Bearbeitungsverlauf bleiben erhalten; die Akte kann wiederhergestellt werden.':'Archived. Original files and activity remain; the case can be restored.'}</p>}<p className="field-help">{de?'ZIP enthält vertrauliche Akteninformationen, Originaldateien und gespeicherte Fassungen (bis 200 MB). Sicher aufbewahren. Archivieren löscht nichts.':'ZIP contains confidential case records, original files and saved versions (up to 200 MB). Keep it secure. Archiving deletes nothing.'}</p>{error&&<p role="alert" className="storage-error">{error}</p>}</div>;
}
