import { useCallback, useEffect, useRef, useState } from "react";
import { IconMicrophone, IconPlayerPlay, IconPlayerPause, IconPlayerStop, IconPlayerTrackPrev, IconPlayerTrackNext, IconPlayerSkipBack, IconPlayerSkipForward, IconSend, IconTrash, IconHeadphones, IconCheck, IconArrowBackUp, IconFileText, IconLoader2 } from "@tabler/icons-react";
import { API_BASE, request } from "./useCaseStorage.js";
import { DictationTape, bindDictationKeys, decodeWav, formatTime } from "./dictationTape.js";
import "./dictation.css";

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const PRIORITY = { normal: "Normal", urgent: "Eilig", immediate: "Sofort" };
const STATUS = { open: "Offen im Pool", in_progress: "In Bearbeitung", done: "Erledigt" };
const stamp = value => value ? new Date(value).toLocaleString("de-DE", { timeZone: "Europe/Berlin", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
const length = ms => formatTime(ms * 16, 16000);

// Re-renders the component whenever the tape changes, and keeps the clock moving during playback.
function useTape(factory) {
  const [, setTick] = useState(0);
  const tape = useRef(null);
  if (!tape.current) tape.current = factory(() => setTick(value => value + 1));
  useEffect(() => {
    const timer = setInterval(() => { if (tape.current.state !== "idle") setTick(value => value + 1); }, 100);
    return () => { clearInterval(timer); tape.current.close(); };
  }, []);
  return tape.current;
}

function Transport({ tape, record = false, autoRewind = 0 }) {
  const cursor = tape.cursor, total = Math.max(tape.duration, cursor);
  const percent = total ? (cursor / total) * 100 : 0;
  const bar = useRef(null);
  const seek = event => { const box = bar.current.getBoundingClientRect(); tape.seek(((event.clientX - box.left) / box.width) * tape.length); };
  const playPause = () => { if (tape.state === "playing") { tape.stop(); if (autoRewind) tape.skip(-autoRewind); } else tape.play(); };
  return <div className="dictation-transport">
    <div className="dictation-clock" aria-live="off"><strong>{formatTime(cursor, tape.rate)}</strong><span> / {formatTime(total, tape.rate)}</span>
      {tape.state === "recording" && <em className="dictation-rec">● {tape.mode === "insert" ? "Einfügen" : "Aufnahme"}</em>}
      {tape.state === "playing" && <em>▶ Wiedergabe{tape.speed !== 1 ? ` ${tape.speed.toFixed(1)}×` : ""}</em>}</div>
    <div className="dictation-bar" ref={bar} onClick={tape.state === "recording" ? undefined : seek} role="slider" aria-label="Position im Diktat" aria-valuemin={0} aria-valuemax={Math.round(total / tape.rate)} aria-valuenow={Math.round(cursor / tape.rate)}>
      <span style={{ width: `${percent}%` }} />{tape.state === "recording" && <i style={{ width: `${Math.min(100, tape.level * 140)}%` }} />}</div>
    <div className="dictation-buttons">
      <button type="button" title="Zum Anfang (Pos1)" onClick={() => tape.seek(0)} disabled={tape.state === "recording"}><IconPlayerSkipBack size={18} /></button>
      <button type="button" title="Rückspulen (F6, halten = schnell)" onClick={() => tape.skip(-2)} disabled={tape.state === "recording"}><IconPlayerTrackPrev size={18} /><kbd>F6</kbd></button>
      <button type="button" className="dictation-main" title="Wiedergabe / Pause (F5)" onClick={playPause} disabled={tape.state === "recording" || !tape.length}>{tape.state === "playing" ? <IconPlayerPause size={20} /> : <IconPlayerPlay size={20} />}<kbd>F5</kbd></button>
      <button type="button" title="Stopp (F4)" onClick={() => tape.stop()}><IconPlayerStop size={18} /><kbd>F4</kbd></button>
      <button type="button" title="Vorspulen (F7, halten = schnell)" onClick={() => tape.skip(2)} disabled={tape.state === "recording"}><IconPlayerTrackNext size={18} /><kbd>F7</kbd></button>
      <button type="button" title="Zum Ende (Ende)" onClick={() => tape.seek(tape.length)} disabled={tape.state === "recording"}><IconPlayerSkipForward size={18} /></button>
      {record && <button type="button" className={`dictation-record${tape.state === "recording" ? " active" : ""}`} title="Aufnahme starten / anhalten (F8)" onClick={() => tape.state === "recording" ? tape.stop() : tape.record().catch(() => tape.emit())}><IconMicrophone size={20} />{tape.state === "recording" ? "Anhalten" : "Aufnahme"}<kbd>F8</kbd></button>}
    </div>
  </div>;
}

function usePosKeys(tape) {
  useEffect(() => {
    const keys = event => {
      if (/input|textarea|select/i.test(event.target?.tagName || "") || tape.state === "recording") return;
      if (event.key === "Home") { event.preventDefault(); tape.seek(0); }
      if (event.key === "End") { event.preventDefault(); tape.seek(tape.length); }
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [tape]);
}

// The lawyer's dictation window: record against a case, correct by overwriting or inserting, send to the pool.
export function DictationRecorder({ cases, preferredCaseId = "", onSent }) {
  const tape = useTape(onChange => new DictationTape({ onChange }));
  const active = cases.filter(item => !item.archived_at);
  const [caseId, setCaseId] = useState(preferredCaseId && active.some(item => item.id === preferredCaseId) ? preferredCaseId : "");
  const [priority, setPriority] = useState("normal"), [note, setNote] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [mine, setMine] = useState([]);
  const load = useCallback(() => request("/dictations?status=all").then(result => setMine(result.items.filter(item => item.author_id === result.me).slice(0, 12))).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => bindDictationKeys(tape, { record: true }), [tape]);
  usePosKeys(tape);
  useEffect(() => {
    const guard = event => { if (tape.dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [tape]);
  useEffect(() => { if (tape.state === "recording") setError(""); }, [tape.state]);

  const send = async () => {
    if (!caseId) { setError("Bitte zuerst die Akte wählen."); return; }
    if (tape.duration < tape.rate) { setError("Das Diktat ist kürzer als eine Sekunde."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const body = new FormData();
      body.append("file", tape.wav(), "diktat.wav"); body.append("priority", priority); body.append("note", note.trim());
      const saved = await request(`/cases/${caseId}/dictations`, { method: "POST", body });
      tape.clear(); setNote(""); setPriority("normal");
      setNotice(`Diktat (${length(saved.duration_ms)}) zur Akte ${saved.reference} ist im Schreibpool.`);
      load(); onSent?.();
    } catch (problem) {
      setError(problem.status === 413 ? "Das Diktat ist zu lang (höchstens etwa 40 Minuten). Bitte in zwei Diktate teilen." : "Senden fehlgeschlagen. Das Diktat bleibt hier erhalten – bitte erneut versuchen.");
    } finally { setBusy(false); }
  };
  const discard = () => { if (window.confirm("Aufnahme verwerfen? Sie kann nicht wiederhergestellt werden.")) { tape.clear(); setNotice(""); } };
  const withdraw = async item => { if (!window.confirm("Dieses Diktat aus dem Pool zurückziehen und löschen?")) return; try { await request(`/dictations/${item.id}`, { method: "DELETE" }); load(); onSent?.(); } catch { setError("Das Diktat wird bereits bearbeitet und kann nicht mehr gelöscht werden."); } };

  return <section className="desk-panel dictation">
    <div className="desk-panel-heading"><div><h2>Diktat aufnehmen</h2><p>Jedes Diktat gehört zu einer Akte und geht nach dem Senden in den Schreibpool.</p></div></div>
    <div className="dictation-meta">
      <label>Akte *<select value={caseId} onChange={event => setCaseId(event.target.value)} disabled={busy}>
        <option value="">— Akte wählen —</option>{active.map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>
      <label>Priorität<select value={priority} onChange={event => setPriority(event.target.value)} disabled={busy}>{Object.entries(PRIORITY).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label className="dictation-note">Hinweis fürs Sekretariat<input maxLength={300} value={note} onChange={event => setNote(event.target.value)} placeholder="z. B. Schriftsatz an das Gericht, 2 Abschriften" disabled={busy} /></label>
    </div>
    <div className="dictation-deck">
      <Transport tape={tape} record />
      <div className="dictation-mode" role="radiogroup" aria-label="Aufnahmemodus">
        {[["overwrite", "Überschreiben"], ["insert", "Einfügen"]].map(([mode, label]) => <label key={mode} className={tape.mode === mode ? "chosen" : ""}><input type="radio" name="dictation-mode" checked={tape.mode === mode} disabled={tape.state === "recording"} onChange={() => tape.setMode(mode)} />{label}</label>)}
        <small>Taste <kbd>Einfg</kbd> wechselt. Überschreiben ersetzt ab der Position, Einfügen schiebt den Rest nach hinten.</small>
      </div>
    </div>
    <p className="dictation-keys"><kbd>F8</kbd> Aufnahme · <kbd>F5</kbd> Wiedergabe/Pause · <kbd>F4</kbd> Stopp · <kbd>F6</kbd>/<kbd>F7</kbd> zurück/vor (halten = schnell) · <kbd>Pos1</kbd>/<kbd>Ende</kbd> Anfang/Ende</p>
    {error && <p className="storage-error" role="alert">{error}</p>}
    {notice && <p className="storage-notice" role="status">{notice}</p>}
    {tape.error && <p className="storage-error" role="alert">{tape.error === "insecure" ? "Aufnahmen gehen nur über https:// oder localhost." : "Kein Mikrofon verfügbar oder der Zugriff wurde abgelehnt. Bitte in den Browser-Einstellungen das Mikrofon für diese Seite erlauben."}</p>}
    {!tape.error && tape.state === "idle" && !tape.length && !notice && <p className="field-help">Beim ersten Start fragt der Browser nach dem Mikrofon.</p>}
    <div className="sample-actions">
      <button className="desk-button solid" disabled={busy || !tape.dirty || tape.state === "recording"} onClick={send}>{busy ? <IconLoader2 size={16} className="la-spin" /> : <IconSend size={16} />}Diktat senden</button>
      <button className="desk-link desk-delete" disabled={busy || !tape.dirty} onClick={discard}><IconTrash size={15} />Verwerfen</button>
    </div>
    {!!mine.length && <><h3 className="dictation-subhead">Meine letzten Diktate</h3><ul className="admin-list dictation-mine">{mine.map(item => <li key={item.id}>
      <strong>{item.reference} · {item.case_title}</strong>
      <small>{stamp(item.created_at)} · {length(item.duration_ms)} · {PRIORITY[item.priority]} · {STATUS[item.status]}{item.assignee_name ? ` · ${item.assignee_name}` : ""}{item.done_at ? ` · erledigt ${stamp(item.done_at)}` : ""}</small>
      {item.status === "open" && <button className="desk-link desk-delete" onClick={() => withdraw(item)}>Zurückziehen</button>}</li>)}</ul></>}
  </section>;
}

// Playback station for the typing pool: precise transport, adjustable speed and a transcript field.
function TranscriptionDesk({ item, me, onDone, onReleased, onClose, openCase }) {
  const tape = useTape(onChange => new DictationTape({ onChange }));
  const [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [autoRewind, setAutoRewind] = useState(1), [text, setText] = useState(""), [doneNote, setDoneNote] = useState(""), [busy, setBusy] = useState(false), [draftSaved, setDraftSaved] = useState("");
  const rewind = useRef(autoRewind); rewind.current = autoRewind;
  const editable = item.status !== "done" && (item.assignee_id === me || item.status === "open");
  useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/api/dictations/${item.id}/audio`, { credentials: "include", headers: { "X-Schimmelpilz-Request": "1" } })
      .then(response => { if (!response.ok) throw new Error(); return response.arrayBuffer(); })
      .then(buffer => { if (!alive) return; const { samples, rate } = decodeWav(buffer); tape.rate = rate; tape.data = samples; tape.length = samples.length; tape.position = 0; tape.emit(); })
      .catch(() => alive && setError("Die Aufnahme konnte nicht geladen werden."))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [item.id, tape]);
  useEffect(() => bindDictationKeys(tape, { autoRewind: () => rewind.current }), [tape]);
  usePosKeys(tape);

  const saveDraft = async () => {
    setBusy(true); setError("");
    try { await request(`/cases/${item.case_id}/drafts`, json("POST", { body: text.trim(), language: "de", kind: "letter", recipient: "" })); setDraftSaved("Als Entwurf im Schriftverkehr der Akte gespeichert."); }
    catch { setError("Entwurf konnte nicht gespeichert werden."); } finally { setBusy(false); }
  };
  const complete = async () => {
    setBusy(true); setError("");
    try { tape.stop(); onDone(await request(`/dictations/${item.id}/complete`, json("POST", { expected_version: item.version, note: doneNote }))); }
    catch (problem) { setError(problem.status === 409 ? "Das Diktat wurde inzwischen geändert. Bitte die Liste neu laden." : "Abschließen fehlgeschlagen."); } finally { setBusy(false); }
  };
  const release = async () => {
    setBusy(true);
    try { tape.stop(); onReleased(await request(`/dictations/${item.id}/release`, json("POST", { expected_version: item.version }))); }
    catch { setError("Freigeben fehlgeschlagen. Bitte die Liste neu laden."); } finally { setBusy(false); }
  };

  return <div className="dictation-desk admin-card">
    <div className="dictation-desk-head"><div><span className="desk-eyebrow">{PRIORITY[item.priority].toUpperCase()} · {STATUS[item.status]}</span>
      <h3><button className="desk-link" onClick={() => openCase(item.case_id)}>{item.reference}</button> · {item.case_title}</h3>
      <p>Diktiert von {item.author_name} am {stamp(item.created_at)} · {length(item.duration_ms)}{item.note ? ` · „${item.note}“` : ""}</p></div>
      <button className="desk-link" onClick={() => { tape.stop(); onClose(); }}>Schließen</button></div>
    {loading ? <p className="la-busy"><IconLoader2 className="la-spin" size={20} />Aufnahme wird geladen …</p> : <>
      <Transport tape={tape} autoRewind={autoRewind} />
      <div className="dictation-settings">
        <label>Geschwindigkeit<select value={tape.speed} onChange={event => tape.setSpeed(Number(event.target.value))}>{[0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.5].map(speed => <option key={speed} value={speed}>{speed.toFixed(1)}×</option>)}</select></label>
        <label>Rücksprung bei Pause<select value={autoRewind} onChange={event => setAutoRewind(Number(event.target.value))}>{[0, 1, 2, 3].map(seconds => <option key={seconds} value={seconds}>{seconds ? `${seconds} s` : "aus"}</option>)}</select></label>
        <p className="dictation-keys"><kbd>F5</kbd> Wiedergabe/Pause · <kbd>F4</kbd> Stopp · <kbd>F6</kbd>/<kbd>F7</kbd> zurück/vor – die Tasten wirken auch beim Schreiben im Textfeld.</p>
      </div>
      {editable && <label className="dictation-text">Abschrift<textarea rows={12} value={text} onChange={event => setText(event.target.value)} placeholder="Hier mitschreiben. Mit „Als Entwurf speichern“ landet der Text im Schriftverkehr der Akte." /></label>}
    </>}
    {error && <p className="storage-error" role="alert">{error}</p>}
    {draftSaved && <p className="storage-notice" role="status"><IconFileText size={16} /> {draftSaved}</p>}
    {item.status === "done" ? <p className="field-help">Erledigt am {stamp(item.done_at)} von {item.done_by_name}{item.done_note ? ` · ${item.done_note}` : ""}.</p>
      : editable && <div className="dictation-finish">
        <button className="desk-button" disabled={busy || text.trim().length < 1} onClick={saveDraft}><IconFileText size={16} />Als Entwurf speichern</button>
        <label>Vermerk (optional)<input maxLength={500} value={doneNote} onChange={event => setDoneNote(event.target.value)} placeholder="z. B. Schriftsatz zur Unterschrift vorgelegt" /></label>
        <button className="desk-button solid" disabled={busy} onClick={complete}><IconCheck size={16} />Als erledigt markieren</button>
        {item.status === "in_progress" && <button className="desk-link" disabled={busy} onClick={release}><IconArrowBackUp size={15} />Zurück in den Pool</button>}
      </div>}
  </div>;
}

// The typing pool: all dictations of the office, filterable by author and status.
export function DictationPool({ open, onChanged }) {
  const [data, setData] = useState({ items: [], authors: [], me: "" });
  const [status, setStatus] = useState("active"), [author, setAuthor] = useState(""), [onlyMine, setOnlyMine] = useState(false);
  const [selected, setSelected] = useState(""), [error, setError] = useState(""), [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    setLoading(true);
    return request(`/dictations?status=${status}${author ? `&author_id=${encodeURIComponent(author)}` : ""}`).then(result => { setData(result); setError(""); }).catch(() => setError("Schreibpool nicht erreichbar.")).finally(() => setLoading(false));
  }, [status, author]);
  useEffect(() => { load(); }, [load]);
  const replace = item => { setData(current => ({ ...current, items: current.items.map(entry => entry.id === item.id ? item : entry) })); onChanged?.(); };
  const take = async item => {
    try { const taken = await request(`/dictations/${item.id}/take`, json("POST", { expected_version: item.version })); replace(taken); setSelected(taken.id); }
    catch { setError("Dieses Diktat hat inzwischen jemand anderes übernommen."); load(); }
  };
  const items = data.items.filter(item => !onlyMine || item.assignee_id === data.me);
  const current = data.items.find(item => item.id === selected);
  const counts = { open: data.items.filter(item => item.status === "open").length, mine: data.items.filter(item => item.status === "in_progress" && item.assignee_id === data.me).length };

  return <section className="desk-panel dictation-pool">
    <div className="desk-panel-heading"><div><h2>Schreibpool</h2><p>{counts.open} offen · {counts.mine} bei mir in Bearbeitung</p></div>
      <button className="desk-link" onClick={load} disabled={loading}>Aktualisieren</button></div>
    <div className="dictation-filters">
      <label>Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="active">Offen &amp; in Bearbeitung</option><option value="open">Nur offen</option><option value="in_progress">In Bearbeitung</option><option value="done">Erledigt</option><option value="all">Alle</option></select></label>
      <label>Diktiert von<select value={author} onChange={event => setAuthor(event.target.value)}><option value="">alle Anwältinnen und Anwälte</option>{data.authors.map(item => <option key={item.author_id} value={item.author_id}>{item.author_name}</option>)}</select></label>
      <label className="dictation-check"><input type="checkbox" checked={onlyMine} onChange={event => setOnlyMine(event.target.checked)} />nur meine</label>
    </div>
    {error && <p className="storage-error" role="alert">{error}</p>}
    {current && <TranscriptionDesk key={current.id} item={current} me={data.me} openCase={id => open(id)} onClose={() => setSelected("")}
      onDone={item => { replace(item); setSelected(""); }} onReleased={item => { replace(item); setSelected(""); }} />}
    {items.length ? <div className="dictation-table-wrap"><table className="dictation-table">
      <thead><tr><th>Priorität</th><th>Akte</th><th>Diktiert von</th><th>Länge</th><th>Eingang</th><th>Status</th><th></th></tr></thead>
      <tbody>{items.map(item => <tr key={item.id} className={`${item.id === selected ? "selected " : ""}priority-${item.priority}`}>
        <td><span className={`dictation-priority ${item.priority}`}>{PRIORITY[item.priority]}</span></td>
        <td><button className="desk-link" onClick={() => open(item.case_id)}>{item.reference}</button><small>{item.case_title}</small>{item.note && <small>„{item.note}“</small>}</td>
        <td>{item.author_name}</td><td>{length(item.duration_ms)}</td><td>{stamp(item.created_at)}</td>
        <td>{STATUS[item.status]}{item.assignee_name && <small>{item.status === "done" ? `${item.done_by_name}, ${stamp(item.done_at)}` : item.assignee_name}</small>}</td>
        <td className="dictation-row-actions">
          {item.status === "open" && <button className="desk-button solid" onClick={() => take(item)}><IconHeadphones size={15} />Diktat übernehmen</button>}
          {item.status === "in_progress" && item.assignee_id === data.me && <button className="desk-button" onClick={() => setSelected(item.id)}><IconHeadphones size={15} />Weiterschreiben</button>}
          {(item.status === "done" || (item.status === "in_progress" && item.assignee_id !== data.me)) && <button className="desk-link" onClick={() => setSelected(item.id)}>Anhören</button>}
        </td></tr>)}</tbody></table></div>
      : !loading && <p className="desk-empty">{status === "done" ? "Noch keine erledigten Diktate." : "Keine offenen Diktate – der Pool ist leer."}</p>}
  </section>;
}
