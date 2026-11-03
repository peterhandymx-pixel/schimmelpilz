import { useEffect, useState } from "react";
import { request } from "./useCaseStorage.js";
import { authRequest } from "./useAuth.js";
import { profileFields } from "./AuthForm.jsx";
import "./account-settings.css";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const organisationKeys = { business: ["legal_form", "representative", "industry", "register_court", "register_number", "vat_id"], law_firm: ["legal_form", "responsible_lawyer", "bar_association", "admission_country", "practice_areas", "register_court", "register_number", "vat_id"] };

const copy = {
  de: {
    edit: "Profil bearbeiten", save: "Speichern", cancel: "Abbrechen", saved: "Gespeichert.", failed: "Speichern fehlgeschlagen. Eingaben prüfen.",
    name: "Name *", organisation: "Unternehmen / Kanzlei *", street: "Straße und Hausnummer *", postal: "Postleitzahl *", city: "Ort *", country: "Land *", phone: "Telefon",
    unverified: "Ihre E-Mail-Adresse ist noch nicht bestätigt.", sendVerification: "Bestätigungslink senden", verificationSent: "Link gesendet. Bitte Postfach prüfen.", verified: "E-Mail bestätigt",
    emailTitle: "E-Mail-Adresse ändern", newEmail: "Neue E-Mail *", currentPassword: "Aktuelles Passwort *", changeEmail: "E-Mail ändern", emailTaken: "Diese E-Mail ist bereits registriert.",
    passwordTitle: "Passwort ändern", newPassword: "Neues Passwort *", repeat: "Neues Passwort wiederholen *", changePassword: "Passwort ändern", mismatch: "Die neuen Passwörter stimmen nicht überein.",
    passwordChanged: "Passwort geändert. Andere Geräte wurden abgemeldet.", wrongPassword: "Das Passwort ist nicht korrekt.", passwordHint: "Mindestens 12 Zeichen.",
    mfaTitle: "Zwei-Faktor-Anmeldung", mfaOn: "Aktiv. Bei der Anmeldung ist zusätzlich ein Code aus Ihrer Authenticator-App nötig.", mfaOff: "Nicht aktiv. Schützen Sie Ihr Konto zusätzlich mit einer Authenticator-App (z. B. Google Authenticator, Microsoft Authenticator, 1Password).",
    mfaAdmin: "Administratoren müssen die Zwei-Faktor-Anmeldung aktivieren, bevor Verwaltungsfunktionen verfügbar sind.",
    mfaStart: "Einrichtung starten", mfaQr: "Mit der Authenticator-App scannen – oder den Schlüssel darunter eintippen.", mfaQrAlt: "QR-Code für die Authenticator-App", mfaKey: "Schlüssel für Ihre App", mfaOpen: "In Authenticator-App öffnen", mfaCode: "6-stelliger Code aus der App *", mfaEnable: "Aktivieren",
    mfaCodes: "Wiederherstellungscodes – jetzt sicher aufbewahren. Jeder Code funktioniert einmal, falls Ihr Telefon fehlt. Sie werden nicht erneut angezeigt.", mfaCodesDone: "Codes gesichert",
    mfaDisable: "Zwei-Faktor-Anmeldung deaktivieren", mfaDisableCode: "Code oder Wiederherstellungscode *", mfaInvalid: "Der Code ist ungültig oder wurde bereits verwendet.", mfaKeep: "Administratoren können die Zwei-Faktor-Anmeldung nicht deaktivieren.",
    deleteTitle: "Konto löschen", deleteText: "Löscht Ihr Konto endgültig: alle Akten, Dokumente, Entwürfe, Fristen, Adressen, Posteingang, Briefpapier und Teamzugänge. Das kann nicht rückgängig gemacht werden. Laden Sie benötigte Akten vorher als ZIP herunter.",
    deleteWord: "LÖSCHEN", deleteType: "Zur Bestätigung LÖSCHEN eingeben *", deleteCheck: "Ich verstehe, dass alle Daten endgültig gelöscht werden.", deleteButton: "Konto endgültig löschen",
    lastAdmin: "Das letzte aktive Administratorkonto kann nicht gelöscht werden.", mfaNeeded: "Bitte den Code aus Ihrer Authenticator-App angeben.",
  },
  en: {
    edit: "Edit profile", save: "Save", cancel: "Cancel", saved: "Saved.", failed: "Could not save. Check the fields.",
    name: "Name *", organisation: "Business / law firm *", street: "Street and number *", postal: "Postal code *", city: "City *", country: "Country *", phone: "Phone",
    unverified: "Your email address is not confirmed yet.", sendVerification: "Send confirmation link", verificationSent: "Link sent. Please check your inbox.", verified: "Email confirmed",
    emailTitle: "Change email address", newEmail: "New email *", currentPassword: "Current password *", changeEmail: "Change email", emailTaken: "This email is already registered.",
    passwordTitle: "Change password", newPassword: "New password *", repeat: "Repeat new password *", changePassword: "Change password", mismatch: "The new passwords do not match.",
    passwordChanged: "Password changed. Other devices were signed out.", wrongPassword: "The password is incorrect.", passwordHint: "At least 12 characters.",
    mfaTitle: "Two-factor sign-in", mfaOn: "Active. Signing in also needs a code from your authenticator app.", mfaOff: "Not active. Protect your account with an authenticator app (e.g. Google Authenticator, Microsoft Authenticator, 1Password).",
    mfaAdmin: "Administrators must enable two-factor sign-in before administration functions are available.",
    mfaStart: "Start setup", mfaQr: "Scan with your authenticator app, or type the key below.", mfaQrAlt: "QR code for the authenticator app", mfaKey: "Key for your app", mfaOpen: "Open in authenticator app", mfaCode: "6-digit code from the app *", mfaEnable: "Enable",
    mfaCodes: "Recovery codes – store them safely now. Each works once if your phone is unavailable. They will not be shown again.", mfaCodesDone: "Codes saved",
    mfaDisable: "Disable two-factor sign-in", mfaDisableCode: "Code or recovery code *", mfaInvalid: "The code is invalid or was already used.", mfaKeep: "Administrators cannot disable two-factor sign-in.",
    deleteTitle: "Delete account", deleteText: "Permanently deletes your account: all cases, documents, drafts, deadlines, addresses, inbox, letter paper and team access. This cannot be undone. Download any cases you need as ZIP first.",
    deleteWord: "DELETE", deleteType: "Type DELETE to confirm *", deleteCheck: "I understand that all data will be permanently deleted.", deleteButton: "Permanently delete account",
    lastAdmin: "The last active administrator account cannot be deleted.", mfaNeeded: "Please enter the code from your authenticator app.",
  },
};

function useAction() {
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const run = async (work, onError) => {
    setBusy(true); setError(""); setNotice("");
    try { const message = await work(); if (message) setNotice(message); return true; }
    catch (failure) { setError(onError(failure)); return false; }
    finally { setBusy(false); }
  };
  return { busy, error, notice, run, setError };
}

function Messages({ action }) {
  return <>{action.error && <p className="storage-error" role="alert">{action.error}</p>}{action.notice && <p className="storage-notice" role="status">{action.notice}</p>}</>;
}

function ProfileForm({ lang, user, onUserUpdated, c }) {
  const [editing, setEditing] = useState(false);
  const action = useAction();
  if (!editing) return <button className="desk-button" onClick={() => setEditing(true)}>{c.edit}</button>;
  const submit = event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const profile = {};
    for (const key of Object.keys(profileFields.de)) { if (key in values) { profile[key] = values[key]; delete values[key]; } }
    profile.role = user.profile?.role || "";
    action.run(async () => { onUserUpdated(await request("/auth/profile", json("PUT", { ...values, profile: { ...user.profile, ...profile } }))); setEditing(false); return c.saved; }, () => c.failed);
  };
  return <form className="account-form" onSubmit={submit}><fieldset disabled={action.busy}><div className="intake-grid">
    <label className="span-two">{c.name}<input name="full_name" required minLength={3} maxLength={160} defaultValue={user.full_name} /></label>
    {user.audience !== "consumer" && <label className="span-two">{c.organisation}<input name="organisation" required maxLength={160} defaultValue={user.organisation} /></label>}
    <label className="span-two">{c.street}<input name="street" required minLength={3} maxLength={200} defaultValue={user.street} /></label>
    <label>{c.postal}<input name="postal_code" required minLength={2} maxLength={20} defaultValue={user.postal_code} /></label>
    <label>{c.city}<input name="city" required minLength={2} maxLength={100} defaultValue={user.city} /></label>
    <label>{c.country}<input name="country" required minLength={2} maxLength={100} defaultValue={user.country} /></label>
    <label>{c.phone}<input name="phone" maxLength={60} defaultValue={user.phone} /></label>
    {(organisationKeys[user.audience] || []).map(key => <label key={key} className={["responsible_lawyer", "practice_areas"].includes(key) ? "span-two" : ""}>{profileFields[lang][key]}<input name={key} maxLength={key === "practice_areas" ? 500 : 160} defaultValue={user.profile?.[key] || ""} /></label>)}
  </div></fieldset><Messages action={action} /><div className="account-actions"><button className="desk-button solid" disabled={action.busy}>{c.save}</button><button type="button" className="desk-button" disabled={action.busy} onClick={() => setEditing(false)}>{c.cancel}</button></div></form>;
}

function EmailForm({ user, onUserUpdated, c, mail }) {
  const action = useAction();
  const verify = useAction();
  const submit = event => {
    event.preventDefault();
    const form = event.currentTarget, values = Object.fromEntries(new FormData(form));
    action.run(async () => { onUserUpdated(await request("/auth/email", json("PUT", values))); form.reset(); return c.saved; }, failure => failure.status === 403 ? c.wrongPassword : failure.status === 409 ? c.emailTaken : c.failed);
  };
  return <section className="account-section"><h3>{c.emailTitle}</h3>
    {user.email_verified ? <p className="account-ok">✓ {c.verified}: {user.email}</p> : <p className="storage-notice">{c.unverified} {mail && <button className="desk-link" disabled={verify.busy} onClick={() => verify.run(async () => { await request("/auth/verify-email/send", { method: "POST" }); return c.verificationSent; }, () => c.failed)}>{c.sendVerification}</button>}</p>}
    <Messages action={verify} />
    <form className="account-form" onSubmit={submit}><fieldset disabled={action.busy}><div className="intake-grid">
      <label>{c.newEmail}<input name="email" type="email" required maxLength={254} autoComplete="email" /></label>
      <label>{c.currentPassword}<input name="password" type="password" required maxLength={128} autoComplete="current-password" /></label>
    </div></fieldset><Messages action={action} /><button className="desk-button" disabled={action.busy}>{c.changeEmail}</button></form>
  </section>;
}

function PasswordForm({ c }) {
  const action = useAction();
  const submit = event => {
    event.preventDefault();
    const form = event.currentTarget, values = Object.fromEntries(new FormData(form));
    if (values.new_password !== values.repeat) { action.setError(c.mismatch); return; }
    action.run(async () => { await request("/auth/password", json("PUT", { current_password: values.current_password, new_password: values.new_password })); form.reset(); return c.passwordChanged; }, failure => failure.status === 403 ? c.wrongPassword : c.failed);
  };
  return <section className="account-section"><h3>{c.passwordTitle}</h3><form className="account-form" onSubmit={submit}><fieldset disabled={action.busy}><div className="intake-grid">
    <label className="span-two">{c.currentPassword}<input name="current_password" type="password" required maxLength={128} autoComplete="current-password" /></label>
    <label>{c.newPassword}<input name="new_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
    <label>{c.repeat}<input name="repeat" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
    <p className="field-help span-two">{c.passwordHint}</p>
  </div></fieldset><Messages action={action} /><button className="desk-button" disabled={action.busy}>{c.changePassword}</button></form></section>;
}

function TwoFactor({ user, onUserUpdated, c }) {
  const action = useAction();
  const [setup, setSetup] = useState(null), [codes, setCodes] = useState(null);
  const refresh = async () => onUserUpdated(await authRequest("me"));
  const values = event => { event.preventDefault(); const form = event.currentTarget; return [form, Object.fromEntries(new FormData(form))]; };
  const mfaError = failure => failure.status === 403 ? c.wrongPassword : failure.status === 422 ? c.mfaInvalid : failure.detail === "administrators_must_keep_mfa" ? c.mfaKeep : c.failed;
  return <section className="account-section"><h3>{c.mfaTitle}</h3>
    <p>{user.mfa_enabled ? <span className="account-ok">✓ {c.mfaOn}</span> : c.mfaOff}</p>
    {user.is_admin && !user.mfa_enabled && <p className="storage-notice">{c.mfaAdmin}</p>}
    {codes && <div className="account-codes"><p><strong>{c.mfaCodes}</strong></p><ul>{codes.map(code => <li key={code}><code>{code}</code></li>)}</ul><button className="desk-button solid" onClick={() => { setCodes(null); refresh(); }}>{c.mfaCodesDone}</button></div>}
    {!user.mfa_enabled && !codes && !setup && <form className="account-form" onSubmit={event => { const [, data] = values(event); action.run(async () => { setSetup(await request("/auth/mfa/setup", json("POST", data))); }, mfaError); }}><fieldset disabled={action.busy}><label>{c.currentPassword}<input name="password" type="password" required maxLength={128} autoComplete="current-password" /></label></fieldset><button className="desk-button" disabled={action.busy}>{c.mfaStart}</button></form>}
    {setup && !codes && <form className="account-form" onSubmit={event => { const [, data] = values(event); action.run(async () => { const result = await request("/auth/mfa/enable", json("POST", data)); setCodes(result.recovery_codes); setSetup(null); }, mfaError); }}>
      {setup.qr_svg && <figure className="account-qr"><img src={setup.qr_svg} width="200" height="200" alt={c.mfaQrAlt} /><figcaption>{c.mfaQr}</figcaption></figure>}
      <p>{c.mfaKey}: <code className="account-secret">{setup.secret.match(/.{1,4}/g).join(" ")}</code> <a className="desk-link" href={setup.otpauth_uri}>{c.mfaOpen}</a></p>
      <fieldset disabled={action.busy}><label>{c.mfaCode}<input name="code" required inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={8} /></label></fieldset>
      <div className="account-actions"><button className="desk-button solid" disabled={action.busy}>{c.mfaEnable}</button><button type="button" className="desk-button" onClick={() => setSetup(null)}>{c.cancel}</button></div></form>}
    {user.mfa_enabled && !user.is_admin && <details><summary>{c.mfaDisable}</summary><form className="account-form" onSubmit={event => { const [, data] = values(event); action.run(async () => { await request("/auth/mfa/disable", json("POST", data)); await refresh(); }, mfaError); }}><fieldset disabled={action.busy}><div className="intake-grid">
      <label>{c.currentPassword}<input name="password" type="password" required maxLength={128} autoComplete="current-password" /></label>
      <label>{c.mfaDisableCode}<input name="code" required minLength={6} maxLength={20} autoComplete="one-time-code" /></label>
    </div></fieldset><button className="desk-button" disabled={action.busy}>{c.mfaDisable}</button></form></details>}
    <Messages action={action} />
  </section>;
}

function DeleteAccount({ user, onAccountDeleted, c }) {
  const action = useAction();
  const [agreed, setAgreed] = useState(false);
  const submit = event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    action.run(async () => { await request("/auth/account/delete", json("POST", { password: values.password, confirm: values.confirm.trim().toUpperCase(), ...(values.mfa_code ? { mfa_code: values.mfa_code } : {}) })); onAccountDeleted(); },
      failure => failure.status === 403 ? (failure.detail === "mfa_code_required" ? c.mfaNeeded : c.wrongPassword) : failure.detail === "last_administrator" ? c.lastAdmin : c.failed);
  };
  return <details className="account-danger"><summary>{c.deleteTitle}</summary><p>{c.deleteText}</p><form className="account-form" onSubmit={submit}><fieldset disabled={action.busy}><div className="intake-grid">
    <label>{c.currentPassword}<input name="password" type="password" required maxLength={128} autoComplete="current-password" /></label>
    <label>{c.deleteType}<input name="confirm" required autoComplete="off" pattern="(LÖSCHEN|löschen|DELETE|delete)" /></label>
    {user.mfa_enabled && <label>{c.mfaDisableCode}<input name="mfa_code" required minLength={6} maxLength={20} autoComplete="one-time-code" /></label>}
    <label className="control-check span-two"><input type="checkbox" checked={agreed} onChange={event => setAgreed(event.target.checked)} />{c.deleteCheck}</label>
  </div></fieldset><Messages action={action} /><button className="desk-button danger" disabled={action.busy || !agreed}>{c.deleteButton}</button></form></details>;
}

export function AccountSettings({ lang, user, onUserUpdated, onAccountDeleted }) {
  const c = copy[lang];
  const [mail, setMail] = useState(false);
  useEffect(() => { authRequest("capabilities").then(value => setMail(Boolean(value?.mail))).catch(() => setMail(false)); }, []);
  return <div className="account-settings">
    <ProfileForm lang={lang} user={user} onUserUpdated={onUserUpdated} c={c} />
    <EmailForm user={user} onUserUpdated={onUserUpdated} c={c} mail={mail} />
    <PasswordForm c={c} />
    <TwoFactor user={user} onUserUpdated={onUserUpdated} c={c} />
    <DeleteAccount user={user} onAccountDeleted={onAccountDeleted} c={c} />
  </div>;
}
