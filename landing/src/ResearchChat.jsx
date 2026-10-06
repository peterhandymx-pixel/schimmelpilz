import { useEffect, useRef, useState } from "react";
import { IconMessageChatbot, IconSend, IconFileText, IconRefresh, IconCircleFilled } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { legalWorkflows } from "./legalWorkflows.js";
import { dateLabel } from "./workbench.js";
import { ResearchDocumentPicker, ResearchSourceList } from "./ResearchSources.jsx";
import {LegalSourcePanel,LegalAnswerSources,CitedAnswer,legalLedger} from './LegalSources.jsx';

function sourceLedger(sources = [], language) {
  if (!sources.length) return "";
  const de = language === "de";
  return `\n\n${de ? "ÜBERGEBENE DOKUMENTSTELLEN – KEINE GEPRÜFTEN RECHTSQUELLEN" : "SUPPLIED DOCUMENT PASSAGES – NOT VERIFIED LEGAL SOURCES"}\n` + sources.map(source => `${source.filename} · ${source.unit_kind === "page" ? (de ? "PDF-Seite" : "PDF page") : (de ? "DOCX-Abschnitt" : "DOCX section")} ${source.unit_no}\n${de ? "Textstand" : "Text version"}: ${source.reviewed_at}\nSHA-256: ${source.text_sha256}`).join("\n\n");
}

export function ResearchChat({ lang, selectedCase, onDraft, onDocuments }) {
  const [runs, setRuns] = useState([]), [question, setQuestion] = useState(""), [workflow, setWorkflow] = useState("research");
  const [status, setStatus] = useState(null), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const controller = useRef(null), messagesRef = useRef(null);
  const [documentIds, setDocumentIds] = useState([]);
  const [legalIds, setLegalIds] = useState([]), [automatic,setAutomatic] = useState(true);
  const de = lang === "de";
  const load = async signal => {
    setLoading(true); setError("");
    try {
      const [health, history] = await Promise.all([request("/research/status", { signal }), selectedCase ? request(`/cases/${selectedCase.id}/research`, { signal }) : Promise.resolve([])]);
      if (!signal?.aborted) { setStatus(health); setRuns(history); }
    } catch (failure) { if (failure.name !== "AbortError") setError(de ? "KI-Chat konnte nicht geladen werden. Bitte erneut versuchen." : "Could not load AI chat. Please retry."); }
    finally { if (!signal?.aborted) setLoading(false); }
  };
  useEffect(() => {
    setDocumentIds([]);setLegalIds([]);
    const pending = new AbortController(); load(pending.signal);
    return () => { pending.abort(); controller.current?.abort(); };
  }, [selectedCase?.id]);
  useEffect(() => {
    const panel = messagesRef.current;
    if (panel) panel.scrollTop = panel.scrollHeight;
  }, [runs, busy]);
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
      const run = await request(`/cases/${selectedCase.id}/research`, { method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.current.signal, body: JSON.stringify({ request_id: crypto.randomUUID(), question: sentQuestion, language: lang, workflow, document_ids: documentIds, legal_source_ids:legalIds, use_legal_catalogue:automatic && (selectedCase.details.jurisdiction || 'DE') === 'DE' }) });
      setRuns(current => [...current, run]); setQuestion(""); setStatus(current => ({ ...current, ready: true }));
    } catch (failure) {
      if (failure.name === "AbortError") return;
      const message = failure.status === 422 ? (de ? "Prüfen Sie Dokumentauswahl, ausgeschlossene Quellen und Rechtsordnung. Ihre Frage bleibt erhalten." : "Check document selection, excluded sources and jurisdiction. Your question has been retained.") : failure.status === 429 ? (de ? "Die lokale KI arbeitet gerade. Bitte kurz warten und erneut senden." : "The local AI is busy. Wait briefly and retry.") : failure.status === 504 ? (de ? "Die KI-Antwort hat zu lange gedauert. Ihre Frage bleibt erhalten." : "The AI response timed out. Your question has been retained.") : (de ? "Die lokale KI ist gerade nicht erreichbar oder das Modell fehlt. Ihre Frage bleibt erhalten; versuchen Sie es erneut." : "Local AI is unavailable or its model is missing. Your question has been retained; please retry.");
      setError(message);
      if (failure.status === 503 || failure.status === 504) setStatus(current => ({ ...current, ready: false }));
      // A failed generation remains in the server history and never masquerades as an answer.
      try { setRuns(await request(`/cases/${selectedCase.id}/research`)); } catch { /* Retain the useful error and current chat. */ }
    } finally { setBusy(false); }
  };
  const suggestions = de ? ["Welche Unterlagen fehlen für den nächsten Schritt?", "Strukturiere den Sachverhalt und die offenen Fragen.", "Welche Zuständigkeitsfragen muss ich prüfen?"] : ["Which documents are missing for the next step?", "Structure the facts and unresolved questions.", "Which jurisdiction questions should I check?"];
  return <section className="research-chat" aria-label={de ? "KI-Recherche-Assistent" : "AI research assistant"}><header className="research-chat-header"><span className="research-chat-avatar"><IconMessageChatbot size={22} /></span><div><h2>{de ? "Ihr KI-Recherche-Assistent" : "Your AI research assistant"}</h2><p>{selectedCase ? `${selectedCase.reference} · ${selectedCase.title}` : (de ? "Wählen Sie eine Akte für den Chat." : "Select a case to start chatting.")}</p></div><span className={`research-connection ${status?.ready ? "ready" : ""}`}><IconCircleFilled size={7} />{loading ? (de ? "Verbinde …" : "Connecting …") : status?.ready ? (de ? "Lokale KI bereit" : "Local AI ready") : (de ? "KI nicht bereit" : "AI not ready")}</span><button className="desk-link" aria-label={de ? "KI-Verbindung prüfen" : "Check AI connection"} onClick={() => load()} disabled={busy || loading}><IconRefresh size={16} /></button></header>
    <div className="research-chat-scope"><strong>{de ? "Aktenbezogene Orientierung & Entwürfe" : "Case-based orientation & drafts"}</strong><span>{de ? "Der Bot nutzt Aktenangaben, geprüfte Dokumentstellen und ausgewählte oder lokal gefundene Originalquellen. Quellenherkunft und Verweise werden technisch geprüft; rechtliche Aussagen benötigen weiterhin Prüfung." : "The bot uses case particulars, reviewed document passages and selected or locally matched primary sources. Source origin and references are checked technically; legal statements still require review."}</span></div>
    <div ref={messagesRef} className="research-messages" aria-live="polite" aria-busy={busy}>{!runs.length && <div className="research-chat-welcome"><IconMessageChatbot size={31} stroke={1.4} /><h3>{de ? "Was möchten Sie zu Ihrer Akte klären?" : "What would you like to clarify about your case?"}</h3><p>{de ? "Fragen stellen, Sachverhalte strukturieren und den nächsten Arbeitsschritt vorbereiten." : "Ask questions, structure the facts and prepare your next step."}</p><div className="research-suggestions">{suggestions.map(text => <button key={text} onClick={() => setQuestion(text)} disabled={!selectedCase || busy}>{text}</button>)}</div></div>}{runs.map(run => <div className="research-chat-turn" key={run.id}><article className="research-user-message"><span>{de ? "Sie" : "You"}</span><p>{run.question}</p></article><article className="research-assistant-message"><span className="research-message-author"><IconMessageChatbot size={17} />Schimmelpilz <small>{dateLabel(run.created_at, lang, true)}</small></span>{run.status === "completed" ? <><CitedAnswer answer={run.answer} sources={run.legal_sources} /><LegalAnswerSources lang={lang} sources={run.legal_sources} audit={run.citation_audit} report={run.retrieval_report} /><ResearchSourceList lang={lang} sources={run.sources} /><div className="research-answer-actions"><small>{de ? "KI-Antwort · rechtlich nicht geprüft" : "AI response · not legally reviewed"}{Boolean(run.truncated) && (de ? " · Antwort gekürzt" : " · Response truncated")}</small><button className="desk-link" disabled={busy} onClick={() => onDraft({ kind: "response", language: run.language, body: `${de ? "KI-ARBEITSPAPIER – NICHT GEPRÜFT" : "AI WORKING PAPER – NOT REVIEWED"}\n${selectedCase.reference}\n\n${run.question}\n\n${run.answer}${sourceLedger(run.sources, run.language)}${legalLedger(run.legal_sources,run.citation_audit,run.language)}` }, selectedCase)}><IconFileText size={14} />{de ? "Als Entwurf übernehmen" : "Use as draft"}</button></div></> : <><p className="research-failed">{run.status === "pending" ? (de ? "Diese Anfrage wurde begonnen. Falls der Server neu gestartet wurde, stellen Sie die Frage bitte erneut." : "This request was started. If the server restarted, please ask again.") : (de ? "Für diese Anfrage konnte keine KI-Antwort gespeichert werden." : "No AI answer could be saved for this request.")}</p><button type="button" className="desk-link" disabled={busy} onClick={() => { setQuestion(run.question); setWorkflow(run.workflow); }}>{de ? "Frage erneut verwenden" : "Reuse question"}</button></>}</article></div>)}{busy && <p className="research-thinking" role="status">{de ? "Schimmelpilz bearbeitet Ihre Frage …" : "Schimmelpilz is working on your question …"}</p>}</div>
    <LegalSourcePanel key={selectedCase?.id || 'no-case'} lang={lang} caseId={selectedCase?.id} jurisdiction={selectedCase?.details.jurisdiction} busy={busy} selected={legalIds} setSelected={setLegalIds} automatic={automatic} setAutomatic={setAutomatic} revision={runs.length} /><form className="research-composer" onSubmit={send}><ResearchDocumentPicker lang={lang} documents={selectedCase?.documents} selected={documentIds} setSelected={setDocumentIds} busy={busy} onDocuments={onDocuments} /><label className="research-workflow-select">{de ? "Arbeitsmodus" : "Work mode"}<select aria-label={de ? "Arbeitsmodus" : "Work mode"} value={workflow} onChange={event => setWorkflow(event.target.value)} disabled={busy}>{legalWorkflows[lang].map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label className="research-question">{de ? "Ihre Frage zur Akte" : "Your case question"}<textarea rows={3} minLength={3} maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)} disabled={!selectedCase || busy} placeholder={de ? "Beschreiben Sie Ihre Frage oder den gewünschten nächsten Schritt …" : "Describe your question or the next step you want to prepare …"} /></label><div className="research-composer-actions"><small>{de ? "Antworten und Verlauf werden in Ihrer Akte gespeichert." : "Answers and history are stored with your case."}</small><button className="desk-button solid" type="submit" disabled={!selectedCase || busy || loading || question.trim().length < 3}><IconSend size={17} />{busy ? (de ? "Wird bearbeitet …" : "Working …") : (de ? "Frage senden" : "Send question")}</button></div>{error && <p className="storage-error" role="alert">{error}</p>}</form>
  </section>;
}
