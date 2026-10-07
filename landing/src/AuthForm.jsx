import { useState } from "react";
import { authRequest } from "./useAuth.js";
import { LetterheadSetup } from './LetterheadSetup.jsx';

export const profileFields = {
  de: {legal_form:'Rechtsform', role:'Ihre Funktion *', representative:'Vertretungsberechtigte Person', register_court:'Registergericht', register_number:'Registernummer', vat_id:'Umsatzsteuer-ID', industry:'Branche / Tätigkeit', responsible_lawyer:'Verantwortliche Rechtsanwältin / verantwortlicher Rechtsanwalt', bar_association:'Zuständige Rechtsanwaltskammer', admission_country:'Zulassungsland', practice_areas:'Rechtsgebiete / Schwerpunkte'},
  en: {legal_form:'Legal form', role:'Your role *', representative:'Authorised representative', register_court:'Registry court', register_number:'Registration number', vat_id:'VAT ID', industry:'Industry / activity', responsible_lawyer:'Responsible lawyer', bar_association:'Bar association', admission_country:'Country of admission', practice_areas:'Practice areas'},
};

export function profileValue(lang, key, value) {
  const roles = lang === 'de'
    ? {management:'Geschäftsführung / Inhaber', legal:'Rechtsabteilung', employee:'Mitarbeiter', lawyer:'Rechtsanwalt / Rechtsanwältin', staff:'Rechtsanwaltsfachangestellte / Assistenz', research:'Juristische Recherche'}
    : {management:'Management / owner', legal:'Legal department', employee:'Employee', lawyer:'Lawyer', staff:'Legal assistant / staff', research:'Legal research'};
  return key === 'role' ? (roles[value] || value) : value;
}

export const authCopy = {
  de: {
    login: "Anmelden", register: "Registrieren", loginIntro: "Melden Sie sich an, um Ihre Akten, Unterlagen und Entwürfe zu öffnen.", registerIntro: "Richten Sie Ihr Konto ein. Die Kontaktdaten stehen anschließend für Ihre eigene Fallanlage bereit.",
    email: "E-Mail *", password: "Passwort *", confirm: "Passwort wiederholen *", passwordHint: "Mindestens 12 Zeichen. Verwenden Sie ein eigenes Passwort für dieses Konto.",
    audience: "Kontotyp *", consumer: "Verbraucher", business: "Unternehmen", law_firm: "Anwaltskanzlei", name: "Vor- und Nachname *", organisation: "Unternehmen / Kanzlei *", street: "Straße und Hausnummer *", postal: "Postleitzahl *", city: "Ort *", country: "Land *", phone: "Telefon (optional)",
    account: "Konto erstellen", otherLogin: "Schon registriert? Anmelden", otherRegister: "Noch kein Konto? Registrieren", mismatch: "Die Passwörter stimmen nicht überein.", duplicate: "Diese E-Mail ist bereits registriert. Bitte melden Sie sich an.", invalid: "Bitte prüfen Sie die Pflichtfelder und verwenden Sie mindestens 12 Zeichen für das Passwort.", wrong: "E-Mail oder Passwort ist nicht korrekt.", limited: "Zu viele Anmeldeversuche. Bitte in 15 Minuten erneut versuchen.", failed: "Der Server ist nicht erreichbar. Ihre Angaben bleiben im Formular.",
    note: "Ihre Kontaktdaten und Akten werden auf diesem Server gespeichert. Dieses Konto versendet keine Schriftsätze automatisch.",
  },
  en: {
    login: "Sign in", register: "Register", loginIntro: "Sign in to open your case files, documents and drafts.", registerIntro: "Set up your account. Your contact details will be available when opening your own cases.",
    email: "Email *", password: "Password *", confirm: "Confirm password *", passwordHint: "At least 12 characters. Use a password dedicated to this account.",
    audience: "Account type *", consumer: "Consumer", business: "Business", law_firm: "Law firm", name: "Full name *", organisation: "Business / law firm *", street: "Street and number *", postal: "Postal code *", city: "City *", country: "Country *", phone: "Phone (optional)",
    account: "Create account", otherLogin: "Already registered? Sign in", otherRegister: "No account yet? Register", mismatch: "The passwords do not match.", duplicate: "This email is already registered. Please sign in.", invalid: "Check required fields and use at least 12 characters for the password.", wrong: "Email or password is incorrect.", limited: "Too many sign-in attempts. Please try again in 15 minutes.", failed: "The server is unavailable. Your entries remain in the form.",
    note: "Your contact details and files are stored on this server. The account does not send documents automatically.",
  },
};

export function AuthForm({ lang, mode, setMode, onAuthenticated, initialAudience = 'consumer' }) {
  const c = authCopy[lang];
  const [audience, setAudience] = useState(initialAudience);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [createdUser, setCreatedUser] = useState(null);
  const register = mode === "register";
  const submit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    setError("");
    if (register && values.password !== values.confirm) { setError(c.mismatch); return; }
    delete values.confirm;
    if (register) {
      values.profile = {};
      for (const key of Object.keys(profileFields[lang])) { if (key in values) { values.profile[key] = values[key]; delete values[key]; } }
    }
    setBusy(true);
    try { const user = await authRequest(mode, values); if (register && audience !== 'consumer') setCreatedUser(user); else { form.reset(); onAuthenticated(user); } }
    catch (error) { setError(error.status === 409 ? c.duplicate : error.status === 422 ? c.invalid : error.status === 429 ? c.limited : error.status === 401 ? c.wrong : c.failed); }
    finally { setBusy(false); }
  };
  if (createdUser) return <LetterheadSetup lang={lang} onboarding onReady={onAuthenticated} />;
  return <form className="auth-form" onSubmit={submit}>
    <p className="dialog-intro">{register ? c.registerIntro : c.loginIntro}</p>
    {register && <p className="field-help">{lang === "de" ? "Kostenlose Pilotphase: keine Kreditkarte, keine automatische Abbuchung und kein kostenpflichtiges Abo. Die angekündigten Monatstarife mit 7 Testtagen sind für den Produktstart vorgesehen." : "Free pilot: no credit card, automatic charge or paid subscription. The announced monthly plans with a 7-day trial are planned for launch."}</p>}
    <fieldset disabled={busy}><div className="intake-grid">
      {register && <><div className="registration-audiences span-two" role="group" aria-label={c.audience}>{['consumer','business','law_firm'].map(value => <label key={value} className={audience === value ? 'selected' : ''}><input type="radio" name="audience" value={value} checked={audience === value} onChange={() => setAudience(value)} /><strong>{c[value]}</strong><small>{lang === 'de' ? {consumer:'Eigene Anliegen und Unterlagen',business:'Verträge, Forderungen und Geschäftspost',law_firm:'Mandatsakten, Recherche und Schriftsätze'}[value] : {consumer:'Personal matters and documents',business:'Contracts, receivables and correspondence',law_firm:'Client files, research and drafting'}[value]}</small></label>)}</div><h3 className="registration-section span-two">{lang === 'de' ? (audience === 'consumer' ? 'Ihre persönlichen Angaben' : audience === 'business' ? 'Ihr Unternehmen' : 'Ihre Kanzlei') : (audience === 'consumer' ? 'Your details' : audience === 'business' ? 'Your business' : 'Your law firm')}</h3>{audience !== 'consumer' && <><label className="span-two">{lang === 'de' ? (audience === 'business' ? 'Vollständiger Firmenname *' : 'Vollständiger Kanzleiname *') : (audience === 'business' ? 'Full company name *' : 'Full law firm name *')}<input name="organisation" required maxLength={160} autoComplete="organization" /></label><label>{profileFields[lang].legal_form}<input name="legal_form" maxLength={80} placeholder={audience === 'business' ? 'GmbH, AG, Einzelunternehmen …' : 'Einzelkanzlei, PartG mbB …'} /></label><label>{profileFields[lang].role}<select key={audience} name="role" aria-label={profileFields[lang].role} required defaultValue=""><option value="" disabled>{lang === 'de' ? 'Bitte auswählen' : 'Please select'}</option>{(audience === 'business' ? [['management', 'Geschäftsführung / Inhaber', 'Management / owner'], ['legal', 'Rechtsabteilung', 'Legal department'], ['employee', 'Mitarbeiter', 'Employee']] : [['lawyer', 'Rechtsanwalt / Rechtsanwältin', 'Lawyer'], ['staff', 'Rechtsanwaltsfachangestellte / Assistenz', 'Legal assistant / staff'], ['research', 'Juristische Recherche', 'Legal research']]).map(([id,de,en]) => <option key={id} value={id}>{lang === 'de' ? de : en}</option>)}</select></label>{(audience === 'business' ? ['representative','industry','register_court','register_number','vat_id'] : ['responsible_lawyer','bar_association','admission_country','practice_areas','register_court','register_number','vat_id']).map(key => <label key={key} className={['responsible_lawyer','practice_areas'].includes(key) ? 'span-two' : ''}>{profileFields[lang][key]}<input name={key} maxLength={key === 'practice_areas' ? 500 : ['register_number','vat_id'].includes(key) ? 80 : key === 'admission_country' ? 100 : 160} /></label>)}<p className="field-help span-two">{lang === 'de' ? 'Diese ergänzenden Organisationsangaben sind optional. Berufsangaben werden gespeichert, aber nicht als Zulassung geprüft. Der Zugang gehört zunächst nur der registrierten Person.' : 'Additional organisation details are optional. Professional details are stored but do not verify admission. Access initially belongs only to the registered person.'}</p></>}<h3 className="registration-section span-two">{lang === 'de' ? (audience === 'consumer' ? 'Kontakt und Zugang' : 'Kontaktperson und Geschäftsanschrift') : (audience === 'consumer' ? 'Contact and sign-in' : 'Contact person and business address')}</h3><label className="span-two">{audience === 'consumer' ? c.name : (lang === 'de' ? 'Vor- und Nachname der nutzenden Person *' : 'Full name of the person using the account *')}<input name="full_name" required minLength={3} maxLength={160} autoComplete="name" /></label></>}
      <label className="span-two">{c.email}<input name="email" required type="email" maxLength={254} autoComplete="username" /></label>
      <label className="span-two">{c.password}<input name="password" required type="password" minLength={register ? 12 : 1} maxLength={128} autoComplete={register ? "new-password" : "current-password"} /></label>
      {register && <><label className="span-two">{c.confirm}<input name="confirm" required type="password" minLength={12} maxLength={128} autoComplete="new-password" /></label><p className="field-help span-two">{c.passwordHint}</p><label className="span-two">{c.street}<input name="street" required minLength={3} maxLength={200} autoComplete="street-address" /></label><label>{c.postal}<input name="postal_code" required minLength={2} maxLength={20} autoComplete="postal-code" /></label><label>{c.city}<input name="city" required minLength={2} maxLength={100} autoComplete="address-level2" /></label><label>{c.country}<input name="country" required minLength={2} maxLength={100} autoComplete="country-name" /></label><label>{c.phone}<input name="phone" maxLength={60} autoComplete="tel" /></label></>}
    </div></fieldset>
    {error && <p className="storage-error" role="alert">{error}</p>}
    <button className="primary-button full-button" disabled={busy}>{busy ? "…" : register ? c.account : c.login}</button>
    <button className="text-link" disabled={busy} type="button" onClick={() => { setError(""); setMode(register ? "login" : "register"); }}>{register ? c.otherLogin : c.otherRegister}</button>
    {register && <p className="field-help">{c.note}{audience !== 'consumer' && (lang === 'de' ? ' Im nächsten Schritt können Sie Ihren Briefkopf als PDF, DOC oder DOCX hinterlegen.' : ' In the next step you can add your letterhead as PDF, DOC or DOCX.')}</p>}
  </form>;
}
