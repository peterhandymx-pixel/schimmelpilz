import { useEffect, useState } from "react";
import { dateLabel } from './workbench.js';
import { IconMailDown } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import "./account-settings.css";

const copy = {
  de: {
    title: "E-Mail-Postfach abrufen", intro: "Importiert Anhänge (PDF, DOC, DOCX, PNG, JPG, ZIP bis 10 MB) aus ungelesenen E-Mails Ihres IMAP-Postfachs in den Posteingang. E-Mails bleiben ungelesen und werden nicht verschoben oder gelöscht. Die Zuordnung zur Akte bleibt Ihre Entscheidung.",
    host: "IMAP-Server *", port: "Port", security: "Verschlüsselung", ssl: "SSL/TLS (993)", starttls: "STARTTLS (143)", username: "Benutzername *", password: "Passwort", passwordKeep: "Leer lassen, um das gespeicherte Passwort zu behalten", folder: "Ordner",
    save: "Einstellungen speichern", fetch: "Jetzt abrufen", remove: "Postfach entfernen", last: "Letzter Abruf", saved: "Gespeichert.", imported: count => `${count} Anhang/Anhänge importiert.`, none: "Keine neuen Anhänge gefunden.",
    errors: { mailbox_host_not_public: "Dieser Server ist nicht öffentlich erreichbar und wird aus Sicherheitsgründen nicht verwendet.", mailbox_host_not_found: "Server nicht gefunden.", mailbox_login_failed: "Anmeldung am Postfach fehlgeschlagen. Benutzername/Passwort prüfen.", mailbox_unreachable: "Postfach nicht erreichbar.", mailbox_folder_not_found: "Ordner nicht gefunden.", mailbox_password_required: "Bitte Passwort angeben.", mailbox_password_unreadable_enter_again: "Gespeichertes Passwort nicht mehr lesbar (z. B. nach Wiederherstellung). Bitte neu eingeben." },
    failed: "Aktion fehlgeschlagen.", hint: "Viele Anbieter verlangen ein App-Passwort statt Ihres normalen Passworts. Das Passwort wird verschlüsselt auf diesem Server gespeichert.",
  },
  en: {
    title: "Fetch email mailbox", intro: "Imports attachments (PDF, DOC, DOCX, PNG, JPG, ZIP up to 10 MB) from unread emails in your IMAP mailbox into the inbox. Emails stay unread and are never moved or deleted. Assigning them to a case stays your decision.",
    host: "IMAP server *", port: "Port", security: "Encryption", ssl: "SSL/TLS (993)", starttls: "STARTTLS (143)", username: "Username *", password: "Password", passwordKeep: "Leave empty to keep the saved password", folder: "Folder",
    save: "Save settings", fetch: "Fetch now", remove: "Remove mailbox", last: "Last fetch", saved: "Saved.", imported: count => `${count} attachment(s) imported.`, none: "No new attachments found.",
    errors: { mailbox_host_not_public: "This server is not publicly reachable and is refused for security reasons.", mailbox_host_not_found: "Server not found.", mailbox_login_failed: "Mailbox sign-in failed. Check username/password.", mailbox_unreachable: "Mailbox unreachable.", mailbox_folder_not_found: "Folder not found.", mailbox_password_required: "Please enter the password.", mailbox_password_unreadable_enter_again: "Saved password can no longer be read (e.g. after a restore). Please enter it again." },
    failed: "Action failed.", hint: "Many providers require an app password instead of your normal password. The password is stored encrypted on this server.",
  },
};

export function MailboxImport({ lang, onImported }) {
  const c = copy[lang];
  const [settings, setSettings] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [security, setSecurity] = useState("ssl");
  useEffect(() => { request("/inbox/mailbox").then(value => { setSettings(value); if (value.security) setSecurity(value.security); }).catch(() => setSettings({ configured: false, unavailable: true })); }, []);
  const run = async work => {
    setBusy(true); setError(""); setNotice("");
    try { await work(); } catch (failure) { setError(c.errors[failure.detail] || c.failed); } finally { setBusy(false); }
  };
  const save = event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    run(async () => { setSettings(await request("/inbox/mailbox", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ host: values.host.trim(), port: security === "ssl" ? 993 : 143, security, username: values.username, password: values.password || null, folder: values.folder || "INBOX" }) })); setNotice(c.saved); });
  };
  const fetchNow = () => run(async () => { const result = await request("/inbox/mailbox/fetch", { method: "POST" }); setNotice(result.imported.length ? c.imported(result.imported.length) : c.none); setSettings(await request("/inbox/mailbox")); onImported?.(); });
  const remove = () => run(async () => { await request("/inbox/mailbox", { method: "DELETE" }); setSettings({ configured: false }); });
  if (!settings || settings.unavailable) return null;
  return <details className="draft-send mailbox-import" open={settings.configured || undefined}><summary><IconMailDown size={16} /> {c.title}</summary><p className="field-help">{c.intro}</p>
    {settings.configured && <div className="account-actions"><button className="desk-button solid" disabled={busy} onClick={fetchNow}>{busy ? "…" : c.fetch}</button>{settings.last_fetch_at && <small>{c.last}: {dateLabel(settings.last_fetch_at, lang, true)} · {settings.last_result}</small>}</div>}
    <form className="account-form" onSubmit={save}><fieldset disabled={busy}><div className="intake-grid">
      <label>{c.host}<input name="host" required maxLength={253} pattern="[A-Za-z0-9.\-]+" placeholder="imap.example.com" defaultValue={settings.host || ""} /></label>
      <label>{c.security}<select value={security} onChange={event => setSecurity(event.target.value)}><option value="ssl">{c.ssl}</option><option value="starttls">{c.starttls}</option></select></label>
      <label>{c.username}<input name="username" required maxLength={254} autoComplete="off" defaultValue={settings.username || ""} /></label>
      <label>{c.password}<input name="password" type="password" maxLength={512} autoComplete="new-password" required={!settings.configured} placeholder={settings.configured ? c.passwordKeep : ""} /></label>
      <label>{c.folder}<input name="folder" maxLength={100} defaultValue={settings.folder || "INBOX"} /></label>
      <p className="field-help span-two">{c.hint}</p>
    </div></fieldset><div className="account-actions"><button className="desk-button" disabled={busy}>{c.save}</button>{settings.configured && <button type="button" className="desk-link desk-delete" disabled={busy} onClick={remove}>{c.remove}</button>}</div></form>
    {error && <p className="storage-error" role="alert">{error}</p>}{notice && <p className="storage-notice" role="status">{notice}</p>}
  </details>;
}
