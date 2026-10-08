import { useState } from 'react';
import { IconPlus, IconEdit, IconUsers } from '@tabler/icons-react';
import { PartyList } from './DeskComponents.jsx';
import { matches } from './workbench.js';
import './contacts.css';

export const contactKinds = {
  de: {client:'Mandant',opponent:'Gegner',law_firm:'Anwaltskanzlei',court:'Gericht',authority:'Behörde',company:'Unternehmen',person:'Privatperson',other:'Sonstige'},
  en: {client:'Client',opponent:'Opponent',law_firm:'Law firm',court:'Court',authority:'Authority',company:'Company',person:'Individual',other:'Other'},
};
const roles = {de:{client:'Mandant / eigene Partei',opponent:'Gegenseite',counsel:'Rechtsvertretung',court:'Gericht',authority:'Behörde',other:'Weitere Beteiligte'},en:{client:'Client / own party',opponent:'Opposing party',counsel:'Legal representative',court:'Court',authority:'Authority',other:'Other party'}};
const blank = {name:'',kind:'person',attention:'',address:'',email:'',phone:'',note:'',case_links:[]};

export function ContactBook({ lang, contacts, cases, query = '', open, onSaved, caseId }) {
  const de = lang === 'de';
  const [editing, setEditing] = useState(null), [form, setForm] = useState(null), [busy,setBusy] = useState(false), [error,setError] = useState(''), [notice,setNotice] = useState(''), [kind,setKind] = useState('all');
  const visible = contacts.items.filter(item => (!caseId || item.case_links.some(link => link.case_id === caseId)) && (kind === 'all' || item.kind === kind) && matches(query,item.name,item.attention,item.address,item.email,item.phone,...item.case_links.map(link => `${link.reference} ${link.title}`)));
  const start = (item, seed) => {
    setEditing(item || null); setError(''); setNotice('');
    setForm(item ? {...item,case_links:item.case_links.map(({case_id,role})=>({case_id,role}))} : {...blank,...seed,case_links:seed?.case_links || (caseId ? [{case_id:caseId,role:'other'}] : [])});
  };
  const set = (field,value) => setForm(current => ({...current,[field]:value}));
  const save = async event => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError('');
    const payload = Object.fromEntries(Object.keys(blank).map(key => [key,form[key]]));
    try {
      await contacts.save(payload,editing); setForm(null); setNotice(de ? 'Kontakt gespeichert.' : 'Contact saved.'); onSaved?.();
    } catch (failure) {
      if (failure.status === 409) contacts.reload();
      setError(failure.status === 409 ? (de ? 'Der Kontakt wurde zwischenzeitlich geändert. Ihre Eingaben bleiben erhalten; öffnen Sie den aktuellen Kontakt erneut.' : 'This contact has changed. Your entries remain here; reopen the current contact.') : failure.status === 404 ? (de ? 'Kontakt oder zugeordnete Akte ist nicht verfügbar. Zuordnung prüfen.' : 'Contact or linked case unavailable. Check the links.') : (de ? 'Kontakt konnte nicht gespeichert werden. Angaben und Verbindung prüfen.' : 'Could not save contact. Check the fields and connection.'));
    } finally { setBusy(false); }
  };
  const legacy = caseId ? cases.filter(item=>item.id===caseId) : cases;
  return <>
    <section className="desk-panel contact-book">
      <div className="desk-panel-heading"><div><h2>{de ? 'Zentrales Adressbuch' : 'Central address book'}</h2><p>{caseId ? (de ? 'Kontakte dieser Akte' : 'Contacts linked to this case') : (de ? 'Kontakte verwalten und mehreren Akten zuordnen' : 'Manage contacts and link them to multiple cases')}</p></div><button className="desk-button solid" onClick={()=>start()} disabled={busy || Boolean(form)}><IconPlus size={17}/>{de ? 'Neuer Kontakt' : 'New contact'}</button></div>
      <div className="contact-filter"><label>{de ? 'Kontaktart' : 'Contact type'}<select value={kind} onChange={e=>setKind(e.target.value)}><option value="all">{de ? 'Alle Kontaktarten' : 'All contact types'}</option>{Object.entries(contactKinds[lang]).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><span>{visible.length} {de ? 'Kontakte in dieser Auswahl' : 'contacts in this view'}</span></div>
      {contacts.loading && <p className="desk-footnote" role="status">{de ? 'Adressbuch wird geladen …' : 'Loading address book …'}</p>}
      {contacts.error && <p className="storage-error" role="alert">{de ? 'Adressbuch nicht erreichbar.' : 'Address book unavailable.'} <button className="desk-link" onClick={()=>contacts.reload()}>{de ? 'Erneut versuchen' : 'Retry'}</button></p>}
      {notice && <p className="contact-notice" role="status">{notice}</p>}
      {form && <form className="contact-editor" onSubmit={save}>
        <h3>{editing ? (de ? 'Kontakt bearbeiten' : 'Edit contact') : (de ? 'Kontakt anlegen' : 'Create contact')}</h3>
        <fieldset disabled={busy}><div className="intake-grid">
          <label>{de ? 'Name / Organisation *' : 'Name / organisation *'}<input autoFocus required maxLength={160} value={form.name} onChange={e=>set('name',e.target.value)}/></label>
          <label>{de ? 'Kontaktart' : 'Contact type'}<select value={form.kind} onChange={e=>set('kind',e.target.value)}>{Object.entries(contactKinds[lang]).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <label className="span-two">{de ? 'Ansprechpartner / Adresszusatz' : 'Attention / address supplement'}<input maxLength={160} value={form.attention} onChange={e=>set('attention',e.target.value)}/></label>
          <label className="span-two">{de ? 'Postanschrift' : 'Postal address'}<textarea rows={3} maxLength={500} value={form.address} onChange={e=>set('address',e.target.value)} placeholder={de ? 'Straße, Hausnummer\nPostleitzahl, Ort\nLand' : 'Street, number\nPostal code, city\nCountry'}/></label>
          <label>E-Mail<input type="email" maxLength={254} value={form.email} onChange={e=>set('email',e.target.value)}/></label>
          <label>{de ? 'Telefon' : 'Phone'}<input type="tel" maxLength={80} value={form.phone} onChange={e=>set('phone',e.target.value)}/></label>
          <label className="span-two">{de ? 'Interner Vermerk' : 'Internal note'}<textarea rows={2} maxLength={2000} value={form.note} onChange={e=>set('note',e.target.value)}/></label>
        </div><h4>{de ? 'Aktenzuordnung & Rolle' : 'Linked cases & role'}</h4><p>{de ? 'Ein Kontakt kann in jeder Akte eine andere Rolle haben.' : 'A contact can have a different role in each case.'}</p>
        <div className="contact-case-options">{cases.map(item=>{
          const link = form.case_links.find(value=>value.case_id===item.id);
          return <div key={item.id} className="contact-case-option"><label><input type="checkbox" checked={Boolean(link)} onChange={e=>set('case_links',e.target.checked ? [...form.case_links,{case_id:item.id,role:'other'}] : form.case_links.filter(value=>value.case_id!==item.id))}/><span><strong>{item.reference}</strong>{item.title}</span></label>{link && <select aria-label={`${de ? 'Rolle in' : 'Role in'} ${item.reference}`} value={link.role} onChange={e=>set('case_links',form.case_links.map(value=>value.case_id===item.id ? {...value,role:e.target.value} : value))}>{Object.entries(roles[lang]).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>}</div>;
        })}{!cases.length && <p>{de ? 'Noch keine Akte vorhanden. Der Kontakt kann trotzdem gespeichert werden.' : 'No cases yet. You can still save the contact.'}</p>}</div>
        </fieldset>{error && <p className="storage-error" role="alert">{error}</p>}<div className="contact-actions"><button type="button" className="desk-button" disabled={busy} onClick={()=>setForm(null)}>{de ? 'Abbrechen' : 'Cancel'}</button><button className="desk-button solid" type="submit" disabled={busy}>{busy ? '…' : de ? 'Kontakt speichern' : 'Save contact'}</button></div>
      </form>}
      {visible.length ? <div className="desk-table-scroll"><table className="desk-table"><thead><tr><th>{de ? 'Name / Art' : 'Name / type'}</th><th>{de ? 'Anschrift & Kontakt' : 'Address & contact'}</th><th>{de ? 'Akten / Rollen' : 'Cases / roles'}</th><th>{de ? 'Aktion' : 'Action'}</th></tr></thead><tbody>{visible.map(item=><tr key={item.id}><td><strong>{item.name}</strong><small>{contactKinds[lang][item.kind]}</small>{item.attention && <small>{item.attention}</small>}</td><td><span className="desk-address">{item.address || '—'}</span><small>{item.email}</small><small>{item.phone}</small></td><td><div className="contact-links">{item.case_links.map(link=><div key={link.case_id}><button className="desk-link" onClick={()=>open(link.case_id,'parties')}>{link.reference}</button><small>{roles[lang][link.role]}</small></div>)}</div>{!item.case_links.length && '—'}</td><td><button className="desk-link" onClick={()=>start(item)} disabled={busy || Boolean(form)}><IconEdit size={15}/>{de ? 'Bearbeiten' : 'Edit'}</button></td></tr>)}</tbody></table></div> : !contacts.loading && !contacts.error && <div className="desk-empty-state"><IconUsers size={30}/><p>{de ? 'Keine gespeicherten Kontakte in dieser Auswahl.' : 'No saved contacts in this view.'}</p></div>}
      <p className="desk-footnote">{de ? 'Aktenstammdaten bleiben separat. Bestehende Schriftsätze behalten ihre gespeicherte Anschrift.' : 'Case particulars remain separate. Existing drafts retain their saved address.'}</p>
    </section>
    <section className="desk-panel contact-legacy"><PartyList cases={legacy} lang={lang} query={query} open={open} onImport={form ? undefined : row=>start(null,{name:row.name,kind:row.role,address:row.address,email:row.email,case_links:row.cases.map(item=>({case_id:item.id,role:row.role}))})}/></section>
  </>;
}

export function recipientBlock(contact) {
  return [contact.name,contact.attention,contact.address].filter(Boolean).join('\n');
}

export function ContactRecipient({ lang, contacts, caseId, onChoose }) {
  const de = lang === 'de';
  const [error,setError] = useState('');
  const linked = contacts.items.filter(item=>item.case_links.some(link=>link.case_id===caseId));
  const others = contacts.items.filter(item=>!linked.some(link=>link.id===item.id));
  return <div className="contact-recipient"><label>{de ? 'Empfänger aus dem Adressbuch' : 'Recipient from address book'}<select value="" disabled={contacts.loading || contacts.error || !contacts.items.length} onChange={e=>{
    const contact = contacts.items.find(item=>item.id===e.target.value); if (!contact) return;
    const block = recipientBlock(contact);
    if (block.length > 500) { setError(de ? 'Der Adressblock überschreitet 500 Zeichen. Anschrift im Adressbuch kürzen oder manuell eintragen.' : 'Address block exceeds 500 characters. Shorten it in the address book or enter it manually.'); return; }
    setError(''); onChoose(block);
  }}><option value="">{contacts.loading ? (de ? 'Lädt …' : 'Loading …') : contacts.error ? (de ? 'Adressbuch nicht erreichbar' : 'Address book unavailable') : !contacts.items.length ? (de ? 'Noch keine Kontakte angelegt' : 'No contacts yet') : (de ? 'Kontakt auswählen …' : 'Choose a contact …')}</option>{[[de ? 'Kontakte dieser Akte' : 'Contacts in this case',linked],[de ? 'Weitere Kontakte' : 'Other contacts',others]].map(([label,items])=>items.length>0 && <optgroup key={label} label={label}>{items.map(item=><option key={item.id} value={item.id}>{item.name} · {contactKinds[lang][item.kind]}</option>)}</optgroup>)}</select></label>{contacts.error && <button type="button" className="desk-link" onClick={()=>contacts.reload()}>{de ? 'Adressbuch erneut laden' : 'Reload address book'}</button>}{error && <p role="alert" className="storage-error">{error}</p>}<p className="field-help">{de ? 'Übernimmt Name und Postanschrift. Vorlagen passen sich automatisch an; die Anschrift in bereits bearbeitetem Text bitte ebenfalls aktualisieren.' : 'Copies name and postal address. Templates update automatically; also update the address in text you have already edited.'}</p></div>;
}
