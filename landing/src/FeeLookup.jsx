import { useState } from 'react';
import { request } from './useCaseStorage.js';

export function FeeLookup({ lang, enabled, onAdd }) {
  const de=lang==='de';
  const [statute,setStatute]=useState('rvg'),[value,setValue]=useState(''),[confirmed,setConfirmed]=useState(false),[note,setNote]=useState(''),[result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const invalidate=()=>{setResult(null);setError('');};
  const calculate=async event=>{
    event.preventDefault();setBusy(true);setError('');
    try{setResult(await request('/fee-tables/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({statute,version:'2025-bgbl-109',value:value.trim().replace(',','.'),applicability_confirmed:confirmed,applicability_note:note})}));}
    catch{setError(de?'Bitte Wert (0–500.000 EUR, ohne Tausendertrennzeichen), Prüfvermerk und bestätigte Anwendbarkeit prüfen.':'Check value (up to EUR 500,000, no thousands separators), review note and confirmed applicability.');}
    finally{setBusy(false);}
  };
  return <details className="cost-fee-lookup"><summary>{de?'Gebührentabelle RVG / GKG / FamGKG':'RVG / GKG / FamGKG fee table'}</summary>
    <p>{de?'Einfache Wertgebühr (1,0) nach den Tabellen aus BGBl. 2025 I Nr. 109. Nur EUR / deutsche Rechtsordnung. Die richtige Fassung, der Wert und der Gebührentatbestand müssen für den Fall geprüft werden.':'Basic value fee (1.0) from tables published in BGBl. 2025 I No. 109. EUR / German law only. Review applicable version, value and fee event for the case.'}</p>
    <p className="field-help">{de?'Nicht abgedeckt: ältere Fassungen, Werte über 500.000 EUR, PKH-Tabelle (§ 49 RVG), Betragsrahmen- / Festgebühren, Inkasso-Sonderregel, automatische Anrechnung oder Gebührenanspruch. Ein Rechnungsdatum genügt nicht zur Fassungswahl.':'Not covered: older versions, values over EUR 500,000, legal-aid table (§ 49 RVG), fixed/range fees, special collection rule, automatic credits or fee entitlement. Invoice date alone does not select the applicable version.'}</p>
    {!enabled&&<p className="storage-notice">{de?'Zuerst eine deutsche Akte und EUR wählen.':'First select a German-law case and EUR.'}</p>}
    <form onSubmit={calculate}><fieldset disabled={busy||!enabled}><div className="cost-form-grid"><label>{de?'Tabelle':'Table'}<select value={statute} onChange={e=>{setStatute(e.target.value);setConfirmed(false);invalidate();}}>{['rvg','gkg','famgkg'].map(id=><option key={id} value={id}>{id.toUpperCase()} · 2025</option>)}</select></label><label>{de?'Gegenstands- / Streit- / Verfahrenswert EUR *':'Subject / dispute / procedure value EUR *'}<input required inputMode="decimal" value={value} onChange={e=>{setValue(e.target.value);invalidate();}}/></label></div>
    <label>{de?'Vermerk zur geltenden Fassung / Übergangsregel *':'Applicable version / transition review note *'}<textarea required minLength={10} maxLength={1000} rows={2} value={note} onChange={e=>{setNote(e.target.value);invalidate();}}/></label>
    <label className="desk-checkbox"><input type="checkbox" required checked={confirmed} onChange={e=>{setConfirmed(e.target.checked);invalidate();}}/>{de?'Ich habe die Anwendbarkeit der ausgewählten Tabelle einschließlich Übergangsrecht für diese Akte geprüft. Eigener Prüfvermerk, keine unabhängige Freigabe.':'I reviewed the selected table and transition rules for this case. My own declaration, not independent approval.'}</label>
    <button className="desk-button" disabled={!confirmed}>{de?'1,0-Wertgebühr berechnen':'Calculate 1.0 value fee'}</button></fieldset></form>
    {error&&<p role="alert" className="storage-error">{error}</p>}
    {result&&<div className="cost-result"><h3>{result.statute.toUpperCase()} · 1,0: {result.base_fee} EUR</h3><p>{de?'Wertstufe bis':'Value bracket up to'} {result.bracket} EUR · {result.version} · {de?'Quellen geprüft am':'Sources checked on'} {result.source_checked_on}</p><p>{result.source.citation}</p><p><a href={result.source.table} target="_blank" rel="noreferrer">{de?'Originaltabelle':'Original table'}</a> · <a href={result.source.transition} target="_blank" rel="noreferrer">{de?'Übergangsregel':'Transition rule'}</a></p><button type="button" className="desk-button" disabled={!enabled} onClick={()=>onAdd(result,{statute,version:'2025-bgbl-109',value:value.trim().replace(',','.'),applicability_confirmed:true,applicability_note:note})}>{de?'Als Rechnungsposition übernehmen':'Use as invoice item'}</button><p className="field-help">{de?'Menge / Satz, VV- / KV-Nummer, Anrechnung und Steuer anschließend ausdrücklich ergänzen. Mindestgebühren, Sonderregeln und Berechtigung bleiben gesondert zu prüfen.':'Explicitly complete multiplier, fee code, credits and tax afterwards. Review minimum fees, special rules and entitlement separately.'}</p></div>}
  </details>;
}
