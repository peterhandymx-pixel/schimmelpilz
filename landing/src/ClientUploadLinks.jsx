import { useEffect, useState } from "react";
import { IconCloudUpload, IconCopy, IconMail, IconQrcode, IconBan } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";
import { dateLabel } from "./workbench.js";
import "./tools.css";

const STATE = { active: "aktiv", expired: "abgelaufen", revoked: "beendet", full: "ausgeschöpft" };

// Upload link for the client: created per case, shown once with copy / e-mail / QR; uploads arrive in the inbox.
export function ClientUploadLinks({ item }) {
  const d = item.details || {};
  const [links, setLinks] = useState([]), [created, setCreated] = useState(null), [qr, setQr] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false), [copied, setCopied] = useState(false);
  const [form, setForm] = useState({ days: 14, max_files: 20, message: "Bitte laden Sie hier die Unterlagen zu Ihrer Angelegenheit hoch (z. B. Verträge, Schreiben, Bescheide, Fotos)." });
  const load = () => request(`/cases/${item.id}/upload-links`).then(setLinks).catch(() => setError("Links konnten nicht geladen werden."));
  useEffect(() => { load(); }, [item.id]);
  const url = created ? `${window.location.origin}${API_BASE}${created.path}` : "";

  const create = async event => {
    event.preventDefault(); setBusy(true); setError(""); setQr(""); setCopied(false);
    try { setCreated(await request(`/cases/${item.id}/upload-links`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, days: Number(form.days), max_files: Number(form.max_files) }) })); await load(); }
    catch { setError("Link konnte nicht erstellt werden."); }
    finally { setBusy(false); }
  };
  const copy = async () => { try { await navigator.clipboard.writeText(url); setCopied(true); } catch { setError("Kopieren nicht möglich – Link bitte markieren und kopieren."); } };
  const showQr = async () => {
    try { const response = await fetch(`${API_BASE}/api/upload-links/qr`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Schimmelpilz-Request": "1" }, body: JSON.stringify({ text: url }) });
      setQr(URL.createObjectURL(await response.blob())); } catch { setError("QR-Code konnte nicht erstellt werden."); }
  };
  const revoke = async link => {
    if (!window.confirm("Diesen Link beenden? Der Mandant kann danach nichts mehr hochladen.")) return;
    try { await request(`/cases/${item.id}/upload-links/${link.id}`, { method: "DELETE" }); if (created?.id === link.id) setCreated(null); await load(); }
    catch { setError("Link konnte nicht beendet werden."); }
  };
  const mail = created ? `mailto:${encodeURIComponent(d.client_email || "")}?subject=${encodeURIComponent(`Ihre Unterlagen – unser Zeichen ${item.reference}`)}&body=${encodeURIComponent(
    `Guten Tag${d.client_name ? " " + d.client_name : ""},\n\nüber den folgenden Link können Sie uns Ihre Unterlagen sicher senden (ohne Anmeldung, auch mit dem Handy):\n\n${url}\n\nDer Link gilt bis ${dateLabel(created.expires_at, "de")}.\n\nMit freundlichen Grüßen`)}` : "";

  return <section className="desk-panel tool-panel">
    <div className="desk-panel-heading"><div><h2><IconCloudUpload size={18} /> Upload-Link für Mandanten</h2>
      <p>Der Mandant öffnet den Link ohne Anmeldung und sendet Dateien oder Handyfotos. Sie landen im Posteingang, diese Akte ist dort schon ausgewählt.</p></div></div>
    {error && <p className="storage-error" role="alert">{error}</p>}
    {created ? <div className="upload-created">
      <p><strong>Neuer Link</strong> · gültig bis {dateLabel(created.expires_at, "de")} · bis {created.max_files} Dateien. Den Link sehen Sie nur jetzt – bitte gleich weitergeben.</p>
      <input readOnly value={url} onFocus={event => event.target.select()} aria-label="Upload-Link" />
      <div className="cost-actions"><button className="desk-button solid" onClick={copy}><IconCopy size={16} />{copied ? "Kopiert" : "Link kopieren"}</button>
        <a className="desk-button" href={mail}><IconMail size={16} />Per E-Mail senden</a>
        <button className="desk-button" onClick={showQr}><IconQrcode size={16} />QR-Code</button>
        <button className="desk-link" onClick={() => { setCreated(null); setQr(""); }}>Fertig</button></div>
      {qr && <figure className="upload-qr"><img src={qr} alt="QR-Code zum Upload-Link" /><figcaption>Mit der Handykamera scannen – z. B. im Mandantengespräch.</figcaption></figure>}
    </div> : <form className="upload-form" onSubmit={create}><fieldset disabled={busy}>
      <div className="note-grid">
        <label>Gültig<select value={form.days} onChange={event => setForm({ ...form, days: event.target.value })}>{[3, 7, 14, 30, 60].map(days => <option key={days} value={days}>{days} Tage</option>)}</select></label>
        <label>Höchstens<select value={form.max_files} onChange={event => setForm({ ...form, max_files: event.target.value })}>{[5, 10, 20, 50].map(count => <option key={count} value={count}>{count} Dateien</option>)}</select></label>
      </div>
      <label>Nachricht an den Mandanten<textarea rows={2} maxLength={1000} value={form.message} onChange={event => setForm({ ...form, message: event.target.value })} /></label>
      <button className="desk-button solid">{busy ? "…" : "Upload-Link erstellen"}</button>
    </fieldset></form>}
    {links.length > 0 && <ul className="form-list">{links.map(link => <li key={link.id}><div><strong>Link vom {dateLabel(link.created_at, "de")} · <span className={`upload-state ${link.state}`}>{STATE[link.state]}</span></strong>
      <small>{link.uploaded} von {link.max_files} Dateien · gültig bis {dateLabel(link.expires_at, "de")}{link.message ? ` · „${link.message.slice(0, 60)}${link.message.length > 60 ? "…" : ""}“` : ""}</small></div>
      {link.state === "active" && <button className="desk-link desk-delete" onClick={() => revoke(link)}><IconBan size={15} />Beenden</button>}</li>)}</ul>}
  </section>;
}
