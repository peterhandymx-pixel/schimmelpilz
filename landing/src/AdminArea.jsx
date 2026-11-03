import { useCallback, useEffect, useState } from "react";
import { IconArrowLeft, IconCopy, IconDownload, IconRefresh } from "@tabler/icons-react";
import { request, API_BASE } from "./useCaseStorage.js";
import { dateLabel, matches } from "./workbench.js";
import { PaymentForm, PLAN_NAMES, STATUS_NAMES, money, send, textError } from "./ControlCenter.jsx";
import "./admin.css";

const AUDIENCES = { consumer: "Verbraucher", business: "Unternehmen", law_firm: "Kanzlei" };
const PROVIDERS = { clip: "Clip", demo: "Testzahlung", manual: "Gutschrift" };
const ACTIONS = {
  admin_profile_edit: "Stammdaten geändert", admin_email_verified: "E-Mail bestätigt", admin_password_reset: "Passwort-Link erstellt", admin_mfa_reset: "Zwei-Faktor zurückgesetzt",
  admin_user_deleted: "Konto gelöscht", admin_trial_extended: "Test verlängert", admin_plan_changed: "Tarif geändert", admin_free_months: "Gratis-Monate", admin_payment_reversed: "Buchung storniert",
  admin_test_mail: "Testmail", admin_promoted_locally: "Zum Admin ernannt", user_control: "Sperre / Rolle geändert", sessions_revoked: "Sitzungen beendet", system_settings_changed: "Betriebseinstellungen",
  payment_recorded: "Zahlung erfasst", access_ended: "Zugang beendet", demo_payment: "Testzahlung", invite_created: "Einladung erstellt", invite_accepted: "Einladung angenommen", invite_revoked: "Einladung widerrufen",
  membership_updated: "Teamrechte geändert", workspace_selected: "Arbeitsbereich gewechselt", POST: "Anfrage (POST)", PUT: "Anfrage (PUT)", DELETE: "Anfrage (DELETE)",
};
const actionName = action => ACTIONS[action] || action;
const bytes = value => value > 1e9 ? `${(value / 1e9).toLocaleString("de-DE", { maximumFractionDigits: 1 })} GB` : value > 1e6 ? `${Math.round(value / 1e6).toLocaleString("de-DE")} MB` : `${Math.max(1, Math.round(value / 1e3)).toLocaleString("de-DE")} KB`;
// The last twelve calendar months, oldest first, so the chart always has a full axis.
const lastMonths = () => Array.from({ length: 12 }, (_, i) => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 11 + i); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; });
const adminError = (error, de) => ({
  administrator_required: "Nur der freigegebene Administrator hat Zugang.",
  admin_not_allowlisted: "Diese Adresse steht nicht in ADMIN_EMAILS und kann kein Administrator werden.",
  email_taken: "Diese E-Mail-Adresse gehört bereits zu einem anderen Konto.",
  confirmation_mismatch: "Die Bestätigung stimmt nicht mit der E-Mail-Adresse des Kontos überein.",
  last_administrator: "Der letzte Administrator kann nicht entfernt werden.",
  only_latest_payment: "Nur die jeweils letzte Buchung eines Kontos kann storniert werden.",
  already_reversed: "Diese Buchung ist bereits storniert.",
  mail_not_configured: "E-Mail-Versand ist nicht eingerichtet (SMTP oder MAIL_OUTBOX_DIR in .env).",
}[error.detail] || (error.status === 422 ? "Eingaben prüfen – eine Begründung braucht mindestens 10 Zeichen." : textError(error, de)));

function useAdmin(path) {
  const [data, setData] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const load = useCallback(() => path ? request(path).then(setData).catch(e => setError(adminError(e, true))) : Promise.resolve(), [path]);
  useEffect(() => { setData(null); setError(""); load(); }, [load]);
  // Runs a change, then reloads; returns the result so callers can show links or references.
  const act = async work => { setBusy(true); setError(""); try { const result = (await work()) ?? true; await load(); return result; } catch (e) { setError(adminError(e, true)); return null; } finally { setBusy(false); } };
  return { data, error, busy, act, load, setError };
}

const Notice = ({ error, notice }) => <>{error && <p role="alert" className="storage-error">{error}</p>}{notice && <p role="status" className="storage-notice">{notice}</p>}</>;

// ---------------- Overview ----------------
function Overview({ lang, openUser }) {
  const { data, error, load } = useAdmin("/admin/overview");
  if (!data) return <Notice error={error} />;
  const max = Math.max(1, ...data.revenue.map(m => m.paid + m.test));
  const months = lastMonths().map(month => data.revenue.find(m => m.month === month) || { month, paid: 0, test: 0 });
  const tiles = [["Benutzer", data.counts.users], ["Neu (30 Tage)", data.signups_30d], ["Bezahlt", data.subscriptions.active || 0], ["Im Test", data.subscriptions.trial || 0], ["Abgelaufen", data.subscriptions.expired || 0], ["Akten", data.counts.cases], ["Dokumente", data.counts.documents], ["Speicher", bytes(data.storage_bytes)]];
  return <>
    <div className="admin-head"><h2>Übersicht</h2><button className="desk-link" onClick={load}><IconRefresh size={16} />Aktualisieren</button></div>
    {data.payment_mode === "demo" && <p className="demo-banner"><strong>Testmodus</strong> Zahlungen werden simuliert (PAYMENT_MODE=demo).</p>}
    <div className="admin-tiles">{tiles.map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
    <div className="admin-columns">
      <section className="admin-card"><h3>Einnahmen der letzten 12 Monate</h3>
        {data.revenue.length ? <div className="admin-bars">{months.map(m => <div key={m.month} title={`${m.month}: ${money(m.paid, data.currency, lang)}${m.test ? ` + Test ${money(m.test, data.currency, lang)}` : ""}`}>
          <span className="bar-paid" style={{ height: `${(m.paid / max) * 100}%` }} /><span className="bar-test" style={{ height: `${(m.test / max) * 100}%` }} /><small>{m.month.slice(5)}/{m.month.slice(2, 4)}</small></div>)}</div> : <p className="desk-empty">Noch keine Zahlungen.</p>}
        <p className="field-help"><span className="legend-paid" /> echte Zahlungen <span className="legend-test" /> Testzahlungen · Summe echt: <strong>{money(data.revenue.reduce((s, m) => s + m.paid, 0), data.currency, lang)}</strong></p>
      </section>
      <section className="admin-card"><h3>Läuft in 7 Tagen ab</h3>
        {data.ending_soon.length ? <ul className="admin-list">{data.ending_soon.map(item => <li key={item.user_id}><button className="desk-link" onClick={() => openUser(item.user_id)}>{item.full_name} · {item.email}</button><small>{STATUS_NAMES.de[item.status]} bis {dateLabel(item.ends, lang)}</small></li>)}</ul> : <p className="desk-empty">Nichts läuft in den nächsten 7 Tagen ab.</p>}
      </section>
    </div>
    <section className="admin-card"><h3>Letzte Buchungen</h3>
      {data.recent_payments.length ? <table className="desk-table"><thead><tr><th>Datum</th><th>Konto</th><th>Tarif</th><th>Betrag</th><th>Art</th><th>Referenz</th></tr></thead><tbody>
        {data.recent_payments.map(p => <tr key={p.id} className={p.reversed_at ? "admin-reversed" : ""}><td>{dateLabel(p.paid_on, lang)}</td><td><button className="desk-link" onClick={() => openUser(p.user_id)}>{p.full_name || p.email}</button></td><td>{PLAN_NAMES.de[p.plan]} · {p.months} M.</td><td>{money(p.amount_minor, p.currency, lang)}</td><td>{PROVIDERS[p.provider] || p.provider}{p.reversed_at ? " · storniert" : ""}</td><td>{p.reference}</td></tr>)}
      </tbody></table> : <p className="desk-empty">Noch keine Buchungen.</p>}
    </section>
  </>;
}

// ---------------- Users ----------------
function UserList({ lang, openUser }) {
  const { data, error } = useAdmin("/admin");
  const [query, setQuery] = useState(""), [filter, setFilter] = useState("all");
  if (!data) return <Notice error={error} />;
  const shown = data.users.filter(u => matches(query, u.email, u.full_name, u.organisation) && (filter === "all" || (filter === "admin" ? u.is_admin : filter === "disabled" ? u.disabled : !u.disabled)));
  return <>
    <div className="admin-head"><h2>Benutzer</h2><span>{data.users.length} Konten</span></div>
    <div className="eakte-filter"><label>Suchen<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Name, E-Mail, Organisation" /></label>
      <label>Anzeigen<select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Alle</option><option value="active">Aktiv</option><option value="disabled">Gesperrt</option><option value="admin">Administratoren</option></select></label><span>{shown.length} angezeigt</span></div>
    <div className="desk-table-scroll"><table className="desk-table admin-users"><thead><tr><th>Name / E-Mail</th><th>Art</th><th>Akten</th><th>Registriert</th><th>Status</th><th></th></tr></thead><tbody>
      {shown.map(u => <tr key={u.id}><td><strong>{u.full_name}</strong><small>{u.email}{u.organisation ? ` · ${u.organisation}` : ""}</small></td><td>{AUDIENCES[u.audience] || u.audience}</td><td>{u.case_count}</td><td>{dateLabel(u.created_at, lang)}</td>
        <td>{u.disabled ? <span className="admin-pill off">Gesperrt</span> : <span className="admin-pill on">Aktiv</span>}{u.is_admin ? <span className="admin-pill admin">Admin</span> : null}</td>
        <td><button className="desk-button" onClick={() => openUser(u.id)}>Öffnen</button></td></tr>)}
    </tbody></table></div>
  </>;
}

function UserDetail({ lang, id, back, currentUser }) {
  const { data, error, busy, act } = useAdmin(`/admin/users/${id}`);
  const billing = useAdmin("/admin/billing");
  const [reason, setReason] = useState(""), [notice, setNotice] = useState(""), [resetLink, setResetLink] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(""), [trialDays, setTrialDays] = useState(7), [freeMonths, setFreeMonths] = useState(1);
  if (!data) return <><button className="desk-link" onClick={back}><IconArrowLeft size={16} />Zurück zur Liste</button><Notice error={error} /></>;
  const u = data.user, sub = data.subscription, self = u.id === currentUser.id;
  const item = billing.data?.subscriptions.find(s => s.user_id === u.id);
  const needReason = reason.trim().length < 10;
  const run = async (work, message) => { setNotice(""); const result = await act(work); if (result !== null) { setNotice(message); billing.load(); } return result; };
  const latest = data.payments.filter(p => !p.reversed_at).sort((a, b) => b.period_end.localeCompare(a.period_end))[0];
  return <>
    <button className="desk-link" onClick={back}><IconArrowLeft size={16} />Zurück zur Liste</button>
    <div className="admin-head"><h2>{u.full_name}</h2><span>{u.email}{u.is_admin ? " · Administrator" : ""}{u.disabled ? " · gesperrt" : ""}</span></div>
    <Notice error={error || billing.error} notice={notice} />
    <label className="admin-reason">Begründung für die nächste Änderung * <small>(wird protokolliert, mindestens 10 Zeichen)</small><input value={reason} onChange={e => setReason(e.target.value)} placeholder="z. B. Kundenanfrage per E-Mail vom 02.11.2026" /></label>

    <div className="admin-columns">
      <section className="admin-card"><h3>Stammdaten</h3>
        <form key={u.control_version} onSubmit={e => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.currentTarget)); run(() => request(`/admin/users/${u.id}/profile`, send("PUT", { ...f, reason, expected_version: u.control_version })), "Stammdaten gespeichert."); }}>
          <fieldset disabled={busy}>
            <label>Name<input name="full_name" required minLength={3} defaultValue={u.full_name} /></label>
            <label>Organisation<input name="organisation" defaultValue={u.organisation} /></label>
            <label>E-Mail<input name="email" type="email" required defaultValue={u.email} /></label>
            <label>Telefon<input name="phone" defaultValue={u.phone} /></label>
            <label>Art<select name="audience" defaultValue={u.audience}>{Object.entries(AUDIENCES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <p className="field-help">Anschrift: {u.street}, {u.postal_code} {u.city}, {u.country} · registriert {dateLabel(u.created_at, lang, true)}</p>
            <button className="desk-button solid" disabled={needReason}>Stammdaten speichern</button>
          </fieldset></form>
      </section>
      <section className="admin-card"><h3>Konto & Sicherheit</h3>
        <ul className="admin-facts">
          <li>E-Mail bestätigt: <strong>{u.email_verified_at ? dateLabel(u.email_verified_at, lang) : "nein"}</strong></li>
          <li>Zwei-Faktor: <strong>{u.mfa_enabled_at ? "aktiv" : "nicht aktiv"}</strong></li>
          <li>Aktive Sitzungen: <strong>{data.counts.sessions}</strong></li>
          <li>Akten {data.counts.cases} · Dokumente {data.counts.documents} · Entwürfe {data.counts.drafts} · Adressen {data.counts.contacts}</li>
          {data.team.members.length > 0 && <li>Teammitglieder: {data.team.members.map(m => `${m.email} (${m.role})`).join(", ")}</li>}
          {data.team.member_of.length > 0 && <li>Mitglied bei: {data.team.member_of.map(m => `${m.email} (${m.role})`).join(", ")}</li>}
        </ul>
        <div className="admin-actions">
          {!u.email_verified_at && <button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/users/${u.id}/verify-email`, send("POST", { reason })), "E-Mail als bestätigt markiert.")}>E-Mail als bestätigt markieren</button>}
          <button className="desk-button" disabled={busy || needReason} onClick={async () => { const r = await run(() => request(`/admin/users/${u.id}/password-reset`, send("POST", { reason })), "Link zum Zurücksetzen erstellt."); if (r) setResetLink(r); }}>Passwort-Link erstellen</button>
          {u.mfa_enabled_at && !self && <button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/users/${u.id}/reset-mfa`, send("POST", { reason })), "Zwei-Faktor zurückgesetzt; alle Sitzungen beendet.")}>Zwei-Faktor zurücksetzen</button>}
          <button className="desk-button" disabled={busy} onClick={() => run(() => request(`/admin/users/${u.id}/revoke-sessions`, send("POST", {})), "Alle Sitzungen beendet.")}>Alle Sitzungen abmelden</button>
          {!self && <button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/users/${u.id}`, send("PUT", { disabled: !u.disabled, is_admin: Boolean(u.is_admin), expected_version: u.control_version, reason })), u.disabled ? "Konto entsperrt." : "Konto gesperrt; Sitzungen beendet.")}>{u.disabled ? "Konto entsperren" : "Konto sperren"}</button>}
          {!self && Boolean(u.is_admin) && <button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/users/${u.id}`, send("PUT", { disabled: Boolean(u.disabled), is_admin: false, expected_version: u.control_version, reason })), "Administratorrecht entzogen.")}>Administratorrecht entziehen</button>}
        </div>
        {resetLink && <div className="storage-notice"><p>{resetLink.mailed ? "Der Link wurde zusätzlich per E-Mail verschickt." : "Kein E-Mail-Versand eingerichtet – Link bitte sicher selbst weitergeben."} Gültig {resetLink.expires_hours} Stunde, einmal verwendbar.</p>
          <code className="admin-link">{resetLink.link}</code><button className="desk-link" onClick={() => navigator.clipboard?.writeText(resetLink.link)}><IconCopy size={15} />Kopieren</button></div>}
      </section>
    </div>

    <section className="admin-card"><h3>Abonnement & Zahlungen</h3>
      <p><strong>{PLAN_NAMES.de[sub.plan]}</strong> · {STATUS_NAMES.de[sub.effective_status] || sub.effective_status}
        {sub.trial_end && <> · Test bis {dateLabel(sub.trial_end, lang)}</>}{sub.period_end && <> · bezahlt bis {dateLabel(sub.period_end, lang)}</>}</p>
      {item?.pending_payment && <p className="storage-notice">Zahlungslink geöffnet am {dateLabel(item.pending_payment.created_at, lang, true)} ({PLAN_NAMES.de[item.pending_payment.plan]}) – Zahlung im Clip-Dashboard prüfen.</p>}
      <div className="admin-actions">
        <label className="admin-inline">Test verlängern um<input type="number" min={1} max={90} value={trialDays} onChange={e => setTrialDays(Number(e.target.value) || 1)} />Tage<button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/billing/${u.id}/extend-trial`, send("POST", { days: trialDays, reason, expected_version: sub.version })), `Test um ${trialDays} Tage verlängert.`)}>Verlängern</button></label>
        <label className="admin-inline">Tarif<select key={sub.version} defaultValue={sub.plan} id="admin-plan">{Object.entries(PLAN_NAMES.de).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select><button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/billing/${u.id}/plan`, send("PUT", { plan: document.getElementById("admin-plan").value, reason, expected_version: sub.version })), "Tarif geändert.")}>Ändern</button></label>
        <label className="admin-inline">Gratis-Monate<input type="number" min={1} max={12} value={freeMonths} onChange={e => setFreeMonths(Number(e.target.value) || 1)} /><button className="desk-button" disabled={busy || needReason} onClick={() => run(() => request(`/admin/billing/${u.id}/free-months`, send("POST", { plan: sub.plan, months: freeMonths, reason, expected_version: sub.version })), `${freeMonths} Monat(e) gutgeschrieben.`)}>Gutschreiben</button></label>
        <button className="desk-button" disabled={busy || needReason || sub.effective_status === "expired"} onClick={() => run(() => request(`/admin/billing/${u.id}`, send("PUT", { pilot: false, reason, expected_version: sub.version })), "Zugang beendet.")}>Zugang sofort beenden</button>
      </div>
      {item && billing.data && <PaymentForm key={item.version} lang={lang} billing={billing.data} item={item} busy={busy} action={work => run(work, "Zahlung erfasst und freigeschaltet.")} />}
      {data.payments.length ? <table className="desk-table"><thead><tr><th>Datum</th><th>Tarif</th><th>Betrag</th><th>Art / Referenz</th><th>Zeitraum</th><th></th></tr></thead><tbody>
        {data.payments.map(p => <tr key={p.id} className={p.reversed_at ? "admin-reversed" : ""}><td>{dateLabel(p.paid_on, lang)}</td><td>{PLAN_NAMES.de[p.plan]} · {p.months} M.</td><td>{money(p.amount_minor, p.currency, lang)}</td><td>{PROVIDERS[p.provider] || p.provider} {p.reference}{p.note ? <small>{p.note}</small> : null}{p.reversed_at ? <small>storniert {dateLabel(p.reversed_at, lang)}: {p.reversed_reason}</small> : null}</td><td>{dateLabel(p.period_start, lang)} – {dateLabel(p.period_end, lang)}</td>
          <td>{latest && p.id === latest.id && <button className="desk-link" disabled={busy || needReason} onClick={() => run(() => request(`/admin/payments/${p.id}/reverse`, send("POST", { reason })), "Buchung storniert; Zugang neu berechnet.")}>Stornieren</button>}</td></tr>)}
      </tbody></table> : <p className="desk-empty">Noch keine Zahlungen.</p>}
    </section>

    {data.audit.length > 0 && <section className="admin-card"><h3>Protokoll zu diesem Konto</h3><ol className="control-audit">{data.audit.map((a, i) => <li key={i}>{dateLabel(a.created_at, lang, true)} · {a.actor_email || "—"} · {actionName(a.action)}<small>{a.target}</small></li>)}</ol></section>}

    {!self && <section className="admin-card admin-danger"><h3>Konto löschen</h3>
      <p>Löscht das Konto mit allen Akten, Dokumenten und Entwürfen endgültig. Zahlungsbelege bleiben für die Buchhaltung erhalten.</p>
      <label>Zur Bestätigung die E-Mail-Adresse eingeben<input value={confirmDelete} onChange={e => setConfirmDelete(e.target.value)} placeholder={u.email} /></label>
      <button className="desk-button danger" disabled={busy || needReason || confirmDelete.trim().toLowerCase() !== u.email} onClick={async () => { const r = await act(() => request(`/admin/users/${u.id}?confirm=${encodeURIComponent(confirmDelete.trim())}&reason=${encodeURIComponent(reason)}`, { method: "DELETE" })); if (r !== null) back(); }}>Konto endgültig löschen</button>
    </section>}
  </>;
}

// ---------------- Billing ----------------
function Billing({ lang, openUser }) {
  const { data, error, load } = useAdmin("/admin/billing");
  const [filter, setFilter] = useState("all"), [query, setQuery] = useState("");
  if (!data) return <Notice error={error} />;
  const shown = data.subscriptions.filter(s => (filter === "all" || s.effective_status === filter || (filter === "pending" && s.pending_payment) || (filter === "due" && s.renewal_due)) && matches(query, s.email));
  return <>
    <div className="admin-head"><h2>Abrechnungen</h2><div className="admin-actions"><a className="desk-button" href={`${API_BASE}/api/admin/payments.csv`}><IconDownload size={16} />Alle Zahlungen als CSV</a><button className="desk-link" onClick={load}><IconRefresh size={16} />Aktualisieren</button></div></div>
    <p>Preise: {Object.entries(data.plans).map(([k, v]) => `${PLAN_NAMES.de[k]} ${money(v, data.currency, lang)}`).join(" · ")} · Clip-Links: {Object.entries(data.links_ready).map(([k, v]) => `${PLAN_NAMES.de[k]} ${v ? "✓" : "—"}`).join(" · ")}</p>
    {!data.checkout_ready && <p className="storage-notice">Noch kein Zahlungslink eingerichtet (CLIP_LINK_* in .env).</p>}
    <div className="eakte-filter"><label>Suchen<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="E-Mail" /></label>
      <label>Status<select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Alle</option><option value="trial">Im Test</option><option value="active">Bezahlt</option><option value="expired">Abgelaufen</option><option value="due">Läuft bald ab</option><option value="pending">Zahlungslink geöffnet</option></select></label><span>{shown.length} Konten</span></div>
    <div className="desk-table-scroll"><table className="desk-table"><thead><tr><th>Konto</th><th>Tarif</th><th>Status</th><th>Läuft bis</th><th>Letzte Zahlung</th><th></th></tr></thead><tbody>
      {shown.map(s => <tr key={s.user_id}><td>{s.email}{s.pending_payment && <small>Zahlungslink geöffnet {dateLabel(s.pending_payment.created_at, lang)}</small>}</td><td>{PLAN_NAMES.de[s.plan]}</td><td>{STATUS_NAMES.de[s.effective_status]?.split(" –")[0] || s.effective_status}{s.renewal_due ? " · bald fällig" : ""}</td>
        <td>{dateLabel(s.effective_status === "active" ? s.period_end : s.trial_end, lang)}</td><td>{(p => p ? `${dateLabel(p.paid_on, lang)} · ${money(p.amount_minor, p.currency, lang)}` : "—")(s.payments.find(p => !p.reversed_at))}</td>
        <td><button className="desk-button" onClick={() => openUser(s.user_id)}>Bearbeiten</button></td></tr>)}
    </tbody></table></div>
  </>;
}

// ---------------- Tools ----------------
function Tools({ lang }) {
  const { data, error, busy, act } = useAdmin("/admin/tools");
  const system = useAdmin("/admin/system");
  const [notice, setNotice] = useState(""), [mailTo, setMailTo] = useState("");
  if (!data || !system.data) return <Notice error={error || system.error} />;
  const settings = system.data.settings;
  const check = ok => ok ? <span className="admin-pill on">bereit</span> : <span className="admin-pill off">fehlt</span>;
  return <>
    <div className="admin-head"><h2>Tools & System</h2></div>
    <Notice error={error || system.error} notice={notice} />
    <div className="admin-columns">
      <section className="admin-card"><h3>Systemstatus</h3><ul className="admin-facts">
        <li>KI-Modell: {data.ai?.model || "—"} {check(data.ai?.ready)}</li>
        <li>Texterkennung (OCR) {check(data.ocr_available)}</li>
        <li>Quellenkatalog: {data.catalogue?.laws?.length ?? 0} Gesetzessammlungen</li>
        <li>E-Mail: {data.mail.smtp ? "SMTP" : data.mail.outbox ? "lokaler Postausgang" : "nicht eingerichtet"} {check(data.mail.smtp || data.mail.outbox)}</li>
        <li>Zahlungen: {data.payment_mode === "demo" ? "Testmodus" : "Clip"} · Links {Object.values(data.links_ready).filter(Boolean).length}/3</li>
        <li>Admin-Sperre (ADMIN_EMAILS) {check(data.admin_allowlist)}</li>
        <li>Speicherplatz frei: {bytes(data.disk.free)} von {bytes(data.disk.total)}</li>
      </ul></section>
      <section className="admin-card"><h3>Betrieb steuern</h3>
        <form key={settings.version} onSubmit={e => { e.preventDefault(); const v = new FormData(e.currentTarget); system.act(() => request("/admin/system", send("PUT", { ai_enabled: v.get("ai") === "on", registrations_enabled: v.get("registrations") === "on", expected_version: settings.version, reason: v.get("reason") }))).then(r => r && setNotice("Betriebseinstellungen gespeichert.")); }}>
          <fieldset disabled={system.busy}>
            <label className="control-check"><input name="ai" type="checkbox" defaultChecked={Boolean(settings.ai_enabled)} />Neue KI-Anfragen zulassen</label>
            <label className="control-check"><input name="registrations" type="checkbox" defaultChecked={Boolean(settings.registrations_enabled)} />Neue Registrierungen zulassen</label>
            <label>Begründung *<input name="reason" required minLength={10} maxLength={500} /></label>
            <button className="desk-button solid">Speichern</button>
          </fieldset></form>
        <button className="desk-button" disabled={busy} onClick={() => act(() => request("/legal/refresh", send("POST", {}))).then(r => r !== null && setNotice("Quellenkatalog wird im Hintergrund aktualisiert."))}>Quellenkatalog aktualisieren</button>
      </section>
    </div>
    <section className="admin-card"><h3>E-Mail testen</h3>
      <form className="admin-inline" onSubmit={e => { e.preventDefault(); act(() => request("/admin/tools/test-mail", send("POST", { to: mailTo }))).then(r => r && setNotice(r.outbox ? "Testmail liegt im lokalen Postausgang (siehe unten)." : "Testmail verschickt.")); }}>
        <input type="email" required value={mailTo} onChange={e => setMailTo(e.target.value)} placeholder="empfaenger@example.com" /><button className="desk-button" disabled={busy}>Testmail senden</button></form>
      {data.mail.outbox && <><h4>Lokaler Postausgang</h4>{data.mail.messages.length ? <ul className="admin-list">{data.mail.messages.map(m => <li key={m.id}><a className="desk-link" href={`${API_BASE}/api/admin/tools/mail/${m.id}`}>{m.subject}</a><small>an {m.to} · {dateLabel(m.date, lang, true)}</small></li>)}</ul> : <p className="desk-empty">Noch keine Nachrichten.</p>}</>}
    </section>
  </>;
}

// ---------------- Audit ----------------
function Audit({ lang }) {
  const [q, setQ] = useState(""), [action, setAction] = useState(""), [entries, setEntries] = useState([]), [actions, setActions] = useState([]), [error, setError] = useState(""), [more, setMore] = useState(false);
  const load = useCallback(async before => {
    try {
      const params = new URLSearchParams({ q, action, limit: "100", ...(before ? { before } : {}) });
      const data = await request(`/admin/audit?${params}`);
      setEntries(current => before ? [...current, ...data.entries] : data.entries); setActions(data.actions); setMore(data.entries.length === 100);
    } catch (e) { setError(adminError(e, true)); }
  }, [q, action]);
  useEffect(() => { const timer = setTimeout(() => load(), 250); return () => clearTimeout(timer); }, [load]);
  return <>
    <div className="admin-head"><h2>Protokoll</h2><span>Alle Verwaltungs- und Zahlungsaktionen</span></div>
    <Notice error={error} />
    <div className="eakte-filter"><label>Suchen<input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="E-Mail, Konto-ID, Text" /></label>
      <label>Aktion<select value={action} onChange={e => setAction(e.target.value)}><option value="">Alle</option>{actions.map(a => <option key={a} value={a}>{actionName(a)}</option>)}</select></label></div>
    <ol className="control-audit">{entries.map(item => <li key={item.id}>{dateLabel(item.created_at, lang, true)} · {item.actor_email || "—"} · <strong>{actionName(item.action)}</strong><small>{item.target}</small></li>)}</ol>
    {more && <button className="desk-button" onClick={() => load(entries[entries.length - 1].created_at)}>Ältere laden</button>}
  </>;
}

export function AdminArea({ lang, tab, user, onTab }) {
  const [userId, setUserId] = useState(null);
  const openUser = id => { setUserId(id); onTab("users"); };
  useEffect(() => { if (tab !== "users") setUserId(null); }, [tab]);
  if (!user.mfa_enabled) return <section className="desk-panel admin-area"><h2>Administration</h2><p className="storage-notice">Die Verwaltung ist erst nach Aktivierung der Zwei-Faktor-Anmeldung verfügbar. Richten Sie sie unter Kanzlei / Profil ein und melden Sie sich danach neu an.</p></section>;
  return <section className="desk-panel admin-area">
    {tab === "overview" && <Overview lang={lang} openUser={openUser} />}
    {tab === "users" && (userId ? <UserDetail key={userId} lang={lang} id={userId} currentUser={user} back={() => setUserId(null)} /> : <UserList lang={lang} openUser={openUser} />)}
    {tab === "billing" && <Billing lang={lang} openUser={openUser} />}
    {tab === "tools" && <Tools lang={lang} />}
    {tab === "audit" && <Audit lang={lang} />}
  </section>;
}
