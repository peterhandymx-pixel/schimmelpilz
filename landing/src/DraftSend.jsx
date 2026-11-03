import { useEffect, useState } from "react";
import { IconMail } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { authRequest } from "./useAuth.js";
import "./account-settings.css";

const copy = {
  de: {
    title: "Per E-Mail senden", intro: "Versendet die gespeicherte Fassung als Anhang über den E-Mail-Server dieser Installation. Antworten gehen an Ihre E-Mail-Adresse. Eine E-Mail ist keine förmliche Einreichung bei Gericht (beA/EGVP) und wahrt keine Frist, die eine bestimmte Form verlangt.",
    to: "Empfänger-E-Mail *", subject: "Betreff *", message: "Begleittext", attachment: "Anhang", pdf: "PDF mit Briefkopf", docx: "Word (bearbeitbar)",
    unsaved: "Speichern Sie Ihre Änderungen zuerst. Versendet wird nur eine gespeicherte Fassung.", notApproved: "Diese Fassung ist noch nicht freigegeben (eigene Prüfung). Sie können trotzdem senden; der Status wird im Verlauf festgehalten.",
    confirm: "Ich habe Empfänger, Inhalt und Anhang geprüft und möchte diese Fassung jetzt versenden.", send: "Jetzt senden", sent: "Gesendet. Versand ist im Prüfverlauf und Aktenverlauf vermerkt.",
    unavailable: "E-Mail-Versand ist nicht eingerichtet. Der Betreiber muss SMTP in der Konfiguration hinterlegen.", failed: "Versand fehlgeschlagen. Bitte Eingaben prüfen oder später erneut versuchen.", conflict: "Der Entwurf wurde inzwischen geändert. Bitte neu laden.", limit: "Zu viele Sendungen in der letzten Stunde.",
  },
  en: {
    title: "Send by email", intro: "Sends the saved version as an attachment through this installation's mail server. Replies go to your email address. Email is not formal court filing (beA/EGVP) and does not meet deadlines that require a specific form.",
    to: "Recipient email *", subject: "Subject *", message: "Cover message", attachment: "Attachment", pdf: "PDF with letterhead", docx: "Word (editable)",
    unsaved: "Save your changes first. Only a saved version is sent.", notApproved: "This version is not approved yet (own review). You can still send it; the status is recorded in the history.",
    confirm: "I have checked recipient, content and attachment and want to send this version now.", send: "Send now", sent: "Sent. Delivery is recorded in the review and case history.",
    unavailable: "Email sending is not set up. The operator needs to configure SMTP.", failed: "Sending failed. Check the fields or try again later.", conflict: "The draft changed meanwhile. Please reload.", limit: "Too many messages in the last hour.",
  },
};

export function DraftSend({ lang, caseItem, draft, dirty, onSent }) {
  const c = copy[lang];
  const [available, setAvailable] = useState(null), [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  useEffect(() => { authRequest("capabilities").then(value => setAvailable(Boolean(value?.mail))).catch(() => setAvailable(false)); }, []);
  useEffect(() => { setConfirmed(false); setNotice(""); }, [draft?.version]);
  if (!draft || !caseItem) return null;
  const submit = async event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request(`/cases/${caseItem.id}/drafts/${draft.id}/send`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to: values.to, subject: values.subject, message: values.message, attachment: values.attachment, expected_version: draft.version, confirmed: true }) });
      setNotice(c.sent); setConfirmed(false); onSent?.(result);
    } catch (failure) { setError(failure.status === 503 ? (failure.detail === "mail_not_configured" ? c.unavailable : c.failed) : failure.status === 409 ? c.conflict : failure.status === 429 ? c.limit : c.failed); }
    finally { setBusy(false); }
  };
  return <details className="draft-send"><summary><IconMail size={16} /> {c.title}</summary><p className="field-help">{c.intro}</p>
    {available === false ? <p className="storage-notice">{c.unavailable}</p> : dirty ? <p className="storage-notice">{c.unsaved}</p> : <form className="account-form" onSubmit={submit}><fieldset disabled={busy}><div className="intake-grid">
      <label>{c.to}<input name="to" type="email" required maxLength={254} /></label>
      <label>{c.attachment}<select name="attachment" defaultValue="pdf"><option value="pdf">{c.pdf}</option><option value="docx">{c.docx}</option></select></label>
      <label className="span-two">{c.subject}<input name="subject" required maxLength={200} defaultValue={`${caseItem.reference}${caseItem.details?.opponent_reference ? ` · Ihr Zeichen ${caseItem.details.opponent_reference}` : ""} · ${caseItem.title}`.slice(0, 200)} /></label>
      <label className="span-two">{c.message}<textarea name="message" rows={3} maxLength={5000} /></label>
      {draft.review_status !== "approved" && <p className="storage-notice span-two">{c.notApproved}</p>}
      <label className="control-check span-two"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{c.confirm}</label>
    </div></fieldset><button className="desk-button solid" disabled={busy || !confirmed}>{busy ? "…" : c.send}</button></form>}
    {error && <p className="storage-error" role="alert">{error}</p>}{notice && <p className="storage-notice" role="status">{notice}</p>}
  </details>;
}
