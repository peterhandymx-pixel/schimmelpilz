import { useState } from "react";
import { authRequest } from "./useAuth.js";

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

export function AuthForm({ lang, mode, setMode, onAuthenticated }) {
  const c = authCopy[lang];
  const [audience, setAudience] = useState("consumer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const register = mode === "register";
  const submit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    setError("");
    if (register && values.password !== values.confirm) { setError(c.mismatch); return; }
    delete values.confirm;
    setBusy(true);
    try { const user = await authRequest(mode, values); form.reset(); onAuthenticated(user); }
    catch (error) { setError(error.status === 409 ? c.duplicate : error.status === 422 ? c.invalid : error.status === 429 ? c.limited : error.status === 401 ? c.wrong : c.failed); }
    finally { setBusy(false); }
  };
  return <form className="auth-form" onSubmit={submit}>
    <p className="dialog-intro">{register ? c.registerIntro : c.loginIntro}</p>
    <fieldset disabled={busy}><div className="intake-grid">
      {register && <><label className="span-two">{c.audience}<select name="audience" value={audience} onChange={event => setAudience(event.target.value)}>{["consumer", "business", "law_firm"].map(value => <option key={value} value={value}>{c[value]}</option>)}</select></label><label className="span-two">{c.name}<input name="full_name" required minLength={3} maxLength={160} autoComplete="name" /></label>{audience !== "consumer" && <label className="span-two">{c.organisation}<input name="organisation" required maxLength={160} autoComplete="organization" /></label>}</>}
      <label className="span-two">{c.email}<input name="email" required type="email" maxLength={254} autoComplete="username" /></label>
      <label className="span-two">{c.password}<input name="password" required type="password" minLength={register ? 12 : 1} maxLength={128} autoComplete={register ? "new-password" : "current-password"} /></label>
      {register && <><label className="span-two">{c.confirm}<input name="confirm" required type="password" minLength={12} maxLength={128} autoComplete="new-password" /></label><p className="field-help span-two">{c.passwordHint}</p><label className="span-two">{c.street}<input name="street" required minLength={3} maxLength={200} autoComplete="street-address" /></label><label>{c.postal}<input name="postal_code" required minLength={2} maxLength={20} autoComplete="postal-code" /></label><label>{c.city}<input name="city" required minLength={2} maxLength={100} autoComplete="address-level2" /></label><label>{c.country}<input name="country" required minLength={2} maxLength={100} autoComplete="country-name" /></label><label>{c.phone}<input name="phone" maxLength={60} autoComplete="tel" /></label></>}
    </div></fieldset>
    {error && <p className="storage-error" role="alert">{error}</p>}
    <button className="primary-button full-button" disabled={busy}>{busy ? "…" : register ? c.account : c.login}</button>
    <button className="text-link" disabled={busy} type="button" onClick={() => { setError(""); setMode(register ? "login" : "register"); }}>{register ? c.otherLogin : c.otherRegister}</button>
    {register && <p className="field-help">{c.note}</p>}
  </form>;
}
