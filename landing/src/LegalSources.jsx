import {useEffect, useState} from 'react';
import {request} from './useCaseStorage.js';
export {legalLedger} from './legalLedger.js';

export function CitedAnswer({answer,sources = []}) {
  const lookup = Object.fromEntries(sources.map(item => [`[${item.citation_id}]`,item]));
  return <p>{answer.split(/(\[L\d+\])/g).map((part,index) => lookup[part] ? <a key={index} href={lookup[part].url} target="_blank" rel="noreferrer" title={`${lookup[part].title} · ${lookup[part].pinpoint}`}>{part}</a> : part)}</p>;
}

export function LegalAnswerSources({lang,sources = [],audit = {},report = {}}) {
  const de = lang === 'de';
  if (!sources.length && !report.automatic && !audit.unknown?.length) return null;
  return <div className="legal-answer-sources">
    {(audit.unknown?.length > 0 || audit.missing_citations) && <p className="storage-error">{de ? 'Quellenverweise prüfen: ' : 'Check citations: '}{audit.unknown?.length ? audit.unknown.map(id => `[${id}]`).join(', ') + (de ? ' wurde nicht übergeben.' : ' was not supplied.') : (de ? 'Die KI nennt keine übergebene Quellen-ID.' : 'AI cites no supplied source ID.')}</p>}
    {!sources.length && report.automatic && <p className="storage-notice">{de ? 'Keine verwendbare Rechtsquelle gefunden. Diese Antwort ist kein belegtes Rechercheergebnis.' : 'No usable legal source found. This answer is not a sourced research result.'}</p>}
    {report.errors?.length > 0 && <p className="storage-notice">{de ? 'Einige Originalquellen konnten nicht abgerufen werden.' : 'Some original sources could not be retrieved.'}</p>}
    {sources.length > 0 && <details className="research-used-sources legal-ledger"><summary>{de ? 'Übergebene Rechtsquellen & Fundstellen' : 'Supplied legal sources & passages'} ({sources.length})</summary><p>{de ? 'Originalquelle und Quellen-ID technisch geprüft. Aussage, passende Fassung und Anwendung bleiben prüfpflichtig. Gespeicherte Auszüge ändern sich bei späteren Aktualisierungen nicht.' : 'Original source and citation IDs checked technically. Proposition, applicable version and application require review. Saved excerpts do not change with later updates.'}</p>{sources.map(item => <article key={item.citation_id} id={`source-${item.snapshot_id}-${item.citation_id}`}><strong>[{item.citation_id}] {item.title}</strong><p>{item.pinpoint} · {item.provider}</p><a href={item.url} target="_blank" rel="noreferrer">{de ? 'Originalquelle öffnen' : 'Open original source'} ↗</a><p>{item.metadata.version_note || [item.metadata.decision_type,item.metadata.decision_date,item.metadata.reference,item.metadata.ecli].filter(Boolean).join(' · ')}</p><small>{de ? 'Abgerufen' : 'Retrieved'}: {item.fetched_at} · {item.review_status === 'checked' ? (de ? 'Eigene Prüfung dokumentiert' : 'User review recorded') : (de ? 'Rechtliche Prüfung offen' : 'Legal review open')}</small><pre>{item.text}</pre>{item.excerpt_truncated && <small>{de ? 'Begrenzter Auszug' : 'Limited excerpt'}</small>}</article>)}</details>}
  </div>;
}

function SourceReview({item,lang,onSaved,busy}) {
  const de = lang === 'de', [note,setNote] = useState(item.review_note || ''), [status,setStatus] = useState(item.review_status), [error,setError] = useState(''), [saving,setSaving] = useState(false);
  const save = async event => {
    event.preventDefault(); setSaving(true); setError('');
    try { const result = await request(`/cases/${item.case_id}/legal-sources/${item.id}/review`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,note})}); onSaved(result); }
    catch { setError(de ? 'Prüfung konnte nicht gespeichert werden. Für „geprüft“ bitte Fassung, Relevanz und Fundstelle beschreiben (mindestens 10 Zeichen).' : 'Could not save review. For “checked”, describe version, relevance and passage (at least 10 characters).'); }
    finally { setSaving(false); }
  };
  return <details className="legal-source-review"><summary>{de ? 'Passagen ansehen & eigene Prüfung dokumentieren' : 'Inspect passages & record your review'}</summary><p>{item.snapshot.metadata.version_note || [item.snapshot.metadata.decision_type,item.snapshot.metadata.decision_date,item.snapshot.metadata.ecli].filter(Boolean).join(' · ')}</p><p>{de ? 'Abgerufen' : 'Retrieved'}: {item.snapshot.fetched_at}</p><div className="legal-full-passages">{item.snapshot.units.map((unit,index) => <div key={index}><strong>{unit.pinpoint}</strong><pre>{unit.text}</pre></div>)}</div><form onSubmit={save}><fieldset disabled={busy || saving}><label>{de ? 'Prüfstatus' : 'Review status'}<select aria-label={de ? 'Prüfstatus' : 'Review status'} value={status} onChange={event => setStatus(event.target.value)}><option value="pending">{de ? 'Offen' : 'Open'}</option><option value="checked">{de ? 'Fassung, Relevanz und Fundstelle selbst geprüft' : 'Version, relevance and passage checked by me'}</option><option value="excluded">{de ? 'Von Antworten ausschließen' : 'Exclude from answers'}</option></select></label><label>{de ? 'Prüfvermerk' : 'Review note'}<textarea maxLength={1500} minLength={status === 'checked' ? 10 : undefined} required={status === 'checked'} value={note} onChange={event => setNote(event.target.value)} rows={2} /></label><button type="submit" className="desk-button">{de ? 'Prüfung speichern' : 'Save review'}</button></fieldset></form>{error && <p role="alert" className="storage-error">{error}</p>}<small>{de ? 'Diese Selbstauskunft ist keine unabhängige Rechtsprüfung oder Freigabe des Schriftsatzes.' : 'This self-declaration is not independent legal review or document approval.'}</small></details>;
}

export function LegalSourcePanel({lang,caseId,jurisdiction,busy,selected,setSelected,automatic,setAutomatic,revision}) {
  const de = lang === 'de';
  const [status,setStatus] = useState(null), [attached,setAttached] = useState([]), [query,setQuery] = useState(''), [kind,setKind] = useState('all'), [results,setResults] = useState([]), [error,setError] = useState(''), [working,setWorking] = useState(false), [searched,setSearched] = useState(false);
  const load = async signal => {
    try {
      const [state,items] = await Promise.all([request('/legal/status',{signal}),caseId ? request(`/cases/${caseId}/legal-sources`,{signal}) : Promise.resolve([])]);
      if (!signal?.aborted) { setStatus(state); setAttached(items); }
    } catch (failure) { if (failure.name !== 'AbortError') setError(de ? 'Quellenkatalog derzeit nicht erreichbar.' : 'Source catalogue currently unavailable.'); }
  };
  useEffect(() => { const pending = new AbortController(); load(pending.signal); return () => pending.abort(); },[caseId,revision]);
  useEffect(() => {
    if (!status?.progress.running) return;
    const pending = new AbortController();
    const timer = setInterval(() => load(pending.signal),2500);
    return () => {clearInterval(timer);pending.abort();};
  },[status?.progress.running,caseId]);
  const search = async event => {
    event.preventDefault();setWorking(true);setError('');
    try { const data = await request(`/legal/search?q=${encodeURIComponent(query.trim())}&kind=${kind}`); setResults(data.results);setStatus(data.coverage);setSearched(true); }
    catch {setError(de ? 'Lokale Suche fehlgeschlagen.' : 'Local search failed.');}
    finally {setWorking(false);}
  };
  const add = async key => {
    setWorking(true);setError('');
    try {
      const item = await request(`/cases/${caseId}/legal-sources`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});
      setAttached(items => [item,...items.filter(value => value.id !== item.id)]);
      if (item.review_status !== 'excluded') setSelected(ids => ids.includes(item.id) || ids.length >= 8 ? ids : [...ids,item.id]);
    } catch {setError(de ? 'Originalquelle nicht verfügbar oder nicht zum Katalog passend. Es wurde keine geprüfte Quelle erfunden.' : 'Original source unavailable or inconsistent with the catalogue. No verified source was fabricated.');}
    finally {setWorking(false);}
  };
  const refresh = async () => {
    setWorking(true);setError('');
    try {await request('/legal/refresh',{method:'POST'});await load();}
    catch {setError(de ? 'Aktualisierung konnte nicht gestartet werden.' : 'Could not start refresh.');}
    finally {setWorking(false);}
  };
  const allowed = (jurisdiction || 'DE') === 'DE';
  return <section className="legal-source-panel" aria-label={de ? 'Rechtsquellen für die KI' : 'Legal sources for AI'}><header><div><span className="desk-eyebrow">{de ? 'ORIGINALQUELLEN' : 'PRIMARY SOURCES'}</span><h3>{de ? 'Gesetze, Urteile & Beschlüsse' : 'Legislation, judgments & orders'}</h3></div><button type="button" className="desk-link" onClick={refresh} disabled={working || busy || status?.progress.running}>{de ? 'Katalog aktualisieren' : 'Refresh catalogue'}</button></header>
    <p className="legal-coverage">{status ? `${status.counts.law || 0} ${de ? 'Vorschriften' : 'provisions'} · ${status.counts.decision || 0} ${de ? 'Entscheidungen im Index' : 'indexed decisions'} · ${status.downloaded_decisions} ${de ? 'Entscheidungen im Volltext' : 'downloaded decisions'}` : (de ? 'Katalog wird geladen …' : 'Loading catalogue …')}</p>
    <p>{de ? 'Suche bleibt lokal. Öffentliches XML wird direkt vom Anbieter geladen; Aktenangaben werden nicht an Suchdienste übermittelt. Gesetzestexte sind konsolidierte Fassungen des Angebots, keine amtliche Verkündung. Sachverhaltsdatum und passende Fassung selbst prüfen.' : 'Search stays local. Public XML is downloaded directly from the provider; case details are not sent to search services. Statutes are consolidated provider texts, not official promulgation. Check event date and applicable version.'}</p>
    <details><summary>{de ? 'Abdeckung & Aktualität' : 'Coverage & freshness'}</summary><p>{status?.laws.join(', ')} · {de ? 'Bundesrecht DE. Entscheidungssuche nach Thema nur in heruntergeladenen Volltexten; Aktenzeichen im gesamten veröffentlichten Bundesgerichtsindex. Keine vollständige Rechtsprechungs- oder historische Fassungsabdeckung. EU, Mexiko und Landesgerichte sind nicht angebunden.' : 'German federal law. Topic search uses downloaded decision texts; reference search uses the published federal index. No complete case-law or historical-version coverage. EU, Mexico and state courts are not connected.'}</p>{status?.collections.map(item => <p key={item.key}>{item.key} · {de ? 'Katalogstand' : 'Catalogue update'}: {item.updated_at}</p>)}</details>
    {status?.progress.running && <p role="status">{de ? 'Aktualisierung' : 'Refresh'}: {status.progress.completed}/{status.progress.total} · {status.progress.current}</p>}
    {status?.progress.errors.length > 0 && <p className="storage-notice">{de ? 'Nicht aktualisiert: ' : 'Not refreshed: '}{status.progress.errors.join(', ')}</p>}
    {!allowed && <p className="storage-notice">{de ? 'Für diese Rechtsordnung ist noch kein Quellenadapter eingerichtet. Deutsche Quellen werden nicht automatisch angewandt.' : 'No source adapter is configured for this jurisdiction. German sources are not applied automatically.'}</p>}
    <label className="legal-auto"><input type="checkbox" checked={automatic && allowed} disabled={!allowed || busy} onChange={event => setAutomatic(event.target.checked)} />{de ? 'Passende Quellen aus dem lokalen Katalog automatisch zur Frage suchen' : 'Automatically find matching sources in the local catalogue'}</label>
    <details className="legal-find"><summary>{de ? 'Quelle gezielt suchen und zur Akte hinzufügen' : 'Find a specific source and add it to this case'}</summary><form className="legal-search" onSubmit={search}><fieldset disabled={working || busy || !allowed}><label>{de ? 'Rechtsbegriff, Norm oder gerichtliches Aktenzeichen' : 'Legal term, provision or court reference'}<input value={query} onChange={event => setQuery(event.target.value)} required minLength={2} maxLength={200} placeholder="§ 535 BGB / VIII ZR 109/18" /></label><label>{de ? 'Quellenart' : 'Source type'}<select aria-label={de ? 'Quellenart' : 'Source type'} value={kind} onChange={event => setKind(event.target.value)}><option value="all">{de ? 'Alle Quellen' : 'All sources'}</option><option value="law">{de ? 'Gesetz' : 'Legislation'}</option><option value="decision">{de ? 'Urteil / Beschluss' : 'Judgment / order'}</option></select></label><button type="submit" className="desk-button">{working ? '…' : (de ? 'Lokal suchen' : 'Search locally')}</button></fieldset></form>{searched && !results.length && <p>{de ? 'Keine Treffer in diesem Katalog. Dies belegt nicht, dass keine passende Norm oder Entscheidung existiert.' : 'No matches in this catalogue. This does not establish that no relevant provision or decision exists.'}</p>}<div className="legal-results">{results.map(item => <article key={item.key}><strong>{item.title}</strong><small>{item.metadata.version_note || item.metadata.decision_date} · {item.fetched_at ? (de ? 'Originaltext abgerufen' : 'Original text retrieved') : (de ? 'Indexeintrag – Originaltext noch laden' : 'Index entry – original text not yet loaded')}</small><a href={item.url} target="_blank" rel="noreferrer">{de ? 'Original öffnen' : 'Open original'} ↗</a><button type="button" className="desk-button" disabled={!caseId || working || busy} onClick={() => add(item.key)}>{de ? 'Original laden & zur Akte hinzufügen' : 'Load original & add to case'}</button></article>)}</div></details>
    {attached.length > 0 && <details className="legal-attached"><summary>{de ? 'Quellen in dieser Akte auswählen & prüfen' : 'Select & review sources in this case'} ({attached.length})</summary><p>{de ? 'Höchstens 8 Quellen auswählen. Die KI erhält höchstens 8 Fundstellen mit zusammen 9.000 Zeichen. Eigene Prüfvermerke ersetzen keine unabhängige Rechtsprüfung.' : 'Select up to 8 sources. AI receives at most 8 passages totalling 9,000 characters. Your review notes do not replace independent legal review.'}</p>{attached.map(item => <article key={item.id}><label><input type="checkbox" checked={selected.includes(item.id)} disabled={busy || item.review_status === 'excluded' || (!selected.includes(item.id) && selected.length >= 8)} onChange={event => setSelected(ids => event.target.checked ? [...ids,item.id] : ids.filter(id => id !== item.id))} /><span><strong>{item.snapshot.title}</strong><small>{item.review_status === 'checked' ? (de ? 'Eigene Prüfung dokumentiert' : 'User review recorded') : item.review_status === 'excluded' ? (de ? 'Ausgeschlossen' : 'Excluded') : (de ? 'Original abgerufen · Rechtsprüfung offen' : 'Original retrieved · legal review open')}</small></span></label><a href={item.snapshot.url} target="_blank" rel="noreferrer">{de ? 'Originalquelle' : 'Original source'} ↗</a><SourceReview item={item} lang={lang} busy={busy} onSaved={value => {setAttached(items => items.map(old => old.id === value.id ? value : old));if (value.review_status === 'excluded') setSelected(ids => ids.filter(id => id !== value.id));}} /></article>)}</details>}
    {error && <p role="alert" className="storage-error">{error}</p>}
  </section>;
}
