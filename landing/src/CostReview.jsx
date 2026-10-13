import { useCallback, useEffect, useRef, useState } from 'react';
import { IconReceipt, IconPlus, IconTrash } from '@tabler/icons-react';
import { request, API_BASE } from './useCaseStorage.js';
import { dateLabel, matches } from './workbench.js';
import './cost-review.css';
import { FeeLookup } from './FeeLookup.jsx';

const newLine = () => ({description:'',quantity:'1',unit_net:'',tax_rate:'0',billed_net:'',evidence:''});
const blank = () => ({title:'',kind:'invoice',issuer:'',invoice_number:'',invoice_date:'',document_id:'',basis:'',notes:'',currency:'EUR',credit_gross:'0',billed_total:'',lines:[newLine()]});
const kinds = {de:{invoice:'Verbraucher- / Geschäftsrechnung',lawyer:'Anwaltsrechnung',court:'Gerichtskosten',operating:'Betriebskosten'},en:{invoice:'Consumer / business invoice',lawyer:'Lawyer invoice',court:'Court costs',operating:'Operating costs'}};
const normalize = value => String(value).trim().replace(',', '.');
const payloadFor = form => ({...form,invoice_date:form.invoice_date || null,document_id:form.document_id || null,credit_gross:normalize(form.credit_gross),billed_total:normalize(form.billed_total),lines:form.lines.map(row=>({...row,quantity:normalize(row.quantity),unit_net:normalize(row.unit_net),tax_rate:normalize(row.tax_rate),billed_net:row.billed_net.trim() ? normalize(row.billed_net) : null}))});

function Result({ result, form, lang }) {
  const de = lang==='de', money = value => `${Number(normalize(value)).toLocaleString(de?'de-DE':'en-GB',{minimumFractionDigits:2,maximumFractionDigits:2})} ${form.currency}`;
  return <section className="cost-result" aria-label={de?'Rechenergebnis':'Calculation result'}>
    <h3>{result.has_difference ? (de?'Rechnerische Abweichung gefunden':'Arithmetic difference found') : (de?'Rechnung rechnerisch stimmig':'Invoice arithmetic matches')}</h3>
    <p>{de?'Rechenprüfung anhand Ihrer Eingaben · rechtliche Berechtigung nicht geprüft.':'Arithmetic check using your inputs · legal entitlement not assessed.'}</p>
    <dl>{[[de?'Netto':'Net',result.net],[de?'Steuer':'Tax',result.tax],[de?'Brutto':'Gross',result.gross],[de?'Abzüge brutto':'Gross credits',form.credit_gross],[de?'Errechnet zahlbar':'Calculated payable',result.payable],[de?'Rechnung zahlbar':'Billed payable',form.billed_total],[de?'Differenz (Rechnung − errechnet)':'Difference (billed − calculated)',result.difference]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{money(value)}</dd></div>)}</dl>
    {result.lines.map((row,index)=>row.difference && row.difference!=='0.00' ? <p className="cost-difference" key={index}>{de?'Position':'Line'} {index+1}: {money(row.difference)} {de?'Abweichung beim Nettobetrag':'difference in net amount'}</p>:null)}
    <p className="field-help">{de?'Rundung: Positionsnetto kaufmännisch auf Cent, Steuer je Steuersatzgruppe auf Cent. Abzüge werden vom Brutto abgezogen. Negative Positionen für steuerwirksame Gutschriften. Eine positive Differenz bedeutet: Die Rechnung verlangt mehr als errechnet.':'Rounding: line net half-up to cents, tax per rate group to cents. Credits deduct from gross. Use negative lines for credits affecting tax. A positive difference means the invoice requests more than calculated.'}</p>
    <div className="cost-tax-groups">{result.tax_groups.map(group=><span key={group.rate}>{group.rate}%: {money(group.net)} → {money(group.tax)}</span>)}</div>
  </section>;
}

export function CostReview({ lang, cases, caseId='', query='', open, onChanged, onDraft }) {
  const de=lang==='de', life=useRef(null);
  const [items,setItems]=useState([]),[loading,setLoading]=useState(true),[loadError,setLoadError]=useState(false),[busy,setBusy]=useState(false);
  const [target,setTarget]=useState(caseId),[form,setForm]=useState(blank),[editing,setEditing]=useState(null),[result,setResult]=useState(null),[saved,setSaved]=useState(null),[versions,setVersions]=useState([]),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const selected=cases.find(item=>item.id===target);
  const reload=useCallback(async signal=>{
    signal=signal || life.current?.signal;setLoading(true);setLoadError(false);
    try {const data=await request(`/cost-reviews${caseId?`?case_id=${encodeURIComponent(caseId)}`:''}`,{signal});if(!signal?.aborted)setItems(data);}
    catch(failure){if(failure.name!=='AbortError')setLoadError(true);}
    finally{if(!signal?.aborted)setLoading(false);}
  },[caseId]);
  useEffect(()=>{const controller=new AbortController();life.current=controller;reload(controller.signal);return()=>controller.abort();},[reload]);
  const invalidate = () => {setResult(null);setSaved(null);setNotice('');setError('');};
  const change = next => {setForm(next);invalidate();};
  const set=(key,value)=>{setForm(current=>({...current,[key]:value}));invalidate();};
  const line=(index,key,value)=>{setForm(current=>({...current,lines:current.lines.map((row,i)=>i===index?{...row,[key]:value,...(key==='unit_net'?{fee_basis:null}:{})}:row)}));invalidate();};
  const reset=()=>{setForm(blank());setEditing(null);setTarget(caseId);setResult(null);setSaved(null);setVersions([]);setError('');setNotice('');};
  const loadItem=async item=>{
    setBusy(true);
    setEditing(item);setTarget(item.case_id);setForm({...item.invoice,invoice_date:item.invoice.invoice_date||'',document_id:item.invoice.document_id||'',lines:item.invoice.lines.map(row=>({...row,billed_net:row.billed_net??''}))});setResult(item.result);setSaved(item);setVersions([]);setError('');setNotice('');
    try{const history=await request(`/cost-reviews/${item.id}/versions`,{signal:life.current.signal});if(!life.current.signal.aborted)setVersions(history);}catch(failure){if(failure.name!=='AbortError')setError(de?'Versionsverlauf konnte nicht geladen werden.':'Could not load version history.');}finally{if(!life.current.signal.aborted)setBusy(false);}
  };
  const submit=async event=>{
    event.preventDefault();if(busy)return;
    const shouldSave=event.nativeEvent.submitter?.value==='save';
    if(shouldSave&&!target){setError(de?'Bitte eine Akte auswählen.':'Please select a case.');return;}
    setBusy(true);setError('');setNotice('');
    try{
      const invoice=payloadFor(form);
      if(!shouldSave){setResult(await request('/cost-reviews/calculate',{method:'POST',signal:life.current.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(invoice)}));setSaved(null);}
      else{
        const item=await request(`/cost-reviews${editing?`/${editing.id}`:''}`,{method:editing?'PUT':'POST',signal:life.current.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({...invoice,case_id:target,...(editing?{expected_version:editing.version}:{})})});
        setEditing(item);setSaved(item);setResult(item.result);setItems(current=>[item,...current.filter(row=>row.id!==item.id)]);setVersions(current=>[{version:item.version,invoice:item.invoice,result:item.result,saved_at:item.updated_at},...current]);setNotice(de?'Prüfung und Ergebnis zur Akte gespeichert.':'Review and result saved to the case.');onChanged?.();
      }
    }catch(failure){if(failure.name==='AbortError')return;setError(failure.status===409?(de?'Die Prüfung wurde zwischenzeitlich geändert. Ihre Eingaben bleiben erhalten. Aktuelle Fassung aus der Liste öffnen.':'Review changed elsewhere. Your inputs remain. Open the current version from the list.'):(de?'Prüfung fehlgeschlagen. Zahlen ohne Tausendertrennzeichen eingeben (z. B. 1234,56); Menge/Satz max. 4 Nachkommastellen, Gesamtbeträge max. 2. Akte und Verbindung prüfen.':'Check failed. Enter numbers without thousands separators (e.g. 1234.56); quantity/rate up to 4 decimals, totals up to 2. Check the case and connection.'));if(failure.status===409)reload();}
    finally{if(!life.current.signal.aborted)setBusy(false);}
  };
  const letter=()=>{
    if(!saved||!selected)return;
    const inv=saved.invoice,r=saved.result;
    const body=de?`Betreff: Bitte um Erläuterung Ihrer Rechnung ${inv.invoice_number}\n\nSehr geehrte Damen und Herren,\n\nbitte erläutern Sie die Berechnung Ihrer Rechnung ${inv.invoice_number} vom ${inv.invoice_date||'[Datum ergänzen]'}. Auf Grundlage der bisher erfassten Positionen ergibt sich ein zahlbarer Betrag von ${r.payable} ${inv.currency}; angegeben sind ${inv.billed_total} ${inv.currency}. Die rechnerische Differenz beträgt ${r.difference} ${inv.currency}.\n\nBitte prüfen Sie insbesondere die folgenden Positionen und übersenden Sie die zugrunde liegenden Belege und Berechnungsgrundlagen:\n${inv.lines.map((row,i)=>`${i+1}. ${row.description} — ${row.evidence||'[Beleg ergänzen]'}`).join('\n')}\n\nDiese Anfrage beruht auf einer vorläufigen Rechenprüfung; sie enthält keine abschließende rechtliche Bewertung.\n\nMit freundlichen Grüßen\n[Name]`:`Subject: Request for explanation of invoice ${inv.invoice_number}\n\nDear Sir or Madam,\n\nPlease explain invoice ${inv.invoice_number} dated ${inv.invoice_date||'[add date]'}. The recorded items give a payable amount of ${r.payable} ${inv.currency}; the invoice states ${inv.billed_total} ${inv.currency}. The arithmetic difference is ${r.difference} ${inv.currency}.\n\nPlease check the following items and supply the supporting documents and calculation basis:\n${inv.lines.map((row,i)=>`${i+1}. ${row.description} — ${row.evidence||'[add evidence]'}`).join('\n')}\n\nThis request is based on a preliminary arithmetic check and contains no final legal assessment.\n\nYours faithfully,\n[Name]`;
    onDraft?.({body,language:lang,kind:'letter',recipient:inv.issuer},selected);
  };
  return <div className="cost-workspace">
    <section className="desk-panel"><div className="desk-panel-heading"><div><h2>{de?'Rechnungen & Kosten prüfen':'Check invoices & costs'}</h2><p>{de?'Positionen nachrechnen, Abweichungen festhalten und Prüfberichte zur Akte speichern.':'Recalculate items, record differences and save review reports to the case.'}</p></div><IconReceipt size={28}/></div>
      <FeeLookup key={`${target}:${form.currency}`} lang={lang} enabled={Boolean(!busy&&selected&&(selected.details?.jurisdiction||'DE')==='DE'&&form.currency==='EUR'&&form.lines.length<100)} onAdd={(fee,basis)=>{const row={...newLine(),description:`${fee.statute.toUpperCase()} · 1,0-Wertgebühr`,unit_net:fee.base_fee,fee_basis:basis,evidence:`${fee.source.citation} · Wert ${fee.value} EUR`};change({...form,lines:form.lines.length===1&&!form.lines[0].description&&!form.lines[0].unit_net?[row]:[...form.lines,row]});}}/>
      <form onSubmit={submit}><fieldset disabled={busy}><div className="cost-form-grid">
        <label>{de?'Akte *':'Case *'}<select required value={target} disabled={Boolean(caseId||editing)} onChange={e=>{setTarget(e.target.value);change({...form,document_id:''});}}><option value="">{de?'Akte auswählen':'Select case'}</option>{cases.map(item=><option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>
        <label>{de?'Bezeichnung *':'Title *'}<input required maxLength={160} value={form.title} onChange={e=>set('title',e.target.value)}/></label>
        <label>{de?'Rechnungsart':'Invoice type'}<select value={form.kind} onChange={e=>set('kind',e.target.value)}>{Object.entries(kinds[lang]).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        <label>{de?'Aussteller':'Issuer'}<input maxLength={160} value={form.issuer} onChange={e=>set('issuer',e.target.value)}/></label>
        <label>{de?'Rechnungsnummer':'Invoice number'}<input maxLength={100} value={form.invoice_number} onChange={e=>set('invoice_number',e.target.value)}/></label>
        <label>{de?'Rechnungsdatum':'Invoice date'}<input type="date" value={form.invoice_date} onChange={e=>set('invoice_date',e.target.value)}/></label>
        <label>{de?'Beleg aus der E-Akte':'Document from electronic file'}<select value={form.document_id} onChange={e=>set('document_id',e.target.value)}><option value="">{de?'Kein Dokument verknüpft':'No document linked'}</option>{(selected?.documents||[]).map(doc=><option key={doc.id} value={doc.id}>{doc.name||doc.original_name}</option>)}</select></label>
        <label>{de?'Währung':'Currency'}<select value={form.currency} onChange={e=>set('currency',e.target.value)}>{['EUR','USD','MXN'].map(value=><option key={value}>{value}</option>)}</select></label>
      </div>
      <p className="field-help">{de?'Manuelle Eingabe: Netto-Einzelpreis × Menge oder Gebührensatz. Steuersatz ausdrücklich eingeben. Gutschriften als negative Netto-Positionen erfassen.':'Manual input: net unit price × quantity or fee multiplier. Enter tax rates explicitly. Record tax-affecting credits as negative net lines.'}</p>
      <div className="desk-table-scroll"><table className="cost-lines"><caption>{de?'Rechnungspositionen':'Invoice items'}</caption><thead><tr>{(de?['Position / Beleg','Menge / Satz','Einzelpreis netto','Steuer %','Rechnungsnetto (optional)','']:['Item / evidence','Qty / factor','Net unit price','Tax %','Billed net (optional)','']).map((value,i)=><th key={i}>{value}</th>)}</tr></thead><tbody>{form.lines.map((row,index)=><tr key={index}><td><input aria-label={`${de?'Position':'Item'} ${index+1}`} required maxLength={300} value={row.description} onChange={e=>line(index,'description',e.target.value)}/><input aria-label={`${de?'Beleg':'Evidence'} ${index+1}`} placeholder={de?'Beleg / Seite / VV-Nr.':'Evidence / page / fee code'} maxLength={500} value={row.evidence} onChange={e=>line(index,'evidence',e.target.value)}/>{row.fee_basis&&<small>{row.fee_basis.statute.toUpperCase()} · {row.fee_basis.version} · {row.fee_basis.value} EUR<br/>{de?"Einzelpreis ändern entfernt den Tabellenbezug.":"Changing unit price removes the table reference."}</small>}</td>{['quantity','unit_net','tax_rate','billed_net'].map((key,i)=><td key={key}><input aria-label={`${(de?['Menge / Satz','Einzelpreis netto','Steuer','Rechnungsnetto']:['Quantity / factor','Net unit price','Tax','Billed net'])[i]} ${index+1}`} inputMode="decimal" required={key!=='billed_net'} value={row[key]} onChange={e=>line(index,key,e.target.value)}/></td>)}<td><button type="button" className="desk-button" disabled={form.lines.length===1} aria-label={`${de?'Position entfernen':'Remove item'} ${index+1}`} onClick={()=>change({...form,lines:form.lines.filter((_,i)=>i!==index)})}><IconTrash size={16}/></button></td></tr>)}</tbody></table></div>
      <button type="button" className="desk-button" disabled={form.lines.length>=100} onClick={()=>change({...form,lines:[...form.lines,newLine()]})}><IconPlus size={16}/>{de?'Position hinzufügen':'Add item'}</button>
      <div className="cost-form-grid cost-totals"><label>{de?'Abzüge / Vorschüsse brutto':'Gross credits / advances'}<input inputMode="decimal" required value={form.credit_gross} onChange={e=>set('credit_gross',e.target.value)}/></label><label>{de?'Rechnung: zahlbarer Gesamtbetrag *':'Invoice: total payable *'}<input inputMode="decimal" required value={form.billed_total} onChange={e=>set('billed_total',e.target.value)}/></label></div>
      <label>{de?'Prüfgrundlage / Tabellenstand / offene Rechtsfragen':'Review basis / table version / unresolved legal issues'}<textarea rows={3} maxLength={3000} value={form.basis} onChange={e=>set('basis',e.target.value)} placeholder={de?'Vertrag, Wertfestsetzung, Gebührenvereinbarung, VV-Nr., geltende Fassung …':'Contract, value decision, fee agreement, fee code, applicable version …'}/></label>
      {['lawyer','court'].includes(form.kind)&&<p className="field-help">{de?'Gebührentatbestand, Wert, Tabellenversion und Anrechnung manuell prüfen. Die einfachen Wertgebührentabellen 2025 sind oben verfügbar. Gebührentatbestand, Satz, Sonderregeln und Anrechnung werden nicht automatisch rechtlich geprüft.':'Manually verify the fee item, value, table version and credits. The basic 2025 value-fee tables are available above. Fee events, multipliers, special rules and credits are not automatically assessed legally.'} <a href="https://www.gesetze-im-internet.de/rvg/__13.html" target="_blank" rel="noreferrer">RVG § 13</a> · <a href="https://www.gesetze-im-internet.de/rvg/__60.html" target="_blank" rel="noreferrer">RVG § 60</a> · <a href="https://www.gesetze-im-internet.de/gkg_2004/" target="_blank" rel="noreferrer">GKG</a> · <a href="https://www.gesetze-im-internet.de/famgkg/" target="_blank" rel="noreferrer">FamGKG</a></p>}
      <label>{de?'Prüfvermerk':'Review note'}<textarea rows={2} maxLength={4000} value={form.notes} onChange={e=>set('notes',e.target.value)}/></label>
      <div className="cost-actions"><button className="desk-button" value="calculate">{de?'Nachrechnen':'Calculate'}</button><button className="desk-button solid" value="save" disabled={!target}>{de?'Prüfung zur Akte speichern':'Save review to case'}</button><button type="button" className="desk-button" onClick={reset}>{de?'Neue Prüfung':'New review'}</button></div></fieldset></form>
      {error&&<p role="alert" className="storage-error">{error}</p>}{notice&&<p role="status" className="storage-notice">{notice}</p>}
      {result&&<Result result={result} form={form} lang={lang}/>}
      {saved&&<div className="cost-actions"><a className="desk-button" href={`${API_BASE}/api/cost-reviews/${saved.id}/report.pdf?lang=${lang}&version=${saved.version}`} target="_blank" rel="noreferrer">{de?'Prüfbericht als PDF':'Review report as PDF'} · v{saved.version}</a>{onDraft&&<button className="desk-button" onClick={letter}>{de?'Klärungsanschreiben entwerfen':'Draft clarification letter'}</button>}</div>}
      {versions.length>0&&<details><summary>{de?'Gespeicherte Fassungen':'Saved versions'} ({versions.length})</summary>{versions.map(row=><div className="cost-version" key={row.version}>v{row.version} · {dateLabel(row.saved_at,lang,true)} · {row.result.payable} {row.invoice.currency}<a href={`${API_BASE}/api/cost-reviews/${editing.id}/report.pdf?lang=${lang}&version=${row.version}`} target="_blank" rel="noreferrer">PDF</a></div>)}</details>}
    </section>
    <section className="desk-panel"><div className="desk-panel-heading"><h2>{de?'Gespeicherte Kostenprüfungen':'Saved cost reviews'}</h2><button className="desk-link" disabled={busy} onClick={()=>reload()}>{de?'Aktualisieren':'Refresh'}</button></div>
      {loading&&<p role="status">{de?'Prüfungen werden geladen …':'Loading reviews …'}</p>}{loadError&&<p role="alert" className="storage-error">{de?'Prüfungen nicht erreichbar. Erneut aktualisieren.':'Reviews unavailable. Refresh to retry.'}</p>}
      <div className="cost-register">{items.filter(item=>matches(query,item.invoice.title,item.invoice.issuer,item.invoice.invoice_number,item.case_reference,item.case_title)).map(item=><article key={item.id}><div><strong>{item.invoice.title}</strong><small>{item.case_reference} · {item.invoice.issuer} · v{item.version}</small><span>{item.result.has_difference?(de?'Abweichung':'Difference'):(de?'Rechnerisch stimmig':'Arithmetic matches')}: {item.result.difference} {item.invoice.currency}</span></div><div className="cost-actions"><button className="desk-button" disabled={busy} onClick={()=>loadItem(item)}>{de?'Prüfung öffnen':'Open review'}</button>{open&&<button className="desk-link" disabled={busy} onClick={()=>open(item.case_id,'costs')}>{de?'Akte öffnen':'Open case'}</button>}</div></article>)}{!loading&&!loadError&&!items.length&&<p>{de?'Noch keine Kostenprüfung gespeichert.':'No cost reviews saved yet.'}</p>}</div>
    </section>
  </div>;
}
