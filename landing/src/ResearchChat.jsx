import { useEffect, useMemo, useRef, useState } from "react";
import { IconFileText, IconRefresh, IconCircleFilled, IconArrowUp, IconArrowUpRight, IconPaperclip, IconScale, IconLoader2, IconPlus, IconMessage, IconChevronDown } from "@tabler/icons-react";
import figureUrl from "./assets/frau-schimmelpilz.webp";
import "./research-gemini.css";
import { VoiceButton } from "./VoiceInput.jsx";
import { request } from "./useCaseStorage.js";
import { DocumentLinks } from "./ExportLinks.jsx";
import { legalWorkflows } from "./legalWorkflows.js";
import { dateLabel } from "./workbench.js";
import { ResearchDocumentPicker, ResearchSourceList } from "./ResearchSources.jsx";
import {LegalSourcePanel,LegalAnswerSources,CitedAnswer,CaseLawList,CitationCheck,SkillNote,legalLedger} from './LegalSources.jsx';

// crypto.randomUUID only exists on HTTPS/localhost; plain-HTTP LAN access still needs request IDs.
export function requestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function sourceLedger(sources = [], language) {
  if (!sources.length) return "";
  const de = language === "de";
  return `\n\n${de ? "ÜBERGEBENE DOKUMENTSTELLEN – KEINE GEPRÜFTEN RECHTSQUELLEN" : "SUPPLIED DOCUMENT PASSAGES – NOT VERIFIED LEGAL SOURCES"}\n` + sources.map(source => `${source.filename} · ${source.unit_kind === "image" ? (de ? "Bild" : "Image") : source.unit_kind === "page" ? (de ? "PDF-Seite" : "PDF page") : (de ? "DOCX-Abschnitt" : "DOCX section")} ${source.unit_no}\n${de ? "Textstand" : "Text version"}: ${dateLabel(source.reviewed_at, language, true)}\nSHA-256: ${source.text_sha256}`).join("\n\n");
}

export function ResearchChat({ lang, selectedCase, cases = [], onSelectCase, onDraft, onDocuments }) {
  const hasCorrectedSources = run => (run.sources || []).some(source => selectedCase?.documents?.some(document => document.id === source.document_id && document.inbox_reassigned_at));
  const [runs, setRuns] = useState([]), [question, setQuestion] = useState(""), [workflow, setWorkflow] = useState("research");
  const [status, setStatus] = useState(null), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const controller = useRef(null), messagesRef = useRef(null), composerRef = useRef(null);
  // Which drawer above the input is open: "", "docs" or "sources".
  const [panel, setPanel] = useState("");
  const [documentIds, setDocumentIds] = useState([]);
  const [legalIds, setLegalIds] = useState([]), [automatic,setAutomatic] = useState(true);
  // Chats like in Gemini: "" is a new, empty chat; otherwise the thread id of the chosen chat.
  const [activeThread, setActiveThread] = useState(""), [chatsOpen, setChatsOpen] = useState(false);
  const de = lang === "de";
  const threads = useMemo(() => {
    const byId = new Map();
    for (const run of runs) {
      const id = run.thread_id || run.id;
      const entry = byId.get(id) || { id, title: run.question, started: run.created_at, last: run.created_at, count: 0 };
      entry.count += 1; if (run.created_at > entry.last) entry.last = run.created_at;
      byId.set(id, entry);
    }
    return [...byId.values()].sort((a, b) => b.last.localeCompare(a.last));
  }, [runs]);
  const visibleRuns = activeThread ? runs.filter(run => (run.thread_id || run.id) === activeThread) : [];
  const openChat = id => { setActiveThread(id); setChatsOpen(false); setError(""); setPanel(""); };
  const load = async signal => {
    setLoading(true); setError("");
    try {
      const [health, history] = await Promise.all([request("/research/status", { signal }), selectedCase ? request(`/cases/${selectedCase.id}/research`, { signal }) : Promise.resolve([])]);
      if (!signal?.aborted) { setStatus(health); setRuns(history); }
    } catch (failure) { if (failure.name !== "AbortError") setError(de ? "KI-Chat konnte nicht geladen werden. Bitte erneut versuchen." : "Could not load AI chat. Please retry."); }
    finally { if (!signal?.aborted) setLoading(false); }
  };
  useEffect(() => {
    setDocumentIds([]);setLegalIds([]);setActiveThread("");
    const pending = new AbortController(); load(pending.signal);
    return () => { pending.abort(); controller.current?.abort(); };
  }, [selectedCase?.id]);
  useEffect(() => {
    const thread = messagesRef.current;
    const last = thread?.lastElementChild;
    if (last && (visibleRuns.length || busy)) last.scrollIntoView({ block: busy ? "end" : "start", behavior: "smooth" });
  }, [runs, busy, activeThread]);
  useEffect(() => {
    if (!status || status.ready || busy) return;
    const pending = new AbortController();
    const timer = setInterval(() => {
      request("/research/status", { signal: pending.signal }).then(health => {
        if (!pending.signal.aborted) setStatus(health);
      }).catch(() => { /* The existing connection status remains visible. */ });
    }, 15000);
    return () => { clearInterval(timer); pending.abort(); };
  }, [status?.ready, busy]);
  const send = async event => {
    event.preventDefault();
    if (busy || loading || !selectedCase || question.trim().length < 3) return;
    const sentQuestion = question.trim();
    setBusy(true); setError("");
    controller.current = new AbortController();
    try {
      const run = await request(`/cases/${selectedCase.id}/research`, { method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.current.signal, body: JSON.stringify({ request_id: requestId(), question: sentQuestion, language: lang, workflow, document_ids: documentIds, legal_source_ids:legalIds, use_legal_catalogue:automatic && (selectedCase.details.jurisdiction || 'DE') === 'DE', ...(activeThread ? { thread_id: activeThread } : {}) }) });
      setRuns(current => [...current, run]); setActiveThread(run.thread_id || run.id); setQuestion(""); setPanel(""); setStatus(current => ({ ...current, ready: true }));
      if (composerRef.current) composerRef.current.style.height = "auto";
    } catch (failure) {
      if (failure.name === "AbortError") return;
      const message = failure.status === 422 ? (de ? "Prüfen Sie Dokumentauswahl, ausgeschlossene Quellen und Rechtsordnung. Ihre Frage bleibt erhalten." : "Check document selection, excluded sources and jurisdiction. Your question has been retained.") : failure.detail === "ai_quota" ? (de ? "Das Kontingent des KI-Anbieters ist für heute aufgebraucht (kostenloser Tarif). Ihre Frage bleibt erhalten. Abhilfe: bezahlten Tarif beim Anbieter aktivieren oder morgen erneut versuchen." : "The AI provider's quota is used up for today (free tier). Your question has been retained. Enable a paid plan or retry tomorrow.") : failure.status === 429 ? (de ? "Die KI beantwortet gerade eine andere Frage. Bitte kurz warten und erneut senden." : "The AI is answering another question. Wait briefly and retry.") : failure.status === 504 ? (de ? "Die KI-Antwort hat zu lange gedauert. Ihre Frage bleibt erhalten." : "The AI response timed out. Your question has been retained.") : (de ? "Der KI-Dienst ist gerade nicht erreichbar oder nicht eingerichtet. Ihre Frage bleibt erhalten; versuchen Sie es erneut." : "The AI service is unavailable or not configured. Your question has been retained; please retry.");
      setError(message);
      if (failure.status === 503 || failure.status === 504) setStatus(current => ({ ...current, ready: false }));
      // A failed generation remains in the server history and never masquerades as an answer.
      try { setRuns(await request(`/cases/${selectedCase.id}/research`)); } catch { /* Retain the useful error and current chat. */ }
    } finally { setBusy(false); }
  };
  const suggestions = de ? ["Wie ist die Rechtslage – mit Normen und Rechtsprechung?", "Welche Unterlagen fehlen für den nächsten Schritt?", "Strukturiere Sachverhalt und offene Fragen.", "Welche Fristen und Zuständigkeiten muss ich prüfen?"] : ["What is the legal position – with statutes and case law?", "Which documents are missing for the next step?", "Structure the facts and open questions.", "Which deadlines and jurisdiction questions should I check?"];
  const providerNote = status?.provider === "ollama" ? (de ? "Läuft auf einem lokalen KI-Modell dieses Servers." : "Runs on a local AI model on this server.")
    : status?.provider === "openai" ? (de ? `Frage, Aktenangaben und ausgewählte Auszüge gehen zur Beantwortung an ${status.host || "den KI-Anbieter"}.` : `Question, case details and selected excerpts are sent to ${status.host || "the AI provider"}.`)
    : status?.provider === "groq" ? (de ? "Frage, Aktenangaben und ausgewählte Auszüge gehen zur Beantwortung an Groq (USA)." : "Question, case details and selected excerpts are sent to Groq (USA).")
    : (de ? "Frage, Aktenangaben und ausgewählte Auszüge gehen zur Beantwortung an Google (Gemini API)." : "Question, case details and selected excerpts are sent to Google (Gemini API).");
  const statusLabel = loading ? (de ? "Verbinde …" : "Connecting …") : status?.enabled === false ? (de ? "KI pausiert" : "AI paused") : status?.ready ? (de ? "KI bereit" : "AI ready") : (de ? "KI nicht bereit" : "AI not ready");
  const canSend = selectedCase && !busy && !loading && status?.enabled !== false && question.trim().length >= 3;
  const grow = target => { target.style.height = "auto"; target.style.height = `${Math.min(target.scrollHeight, 240)}px`; };
  const keys = event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (canSend) send(event); } };
  const toggle = name => setPanel(current => current === name ? "" : name);
  const draftFromRun = run => onDraft({ research_run_id: run.id, kind: "response", language: run.language, body: `${de ? "KI-ARBEITSPAPIER – NICHT GEPRÜFT" : "AI WORKING PAPER – NOT REVIEWED"}\n${selectedCase.reference}\n\n${run.question}\n\n${run.answer}${sourceLedger(run.sources, run.language)}${legalLedger(run.legal_sources, run.citation_audit, run.language)}` }, selectedCase);

  const chatList = <aside className={`rc-chats ${chatsOpen ? "open" : ""}`} aria-label={de ? "Chats dieser Akte" : "Chats of this case"}>
    <button type="button" className={`rc-newchat ${!activeThread ? "on" : ""}`} onClick={() => openChat("")} disabled={!selectedCase || busy}><IconPlus size={16} />{de ? "Neuer Chat" : "New chat"}</button>
    <button type="button" className="rc-chats-toggle" aria-expanded={chatsOpen} onClick={() => setChatsOpen(!chatsOpen)}>
      <IconMessage size={15} />{de ? `Chats (${threads.length})` : `Chats (${threads.length})`}<IconChevronDown size={15} /></button>
    <div className="rc-chats-list">
      <span className="rc-chats-label">{de ? "Chats in dieser Akte" : "Chats in this case"}</span>
      {threads.length ? threads.map(chat => <button type="button" key={chat.id} className={`rc-chat ${chat.id === activeThread ? "on" : ""}`} onClick={() => openChat(chat.id)} disabled={busy} title={chat.title}>
        <span className="rc-chat-title">{chat.title}</span>
        <small>{dateLabel(chat.last, lang, true)}{chat.count > 1 ? ` · ${chat.count} ${de ? "Fragen" : "questions"}` : ""}</small></button>)
        : <small className="rc-chats-empty">{de ? "Noch keine Chats. Ihre erste Frage startet einen." : "No chats yet. Your first question starts one."}</small>}
    </div>
  </aside>;

  return <div className="rc-shell">{chatList}<section className="rc" aria-label={de ? "KI-Recherche" : "AI research"}>
    <header className="rc-bar">
      <label className="rc-case"><span>{de ? "Akte" : "Case"}</span>
        <select value={selectedCase?.id || ""} onChange={event => onSelectCase?.(event.target.value)} aria-label={de ? "Recherche für Akte" : "Research for case"}>
          <option value="" disabled>{de ? "Akte auswählen …" : "Select a case …"}</option>{cases.map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>
      <span className={`rc-status ${status?.ready ? "ready" : ""}`}><IconCircleFilled size={8} />{statusLabel}</span>
      <button type="button" className="rc-icon" aria-label={de ? "KI-Verbindung prüfen" : "Check AI connection"} onClick={() => load()} disabled={busy || loading}><IconRefresh size={17} /></button>
      {selectedCase && <button type="button" className="rc-pill" onClick={() => onDraft(undefined, selectedCase)}><IconFileText size={15} />{de ? "Neuer Entwurf" : "New draft"}</button>}
    </header>

    <div ref={messagesRef} className="rc-thread" aria-live="polite" aria-busy={busy}>
      {!visibleRuns.length && !busy && <div className="rc-hello">
        <h2><span className="rc-gradient">{de ? "Hallo," : "Hello,"}</span><br />{selectedCase ? (de ? `was möchten Sie zu „${selectedCase.title}“ klären?` : `what would you like to clarify about “${selectedCase.title}”?`) : (de ? "wählen Sie oben eine Akte." : "choose a case above.")}</h2>
        {selectedCase && <div className="rc-cards">{suggestions.map(text => <button type="button" key={text} onClick={() => { setQuestion(text); setTimeout(() => composerRef.current?.focus(), 0); }} disabled={busy}><span>{text}</span><IconArrowUpRight size={16} /></button>)}</div>}
      </div>}
      {visibleRuns.map(run => <div className="rc-turn" key={run.id}>
        <div className="rc-q"><p>{run.question}</p></div>
        <div className="rc-a"><span className="rc-avatar" style={{ backgroundImage: `url(${figureUrl})` }} aria-hidden="true" />
          <div className="rc-a-body">
            <span className="rc-meta">Frau Schimmelpilz · {dateLabel(run.created_at, lang, true)}{run.workflow && run.workflow !== "research" ? ` · ${legalWorkflows[lang].find(item => item.id === run.workflow)?.title || ""}` : ""}</span>
            {run.status === "completed" ? <>
              <CitedAnswer answer={run.answer} sources={run.legal_sources} caseLaw={run.retrieval_report?.case_law || []} />
              <CitationCheck lang={lang} items={run.retrieval_report?.citation_check || []} />
              <LegalAnswerSources lang={lang} sources={[]} audit={run.citation_audit} report={{ ...run.retrieval_report, automatic: false }} />
              {(run.legal_sources?.length > 0 || run.retrieval_report?.case_law?.length > 0 || run.sources?.length > 0 || run.retrieval_report?.skill) && <details className="rc-sources">
                <summary>{de ? "Quellen" : "Sources"}: {[run.legal_sources?.length && `${run.legal_sources.length} ${de ? "Normstellen" : "statute passages"}`, run.retrieval_report?.case_law?.length && `${run.retrieval_report.case_law.length} ${de ? "Urteile" : "decisions"}`, run.sources?.length && `${run.sources.length} ${de ? "Dokumentstellen" : "document passages"}`, run.retrieval_report?.skill && (de ? "Fachanleitung" : "expert guide")].filter(Boolean).join(" · ")}</summary>
                <SkillNote lang={lang} skill={run.retrieval_report?.skill} />
                <CaseLawList lang={lang} items={run.retrieval_report?.case_law || []} />
                <LegalAnswerSources lang={lang} sources={run.legal_sources} audit={{}} report={{}} />
                <ResearchSourceList lang={lang} sources={run.sources} />
              </details>}
              {hasCorrectedSources(run) && <p className="storage-notice">{de ? "Die Zuordnung einer verwendeten Datei wurde berichtigt. Diese Antwort bleibt als historischer Nachweis erhalten und kann nicht neu als Entwurf übernommen werden." : "An underlying document assignment was corrected. This answer remains a historical record and cannot be newly adopted as a draft."}</p>}
              <div className="rc-actions">
                <button type="button" className="rc-pill" disabled={busy || hasCorrectedSources(run)} onClick={() => draftFromRun(run)}><IconFileText size={15} />{de ? "Als Entwurf übernehmen" : "Use as draft"}</button>
                <DocumentLinks path={`/api/cases/${selectedCase.id}/research/${run.id}/answer`} lang={lang} />
                {Boolean(run.truncated) && <small>{de ? "Antwort gekürzt" : "Response truncated"}</small>}
              </div>
            </> : <>
              <p className="research-failed">{run.status === "pending" ? (de ? "Diese Anfrage wurde begonnen. Falls der Server neu gestartet wurde, stellen Sie die Frage bitte erneut." : "This request was started. If the server restarted, please ask again.") : (de ? "Für diese Anfrage konnte keine KI-Antwort gespeichert werden." : "No AI answer could be saved for this request.")}</p>
              <button type="button" className="rc-pill" disabled={busy} onClick={() => { setQuestion(run.question); setWorkflow(run.workflow); }}>{de ? "Frage erneut verwenden" : "Reuse question"}</button>
            </>}
          </div>
        </div>
      </div>)}
      {busy && <div className="rc-a rc-thinking" role="status"><span className="rc-avatar" style={{ backgroundImage: `url(${figureUrl})` }} aria-hidden="true" /><div className="rc-a-body"><span className="rc-meta">Frau Schimmelpilz</span><div className="rc-shimmer"><i /><i /><i /></div><small>{de ? "Ich lese Normen und Rechtsprechung und schreibe die Antwort …" : "Reading statutes and case law and writing the answer …"}</small></div></div>}
    </div>

    <form className="rc-composer" onSubmit={send}>
      {panel === "docs" && <div className="rc-pop"><ResearchDocumentPicker lang={lang} documents={selectedCase?.documents} selected={documentIds} setSelected={setDocumentIds} busy={busy} onDocuments={onDocuments} /></div>}
      {panel === "sources" && <div className="rc-pop"><LegalSourcePanel key={selectedCase?.id || "no-case"} lang={lang} caseId={selectedCase?.id} jurisdiction={selectedCase?.details.jurisdiction} busy={busy} selected={legalIds} setSelected={setLegalIds} automatic={automatic} setAutomatic={setAutomatic} revision={runs.length} /></div>}
      <div className="rc-box">
        <textarea ref={composerRef} rows={1} minLength={3} maxLength={4000} value={question} onChange={event => { setQuestion(event.target.value); grow(event.target); }} onKeyDown={keys} disabled={!selectedCase || busy}
          aria-label={de ? "Ihre Frage zur Akte" : "Your case question"} placeholder={selectedCase ? (de ? "Frage zur Akte stellen …" : "Ask about this case …") : (de ? "Erst oben eine Akte wählen" : "Choose a case first")} />
        <div className="rc-tools">
          <select className="rc-pill" aria-label={de ? "Arbeitsmodus" : "Work mode"} value={workflow} onChange={event => setWorkflow(event.target.value)} disabled={busy}>{legalWorkflows[lang].map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
          <button type="button" className={`rc-pill ${panel === "docs" ? "on" : ""}`} onClick={() => toggle("docs")} disabled={!selectedCase}><IconPaperclip size={15} />{de ? "Dokumente" : "Documents"}{documentIds.length ? ` (${documentIds.length})` : ""}</button>
          <button type="button" className={`rc-pill ${panel === "sources" ? "on" : ""}`} onClick={() => toggle("sources")} disabled={!selectedCase}><IconScale size={15} />{de ? "Rechtsquellen" : "Legal sources"}{legalIds.length ? ` (${legalIds.length})` : automatic ? (de ? " · automatisch" : " · automatic") : ""}</button>
          {status?.speech && <VoiceButton lang={lang} className="rc-voice" disabled={!selectedCase || busy} onError={setError}
            onText={text => { setError(""); setQuestion(current => (current.trim() ? current.trimEnd() + " " : "") + text); setTimeout(() => { if (composerRef.current) { grow(composerRef.current); composerRef.current.focus(); } }, 0); }} />}
          <button type="submit" className="rc-send" disabled={!canSend} aria-label={de ? "Frage senden" : "Send question"}>{busy ? <IconLoader2 size={20} className="la-spin" /> : <IconArrowUp size={20} />}</button>
        </div>
      </div>
      {workflow === "comparison" && documentIds.length < 2 && <p className="storage-notice">{de ? "Für die Gegenüberstellung unter „Dokumente“ mindestens zwei Schriftsätze auswählen, z. B. Klage und Klageerwiderung (Text muss geprüft sein)." : "For a comparison, select at least two submissions under “Documents”, e.g. claim and defence (text must be reviewed)."}</p>}
      {error && <p className="storage-error" role="alert">{error}</p>}
      <p className="rc-note">{de ? "Frau Schimmelpilz kann Fehler machen – Antworten sind Arbeitshilfen, rechtlich nicht geprüft. Zitate werden automatisch geprüft. " : "Ms Schimmelpilz can make mistakes – answers are working aids, not legal review. Citations are checked automatically. "}{providerNote} {status?.speech ? (de ? "Spracheingaben gehen zur Umwandlung in Text an Groq und werden nicht gespeichert. " : "Voice input is sent to Groq for transcription and not stored. ") : ""}{de ? "Verlauf wird in der Akte gespeichert." : "History is stored with the case."}</p>
    </form>
  </section></div>;
}
