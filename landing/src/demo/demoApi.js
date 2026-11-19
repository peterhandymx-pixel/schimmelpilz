// Public demo (schimmelpilz.online/app/): the real interface on recorded, invented data – no server, nothing is saved.
// Data comes from demo/build_demo.py. Dates move with the calendar so the demo always looks current.
// Deadline and cost-risk calculations run here, ported 1:1 from server/deadlines.py and server/cost_risk.py.
import recorded from "./fixtures.json";

const DAY = 864e5;
const iso = date => date.toISOString().slice(0, 10);
const todayIso = () => { const d = new Date(); return iso(new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))); };
const offsetDays = Math.round((Date.parse(todayIso()) - Date.parse(recorded.recorded_on)) / DAY);
const shiftDate = value => offsetDays ? iso(new Date(Date.parse(value) + offsetDays * DAY)) : value;
const shiftText = text => offsetDays ? text.replace(/\b(20\d\d-[01]\d-[0-3]\d)(?=[T"&,\s]|$)/g, (_, date) => shiftDate(date)) : text;

const fixtures = new Map();
for (const [key, entry] of Object.entries(recorded.fixtures)) {
  const shifted = entry.json !== undefined ? { ...entry, json: JSON.parse(shiftText(JSON.stringify(entry.json))) } : entry;
  fixtures.set(shiftText(key), shifted);
}
const byPath = new Map();
for (const [key, entry] of fixtures) { const path = key.split("?")[0]; if (!byPath.has(path)) byPath.set(path, entry); }

// ---------- deadlines (server/deadlines.py) ----------
const STATES = { BW: "Baden-Württemberg", BY: "Bayern", BE: "Berlin", BB: "Brandenburg", HB: "Bremen", HH: "Hamburg", HE: "Hessen", MV: "Mecklenburg-Vorpommern", NI: "Niedersachsen", NW: "Nordrhein-Westfalen", RP: "Rheinland-Pfalz", SL: "Saarland", SN: "Sachsen", ST: "Sachsen-Anhalt", SH: "Schleswig-Holstein", TH: "Thüringen" };
const utc = (y, m, d) => new Date(Date.UTC(y, m - 1, d));
const plus = (date, days) => new Date(date.getTime() + days * DAY);
function easter(year) {
  const a = year % 19, b = Math.floor(year / 100), c = year % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  return utc(year, Math.floor((h + l - 7 * m + 114) / 31), ((h + l - 7 * m + 114) % 31) + 1);
}
function holidays(year, state) {
  const s = easter(year), r = new Map();
  const add = (date, name) => r.set(iso(date), name);
  add(utc(year, 1, 1), "Neujahr"); add(plus(s, -2), "Karfreitag"); add(plus(s, 1), "Ostermontag"); add(utc(year, 5, 1), "Tag der Arbeit");
  add(plus(s, 39), "Christi Himmelfahrt"); add(plus(s, 50), "Pfingstmontag"); add(utc(year, 10, 3), "Tag der Deutschen Einheit");
  add(utc(year, 12, 25), "1. Weihnachtstag"); add(utc(year, 12, 26), "2. Weihnachtstag");
  if (year === 2017) add(utc(2017, 10, 31), "Reformationstag (bundesweit 2017)");
  if (!state) return r;
  if (["BW", "BY", "ST"].includes(state)) add(utc(year, 1, 6), "Heilige Drei Könige");
  if ((state === "BE" && year >= 2019) || (state === "MV" && year >= 2023)) add(utc(year, 3, 8), "Internationaler Frauentag");
  if (state === "BE" && (year === 2020 || year === 2025)) add(utc(year, 5, 8), "Tag der Befreiung (einmalig)");
  if (["BW", "BY", "HE", "NW", "RP", "SL"].includes(state)) add(plus(s, 60), "Fronleichnam");
  if (state === "SL") add(utc(year, 8, 15), "Mariä Himmelfahrt");
  if (state === "TH" && year >= 2019) add(utc(year, 9, 20), "Weltkindertag");
  if (["BB", "MV", "SN", "ST", "TH"].includes(state) || (["HB", "HH", "NI", "SH"].includes(state) && year >= 2018)) add(utc(year, 10, 31), "Reformationstag");
  if (["BW", "BY", "NW", "RP", "SL"].includes(state)) add(utc(year, 11, 1), "Allerheiligen");
  if (state === "SN") { const d = utc(year, 11, 22); add(plus(d, -((d.getUTCDay() + 6 - 2 + 7) % 7)), "Buß- und Bettag"); }
  return r;
}
function addMonths(start, months) {
  const index = start.getUTCMonth() + months, year = start.getUTCFullYear() + Math.floor(index / 12), month = ((index % 12) + 12) % 12;
  const last = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return [start.getUTCDate() <= last ? utc(year, month + 1, start.getUTCDate()) : null, utc(year, month + 1, last)];
}
function deadline({ start_date, amount, unit, start_type = "event", state = null, shift_non_working_days = true }) {
  const start = new Date(start_date + "T00:00:00Z"), inclusive = start_type === "day_start";
  let end, rule;
  if (unit === "days") { end = plus(start, inclusive ? amount - 1 : amount); rule = "§ 188 Abs. 1 BGB"; }
  else if (unit === "weeks") { end = plus(start, 7 * amount - (inclusive ? 1 : 0)); rule = "§ 188 Abs. 2 BGB"; }
  else { const [corresponding, last] = addMonths(start, amount * (unit === "years" ? 12 : 1)); end = corresponding ? (inclusive ? plus(corresponding, -1) : corresponding) : last; rule = corresponding ? "§ 188 Abs. 2 BGB" : "§ 188 Abs. 3 BGB"; }
  const skipped = []; let final = end;
  while (shift_non_working_days) {
    const names = holidays(final.getUTCFullYear(), state), weekday = final.getUTCDay();
    if (weekday === 0 || weekday === 6) skipped.push({ date: iso(final), reason: weekday === 6 ? "Samstag" : "Sonntag" });
    else if (names.has(iso(final))) skipped.push({ date: iso(final), reason: names.get(iso(final)) });
    else break;
    final = plus(final, 1);
  }
  return { start: start_date, first_day: iso(inclusive ? start : plus(start, 1)), raw_end: iso(end), end: iso(final), rule, start_rule: inclusive ? "§ 187 Abs. 2 BGB" : "§ 187 Abs. 1 BGB",
    shifted: iso(final) !== iso(end), skipped, state, state_name: STATES[state] || "nur bundesweite Feiertage", scope: "calculation_aid_not_legal_verification" };
}

// ---------- cost risk (server/cost_risk.py), in cents ----------
const INSTANCES = {
  civil_first: { label: "Zivilgericht, 1. Instanz", procedure: [13, "VV 3100"], hearing: [12, "VV 3104"], settlement: [10, "VV 1003"], court: [30, "KV 1210"], settled: [10, "KV 1211"], reimburse: true },
  civil_appeal: { label: "Berufung", procedure: [16, "VV 3200"], hearing: [12, "VV 3202"], settlement: [13, "VV 1004"], court: [40, "KV 1220"], settled: [20, "KV 1222"], reimburse: true },
  labour_first: { label: "Arbeitsgericht, 1. Instanz", procedure: [13, "VV 3100"], hearing: [12, "VV 3104"], settlement: [10, "VV 1003"], court: [20, "KV 8210"], settled: [0, "Vorbem. 8 KV"], reimburse: false },
};
const cents = text => Math.round(Number(text) * 100);
const money = value => (value / 100).toFixed(2);
const times = (base, rate10) => Math.floor((base * rate10 + 5) / 10);
const rateText = rate10 => (rate10 / 10).toFixed(1).replace(".", ",");
function lawyer(base, spec, hearing, settled, vat) {
  const lines = [[`Verfahrensgebühr ${spec.procedure[1]} (${rateText(spec.procedure[0])})`, times(base, spec.procedure[0])]];
  if (hearing) lines.push([`Terminsgebühr ${spec.hearing[1]} (${rateText(spec.hearing[0])})`, times(base, spec.hearing[0])]);
  if (settled) lines.push([`Einigungsgebühr ${spec.settlement[1]} (${rateText(spec.settlement[0])})`, times(base, spec.settlement[0])]);
  const fees = lines.reduce((sum, [, amount]) => sum + amount, 0);
  lines.push(["Post- und Telekommunikationspauschale VV 7002", Math.min(Math.floor((fees * 20 + 50) / 100), 2000)]);
  const net = lines.reduce((sum, [, amount]) => sum + amount, 0), tax = vat ? Math.floor((net * 19 + 50) / 100) : 0;
  if (vat) lines.push(["19 % Umsatzsteuer VV 7008", tax]);
  return { lines: lines.map(([label, amount]) => ({ label, amount: money(amount) })), net, total: net + tax };
}
function costRisk({ value, instance = "civil_first", hearing = true, own_vat_deductible = false, opponent_vat_deductible = false, win_percent = 50 }) {
  const amount = cents(value), { values, rvg, court: courtTable } = recorded.tables;
  if (!(amount > 0) || amount > 50000000) return null;
  const index = values.findIndex(limit => amount <= limit * 100), spec = INSTANCES[instance];
  const base = cents(rvg[index]), courtBase = cents(courtTable[index]);
  const court = times(courtBase, spec.court[0]), courtSettled = times(courtBase, spec.settled[0]);
  const own = lawyer(base, spec, hearing, false, !own_vat_deductible), other = lawyer(base, spec, hearing, false, !opponent_vat_deductible);
  const ownSettled = lawyer(base, spec, hearing, true, !own_vat_deductible), otherSettled = lawyer(base, spec, hearing, true, !opponent_vat_deductible);
  const share = rest => Math.floor((rest * (100 - win_percent) + 50) / 100);
  const loss = spec.reimburse ? court + own.total + other.total : court + own.total;
  const win = spec.reimburse ? 0 : own.total;
  const quota = spec.reimburse ? share(court + own.total + other.total) : share(court) + own.total;
  const settlement = Math.floor((courtSettled + 1) / 2) + ownSettled.total;
  return {
    value: String(value), bracket: String(values[index]), instance, instance_label: spec.label, hearing, win_percent, base_fee_rvg: money(base), base_fee_court: money(courtBase),
    court: { label: `Gerichtsgebühr ${spec.court[1]} (${rateText(spec.court[0])})`, amount: money(court), settled_label: `bei Vergleich ${spec.settled[1]} (${rateText(spec.settled[0])})`, settled_amount: money(courtSettled) },
    own_lawyer: { ...own, net: money(own.net), total: money(own.total) }, other_lawyer: { ...other, net: money(other.net), total: money(other.total) },
    own_lawyer_settled_total: money(ownSettled.total), other_lawyer_settled_total: money(otherSettled.total), advance: instance === "labour_first" ? "0.00" : money(court), reimburse_lawyer: spec.reimburse,
    scenarios: [{ id: "loss", label: "Vollständiges Unterliegen", amount: money(loss) }, { id: "quota", label: `Teilweises Obsiegen (${win_percent} %) nach § 92 ZPO`, amount: money(quota) },
      { id: "win", label: "Vollständiges Obsiegen", amount: money(win) }, { id: "settlement", label: "Vergleich, Kosten gegeneinander aufgehoben", amount: money(settlement) }],
    notes: [...(spec.reimburse ? [] : ["Arbeitsgericht 1. Instanz: Jede Seite trägt ihre Anwaltskosten selbst, auch bei Obsiegen (§ 12a Abs. 1 ArbGG). Gerichtskosten werden erst am Ende fällig (§ 6 Abs. 4 GKG)."]),
      ...(own_vat_deductible ? ["Eigene Anwaltskosten ohne Umsatzsteuer gerechnet (Mandant vorsteuerabzugsberechtigt)."] : []),
      "Gebühren nach RVG/GKG in der Fassung des BGBl. 2025 I Nr. 109. Nicht enthalten: Auslagen für Zeugen und Sachverständige, Reisekosten, Mehrvergleich, abweichende Vergütungsvereinbarung."],
  };
}
// Note: Math.floor((courtSettled + 1) / 2) mirrors round-half-up of courtSettled / 2 to the cent.

// ---------- responses ----------
const json = (data, status = 200) => new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const binary = entry => {
  const bytes = Uint8Array.from(atob(entry.b64), char => char.charCodeAt(0));
  return new Response(bytes, { status: entry.status, headers: { "Content-Type": entry.type || "application/octet-stream", "Content-Disposition": entry.disposition || "",
    "X-Draft-Version": "1", "X-Draft-Review-Status": "draft", "X-Bea-Check": JSON.stringify({ ok: true, issues: [], notes: [], pages: 1, fonts: 2 }) } });
};
const fromFixture = entry => entry.b64 !== undefined ? binary(entry) : json(entry.json, entry.status);
export const blocked = () => { window.dispatchEvent(new CustomEvent("schimmelpilz-demo-blocked")); return json({ detail: "demo_read_only" }, 403); };
const me = () => fixtures.get("GET /api/auth/me").json;

function lookup(method, url) {
  const key = `${method} ${url.pathname}${url.search}`;
  if (fixtures.has(key)) return fixtures.get(key);
  if (method === "GET" && byPath.has(url.pathname)) return byPath.get(url.pathname);
  return null;
}

async function demoResponse(input, init = {}) {
  const url = new URL(typeof input === "string" ? input : input.url, window.location.origin);
  const method = (init.method || (typeof input !== "string" && input.method) || "GET").toUpperCase();
  const path = url.pathname;
  const body = () => { try { return JSON.parse(init.body || "{}"); } catch { return {}; } };
  if (path === "/api/auth/login" || path === "/api/auth/register") return json(me());
  if (path === "/api/auth/logout") { setTimeout(() => window.location.assign("/"), 50); return json(null, 204); }
  if (path === "/api/deadlines/holidays") {
    const names = holidays(Number(url.searchParams.get("year")), url.searchParams.get("state"));
    return json([...names].sort().map(([date, name]) => ({ date, name })));
  }
  if (method === "POST" && path === "/api/deadlines/calculate") return json(deadline(body()));
  if (method === "POST" && path === "/api/cost-risk/calculate") { const result = costRisk(body()); return result ? json(result) : json({ detail: "value_out_of_range" }, 422); }
  if (method === "GET") {
    const entry = lookup(method, url);
    if (entry) return fromFixture(entry);
    console.info("[Demo] keine Beispieldaten für", path + url.search);
    return json({ detail: "demo_not_available" }, 404);
  }
  return blocked();
}

export function openDemoFile(href) {
  const url = new URL(href, window.location.origin), entry = lookup("GET", url);
  if (!entry || entry.b64 === undefined) { blocked(); return; }
  const response = binary(entry);
  response.blob().then(blob => window.open(URL.createObjectURL(blob), "_blank", "noopener"));
}

export function install() {
  const original = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const target = typeof input === "string" ? input : input.url;
    const path = new URL(target, window.location.origin).pathname;
    return path.startsWith("/api/") ? demoResponse(input, init) : original(input, init);
  };
  // Plain links and window.open to /api/ (PDFs, calendar file) are served from the recorded files.
  document.addEventListener("click", event => {
    const link = event.target.closest?.("a[href]");
    if (!link) return;
    const url = new URL(link.getAttribute("href"), window.location.origin);
    if (url.origin === window.location.origin && url.pathname.startsWith("/api/")) { event.preventDefault(); openDemoFile(url.href); }
    if (url.protocol === "mailto:") return;
  }, true);
  const open = window.open.bind(window);
  window.open = (target, ...rest) => {
    if (typeof target === "string" && new URL(target, window.location.origin).pathname.startsWith("/api/")) { openDemoFile(target); return null; }
    return open(target, ...rest);
  };
}
