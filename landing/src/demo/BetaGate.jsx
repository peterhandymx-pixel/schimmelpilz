import { useState } from "react";

// Entry to the public demo: a beta-test code. Only its SHA-256 is in the page; the check runs in the browser,
// so this keeps casual visitors out but is no protection for confidential data (the demo has none).
const CODE_SHA256 = "5e5c743a015ff8d81e2374d5bca1bdf8ed87ce18484fce8cf4062183dde08493";
const KEY = "schimmelpilz-beta-access";

async function sha256(text) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

export const hasAccess = () => { try { return localStorage.getItem(KEY) === CODE_SHA256; } catch { return false; } };

export function BetaGate({ onEnter }) {
  const [code, setCode] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError("");
    const hash = await sha256(code.trim());
    if (hash === CODE_SHA256) {
      try { localStorage.setItem(KEY, hash); } catch { /* access for this visit only */ }
      onEnter();
    } else { setError("Dieser Code ist nicht gültig. Bitte prüfen Sie die Eingabe."); setBusy(false); }
  };
  return <main className="beta-gate">
    <form className="beta-card" onSubmit={submit}>
      <img src={`${import.meta.env.BASE_URL}icon-192.png`} alt="" width="64" height="64" />
      <p className="beta-eyebrow">Rechtsassistentin Schimmelpilz · Beta</p>
      <h1>Einloggen</h1>
      <label htmlFor="beta-code">Wie lautet Ihr Beta-Test-Code?</label>
      <input id="beta-code" value={code} onChange={event => setCode(event.target.value)} inputMode="numeric" autoComplete="one-time-code" autoFocus required maxLength={40} />
      {error && <p className="beta-error" role="alert">{error}</p>}
      <button disabled={busy || !code.trim()}>{busy ? "…" : "Weiter"}</button>
      <p className="beta-note">Sie erhalten den Code von der Kanzlei. Die Testversion zeigt erfundene Beispielakten.</p>
      <a href="/">← Zur Website</a>
    </form>
  </main>;
}
