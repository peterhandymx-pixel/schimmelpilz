import {useEffect, useState} from 'react';
import {request} from './useCaseStorage.js';
import {dateLabel} from './workbench.js';
import {savedDraftPdf} from './pdfExport.js';
import './draft-review.css';

export const reviewLabels = {
  de:{draft:'Entwurf',in_review:'In Prüfung',approved:'Freigegeben · eigene Prüfung'},
  en:{draft:'Draft',in_review:'In review',approved:'Approved · user review'},
};
const checklist = {
  de:{facts:'Sachverhalt, Belege und fehlende Angaben',source_versions:'Passende Fassungen, Fundstellen und Aussagebezug',adverse_authority:'Gegenargumente und entgegenstehende Rechtsprechung',procedure_recipient_signature:'Zuständigkeit, Form, Fristen, Empfänger und Signatur'},
  en:{facts:'Facts, evidence and missing particulars',source_versions:'Applicable versions, passages and proposition support',adverse_authority:'Counterarguments and adverse authority',procedure_recipient_signature:'Jurisdiction, form, deadlines, recipient and signature'},
};
const eventLabels = {
  de:{created:'Entwurf erstellt',edited:'Fassung geändert',begin:'Prüfung begonnen',check:'Prüfvermerk gespeichert',approve:'Eigene Freigabe gespeichert',reopen:'Prüfung wieder geöffnet'},
  en:{created:'Draft created',edited:'Version changed',begin:'Review started',check:'Review note saved',approve:'User approval saved',reopen:'Review reopened'},
};
const flags = {
  de:{missing_recipient:'Empfänger fehlt (oder interne Verwendung angeben)',placeholder:'Offener Platzhalter',unknown_citation:'Quellen-ID ohne gespeicherte Originalpassage',no_linked_passage:'Keine Originalpassage zugeordnet; Tatsachen und unbelegte Aussagen selbst prüfen',source_review_open:'Eigene Quellenprüfung war bei der Recherche offen',limited_excerpt:'Nur begrenzter Auszug verfügbar'},
  en:{missing_recipient:'Recipient missing (or specify internal use)',placeholder:'Unfilled placeholder',unknown_citation:'Citation ID has no saved original passage',no_linked_passage:'No original passage mapped; review facts and unsupported statements yourself',source_review_open:'Source review was open at research time',limited_excerpt:'Only a limited excerpt available'},
};

function ReviewCheck({item,lang,disabled,onSave,documents}) {
  const de = lang === 'de';
  const [note,setNote] = useState(item.review?.note || ''), [checked,setChecked] = useState(Boolean(item.review?.checked));
  const title = item.kind === 'checklist' ? checklist[lang][item.id] : (de ? 'Aussagen in diesem Textblock' : 'Statements in this text block');
  return <details className="draft-review-check"><summary><span className={item.review?.checked ? 'review-resolved' : 'review-open'}>{item.review?.checked ? '✓' : '○'}</span> {title}</summary>
    <div className="draft-evidence-grid"><div><h4>{title}</h4>{item.kind === 'block' && <pre>{item.text}</pre>}{item.flags.map(flag => <p className="field-help" key={flag}>{flags[lang][flag]}</p>)}</div><div><h4>{de ? 'Übergebene Originalpassagen' : 'Supplied original passages'}</h4>{item.sources.map(source => <article className="draft-source-passage" key={source.citation_id}><strong>[{source.citation_id}] {source.title}</strong><p>{source.pinpoint}</p><a href={source.url} target="_blank" rel="noreferrer">{de ? 'Original öffnen' : 'Open original'} ↗</a><small>{source.metadata.version_note || [source.metadata.decision_date,source.metadata.reference,source.metadata.ecli].filter(Boolean).join(' · ')}<br />{de ? 'Abgerufen' : 'Retrieved'}: {source.fetched_at}</small><pre>{source.text}</pre></article>)}{item.id === 'facts' && documents.map((source,index) => <article className="draft-source-passage" key={index}><strong>{source.filename} · {source.unit_kind} {source.unit_no}</strong><pre>{source.text}</pre></article>)}{!item.sources.length && !(item.id === 'facts' && documents.length) && <p className="field-help">{de ? 'Manuelle Prüfung nötig. Ein Quellenverweis allein belegt die Aussage nicht.' : 'Manual review required. A citation alone does not establish support.'}</p>}</div></div>
    <form onSubmit={event => {event.preventDefault();onSave(item.id,checked,note);}}><fieldset disabled={disabled}><label><input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} />{de ? 'Für diese Fassung selbst geprüft' : 'Personally checked for this version'}</label><label>{de ? 'Prüfvermerk zu diesem Punkt' : 'Review note for this item'}<textarea value={note} onChange={event => setNote(event.target.value)} rows={2} maxLength={2500} minLength={checked ? 10 : undefined} required={checked} /></label><button type="submit" className="small-action">{de ? 'Prüfpunkt speichern' : 'Save review item'}</button></fieldset></form>
    {item.review && <small>{item.review.actor_name} · {dateLabel(item.review.updated_at,lang,true)}</small>}
  </details>;
}

export function DraftReview({lang,caseId,draft,dirty,busy,onUpdated}) {
  const de = lang === 'de';
  const [data,setData] = useState(null), [error,setError] = useState(''), [working,setWorking] = useState(false), [note,setNote] = useState(''), [confirmed,setConfirmed] = useState(false), [historical,setHistorical] = useState(null);
  useEffect(() => {
    const pending = new AbortController(); setData(null);setHistorical(null);setConfirmed(false);setNote('');setError('');
    if (draft?.id) request(`/cases/${caseId}/drafts/${draft.id}/review`,{signal:pending.signal}).then(result => {if (!pending.signal.aborted) setData(result);}).catch(failure => {if (failure.name !== 'AbortError') setError(de ? 'Prüfung konnte nicht geladen werden.' : 'Could not load review.');});
    return () => pending.abort();
  },[caseId,draft?.id,draft?.version]);
  const action = async (type,extra = {}) => {
    if (!data || dirty || working || busy || data.draft.version !== draft.version) return;
    setWorking(true);setError('');
    try {
      const result = await request(`/cases/${caseId}/drafts/${draft.id}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:type,expected_version:data.draft.version,expected_review_revision:data.draft.review_revision,...extra})});
      setData(result);onUpdated(result.draft);setConfirmed(false);
    } catch (failure) {setError(failure.status === 409 ? (de ? 'Fassung oder Prüfstand hat sich geändert, oder offene Punkte blockieren die Freigabe. Entwurf schließen und erneut öffnen.' : 'Version/review changed, or unresolved items prevent approval. Close and reopen the draft.') : (de ? 'Prüfvermerk und Bestätigung prüfen. Die Aktion wurde nicht gespeichert.' : 'Check the note and confirmation. The action was not saved.'));}
    finally {setWorking(false);}
  };
  const showVersion = async version => {
    setWorking(true);setError('');
    try {setHistorical(await request(`/cases/${caseId}/drafts/${draft.id}/versions/${version}`));}
    catch {setError(de ? 'Fassung nicht verfügbar.' : 'Version unavailable.');}
    finally {setWorking(false);}
  };
  const download = async () => {
    setWorking(true);setError('');
    try {await savedDraftPdf(`/cases/${caseId}/drafts/${draft.id}/pdf`,data.draft.version);}
    catch {setError(de ? 'Gespeicherte PDF-Fassung nicht verfügbar oder bereits geändert. Entwurf erneut öffnen.' : 'Saved PDF version unavailable or changed. Reopen the draft.');}
    finally {setWorking(false);}
  };
  if (!draft?.id) return <section className="draft-review-panel"><h3>{de ? 'Prüfung & Freigabe' : 'Review & approval'}</h3><p>{de ? 'Zuerst speichern. Danach können Sie diese Fassung mit ihren Originalpassagen prüfen und freigeben.' : 'Save first. Then review and approve this version with its original passages.'}</p></section>;
  const disabled = dirty || busy || working || !data || data.draft.version !== draft.version;
  return <section className="draft-review-panel" aria-label={de ? 'Prüfung & Freigabe' : 'Review & approval'}><header><h3>{de ? 'Prüfung & Freigabe' : 'Review & approval'}</h3>{data && <span className={`draft-review-badge ${dirty ? 'draft' : data.draft.review_status}`}>v{data.draft.version} · {dirty ? (de ? 'Ungespeicherte Änderungen' : 'Unsaved changes') : reviewLabels[lang][data.draft.review_status]}</span>}</header>
    <p>{de ? 'Quellenzuordnung ist technisch; Aussagebezug, Fakten, Gegenargumente und passende Fassung müssen Sie selbst prüfen. Eine Kontofreigabe bestätigt weder eine Anwaltszulassung noch eine unabhängige Rechtsprüfung.' : 'Source mapping is technical; review proposition support, facts, counterarguments and applicable versions yourself. Account approval verifies neither a lawyer licence nor independent legal review.'}</p>
    {dirty && <p className="storage-notice">{de ? 'Änderungen zuerst speichern. Inhalt, Sprache, Empfänger oder Briefkopf setzen eine bestehende Freigabe zurück und erzeugen eine neue Fassung.' : 'Save changes first. Content, language, recipient or letterhead changes reset approval and create a new version.'}</p>}
    {data && <><p><strong>{data.unresolved}</strong> {de ? 'offene Prüfpunkte' : 'unresolved review items'} · <strong>{data.hard_blocks.length}</strong> {de ? 'blockierende Angaben' : 'blocking particulars'}</p>{data.hard_blocks.length > 0 && <ul className="draft-review-blockers">{data.hard_blocks.map((item,index) => <li key={index}>{flags[lang][item.kind]}{item.text && ': '+item.text}</li>)}</ul>}
      {!draft.research_run_id && <p className="field-help">{de ? 'Kein strukturiertes Rechercheergebnis verbunden. Text im Quellenanhang wird nicht als verifizierte Quelle eingelesen. Für KI-Fundstellen einen neuen Entwurf aus Recherche übernehmen.' : 'No structured research result connected. Editable appendix text is not ingested as verified authority. Adopt a new draft from Research to retain AI source passages.'}</p>}
      {data.draft.review_status === 'draft' && <button type="button" disabled={disabled} className="desk-button" onClick={() => action('begin')}>{de ? 'Prüfung beginnen' : 'Begin review'}</button>}
      {data.checks.map(item => <ReviewCheck key={`${data.draft.version}:${item.id}`} item={item} lang={lang} documents={data.source_context.sources || []} disabled={disabled || data.draft.review_status !== 'in_review'} onSave={(id,checked,value) => action('check',{check_id:id,checked,note:value})} />)}
      {data.draft.review_status === 'in_review' && <form className="draft-approval" onSubmit={event => {event.preventDefault();action('approve',{note,confirmed});}}><fieldset disabled={disabled}><label>{de ? 'Freigabevermerk' : 'Approval note'}<textarea rows={2} required minLength={20} maxLength={2500} value={note} onChange={event => setNote(event.target.value)} /></label><label><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{de ? 'Ich bestätige meine eigene Prüfung dieser gespeicherten Fassung.' : 'I confirm my own review of this saved version.'}</label><button className="desk-button solid" type="submit" disabled={!data.can_approve || !confirmed || note.trim().length < 20}>{de ? 'Diese Fassung freigeben' : 'Approve this version'}</button></fieldset></form>}
      {data.draft.review_status === 'approved' && <div className="draft-approved-record"><p>{de ? 'Freigegeben durch' : 'Approved by'} <strong>{data.draft.approved_name}</strong> · v{data.draft.version} · {dateLabel(data.draft.approved_at,lang,true)}</p><button type="button" disabled={disabled} className="desk-button" onClick={() => action('reopen')}>{de ? 'Prüfung wieder öffnen' : 'Reopen review'}</button></div>}
      <button type="button" disabled={disabled} className="desk-button" onClick={download}>{de ? 'Gespeicherte Fassung als PDF' : 'Download saved version as PDF'} · v{data.draft.version}</button>
      <details className="draft-version-history"><summary>{de ? 'Fassungen & Prüfverlauf' : 'Versions & review history'} ({data.versions.length})</summary>{data.versions.map(version => <div className="draft-version-row" key={version.version}><span>v{version.version} · {dateLabel(version.created_at,lang,true)} · {version.actor_name || (de ? 'Vorhandene Fassung übernommen' : 'Existing version retained')}</span><button type="button" disabled={working} className="desk-link" onClick={() => showVersion(version.version)}>{de ? 'Fassung ansehen' : 'View version'}</button></div>)}{historical && <article className="draft-historical"><h4>{de ? 'Gespeicherte Fassung' : 'Saved version'} {historical.version}</h4><small>SHA-256: {historical.sha256}</small><pre>{historical.snapshot.body}</pre></article>}<ol>{data.events.map(event => <li key={event.id}><strong>v{event.version} · {eventLabels[lang][event.action] || event.action}</strong> · {event.actor_name} · {dateLabel(event.created_at,lang,true)}{event.note && <p>{event.note}</p>}</li>)}</ol></details>
    </>}{error && <p className="storage-error" role="alert">{error}</p>}</section>;
}
