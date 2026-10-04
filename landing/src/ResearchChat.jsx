import { useEffect, useRef, useState } from "react";
import { IconMessageChatbot, IconSend, IconFileText, IconRefresh, IconCircleFilled } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";
import { legalWorkflows } from "./legalWorkflows.js";
import { dateLabel } from "./workbench.js";

export function ResearchChat({ lang, selectedCase, onDraft }) {
  const [runs, setRuns] = useState([]), [question, setQuestion] = useState(""), [workflow, setWorkflow] = useState("research");
  const [status, setStatus] = useState(null), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const controller = useRef(null), messagesRef = useRef(null);
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
    const pending = new AbortController(); load(pending.signal);
    return () => { pending.abort(); controller.current?.abort(); };
  }, [selectedCase?.id]);
  useEffect(() => {
    const panel = messagesRef.current;
    if (panel) panel.scrollTop = panel.scrollHeight;
  }, [runs, busy]);
  const send = async event => {
    event.preventDefault();
    if (busy || loading || !selectedCase || question.trim().length < 3) return;
    const sentQuestion = question.trim();
    setBusy(true); setError("");
    controller.current = new AbortController();
    try {
      const run = await request(`/cases/${selectedCase.id}/research`, { method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.current.signal, body: JSON.stringify({ request_id: crypto.randomUUID(), question: sentQuestion, language: lang, workflow }) });
      setRuns(current => [...current, run]); setQuestion(""); setStatus(current => ({ ...current, ready: true }));
    } catch (failure) {
      if (failure.name === "AbortError") return;
      const message = failure.status === 429 ? (de ? "Die lokale KI arbeitet gerade. Bitte kurz warten und erneut senden." : "The local AI is busy. Wait briefly and retry.") : failure.status === 504 ? (de ? "Die KI-Antwort hat zu lange gedauert. Ihre Frage bleibt erhalten." : "The AI response timed out. Your question has been retained.") : (de ? "Die lokale KI ist gerade nicht erreichbar oder das Modell fehlt. Ihre Frage bleibt erhalten; versuchen Sie es erneut." : "Local AI is unavailable or its model is missing. Your question has been retained; please retry.");
      setError(message);
      // A failed generation remains in the server history and never masquerades as an answer.
      try { setRuns(await request(`/cases/${selectedCase.id}/research`)); } catch { /* Retain the useful error and current chat. */ }
    } finally { setBusy(false); }
  };
  const suggestions = de ? ["Welche Unterlagen fehlen für den nächsten Schritt?", "Strukturiere den Sachverhalt und die offenen Fragen.", "Welche Zuständigkeitsfragen muss ich prüfen?"] : ["Which documents are missing for the next step?", "Structure the facts and unresolved questions.", "Which jurisdiction questions should I check?"];
  return <section className="research-chat" aria-label={de ? "KI-Recherche-Assistent" : "AI research assistant"}><header className="research-chat-header"><span className="research-chat-avatar"><IconMessageChatbot size={22} /></span><div><h2>{de ? "Ihr KI-Recherche-Assistent" : "Your AI research assistant"}</h2><p>{selectedCase ? `${selectedCase.reference} · ${selectedCase.title}` : (de ? "Wählen Sie eine Akte für den Chat." : "Select a case to start chatting.")}</p></div><span className={`research-connection ${status?.ready ? "ready" : ""}`}><IconCircleFilled size={7} />{loading ? (de ? "Verbinde …" : "Connecting …") : status?.ready ? (de ? "Lokale KI bereit" : "Local AI ready") : (de ? "KI nicht bereit" : "AI not ready")}</span><button className="desk-link" aria-label={de ? "KI-Verbindung prüfen" : "Check AI connection"} onClick={() => load()} disabled={busy || loading}><IconRefresh size={16} /></button></header>
    <div className="research-chat-scope"><strong>{de ? "Aktenbezogene Orientierung & Entwürfe" : "Case-based orientation & drafts"}</strong><span>{de ? "Der Bot nutzt Stammdaten und Chatverlauf. Dateien werden noch nicht ausgelesen; Internetquellen werden nicht automatisch geprüft." : "The bot uses particulars and chat history. Files are not yet extracted; internet sources are not automatically verified."}</span></div>
    <div ref={messagesRef} className="research-messages" aria-live="polite" aria-busy={busy}>{!runs.length && <div className="research-chat-welcome"><IconMessageChatbot size={31} stroke={1.4} /><h3>{de ? "Was möchten Sie zu Ihrer Akte klären?" : "What would you like to clarify about your case?"}</h3><p>{de ? "Fragen stellen, Sachverhalte strukturieren und den nächsten Arbeitsschritt vorbereiten." : "Ask questions, structure the facts and prepare your next step."}</p><div className="research-suggestions">{suggestions.map(text => <button key={text} onClick={() => setQuestion(text)} disabled={!selectedCase || busy}>{text}</button>)}</div></div>}{runs.map(run => <div className="research-chat-turn" key={run.id}><article className="research-user-message"><span>{de ? "Sie" : "You"}</span><p>{run.question}</p></article><article className="research-assistant-message"><span className="research-message-author"><IconMessageChatbot size={17} />Schimmelpilz <small>{dateLabel(run.created_at, lang, true)}</small></span>{run.status === "completed" ? <><p>{run.answer}</p><div className="research-answer-actions"><small>{de ? "KI-Antwort · rechtlich nicht geprüft" : "AI response · not legally reviewed"}{Boolean(run.truncated) && (de ? " · Antwort gekürzt" : " · Response truncated")}</small><button className="desk-link" disabled={busy} onClick={() => onDraft({ kind: "response", language: run.language, body: `${de ? "KI-ARBEITSPAPIER – NICHT GEPRÜFT" : "AI WORKING PAPER – NOT REVIEWED"}\n${selectedCase.reference}\n\n${run.question}\n\n${run.answer}` }, selectedCase)}><IconFileText size={14} />{de ? "Als Entwurf übernehmen" : "Use as draft"}</button></div></> : <p className="research-failed">{run.status === "pending" ? (de ? "Diese Anfrage wurde begonnen. Falls der Server neu gestartet wurde, stellen Sie die Frage bitte erneut." : "This request was started. If the server restarted, please ask again.") : (de ? "Für diese Anfrage konnte keine KI-Antwort gespeichert werden." : "No AI answer could be saved for this request.")}</p>}</article></div>)}{busy && <p className="research-thinking" role="status">{de ? "Schimmelpilz bearbeitet Ihre Frage …" : "Schimmelpilz is working on your question …"}</p>}</div>
    <form className="research-composer" onSubmit={send}><label className="research-workflow-select">{de ? "Arbeitsmodus" : "Work mode"}<select aria-label={de ? "Arbeitsmodus" : "Work mode"} value={workflow} onChange={event => setWorkflow(event.target.value)} disabled={busy}>{legalWorkflows[lang].map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label className="research-question">{de ? "Ihre Frage zur Akte" : "Your case question"}<textarea rows={3} minLength={3} maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)} disabled={!selectedCase || busy} placeholder={de ? "Beschreiben Sie Ihre Frage oder den gewünschten nächsten Schritt …" : "Describe your question or the next step you want to prepare …"} /></label><div className="research-composer-actions"><small>{de ? "Antworten und Verlauf werden in Ihrer Akte gespeichert." : "Answers and history are stored with your case."}</small><button className="desk-button solid" type="submit" disabled={!selectedCase || busy || loading || question.trim().length < 3}><IconSend size={17} />{busy ? (de ? "Wird bearbeitet …" : "Working …") : (de ? "Frage senden" : "Send question")}</button></div>{error && <p className="storage-error" role="alert">{error}</p>}</form>
  </section>;
}
