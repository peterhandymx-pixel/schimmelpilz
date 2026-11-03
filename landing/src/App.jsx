// @refresh reset
import { useEffect, useId, useRef, useState } from "react";
import { CaseIntake, intakeCopy } from "./CaseIntake.jsx";
import { FeatureOverview } from "./FeatureOverview.jsx";
import { PricingOverview } from './PricingOverview.jsx';
import { documentTemplate, draftCopy } from "./draftTemplates.js";
import { useCaseStorage, readPreference, writePreference } from "./useCaseStorage.js";
import { AuthForm, authCopy } from "./AuthForm.jsx";
import { DraftPdfPreview } from './DraftPdfPreview.jsx';
import { DraftReview } from './DraftReview.jsx';
import { DraftSend } from './DraftSend.jsx';
import { Dashboard } from "./Dashboard.jsx";
import { useContacts } from './useContacts.js';
import { ContactRecipient } from './ContactBook.jsx';
import { useAuth, authRequest } from "./useAuth.js";
import { BrandLogo } from "./BrandLogo.jsx";
import { LegalLinks, LegalPage, legalPageFromHash } from "./LegalPages.jsx";
import {
  IconArrowRight as ArrowRight, IconCheck as Check, IconChevronDown as ChevronDown, IconFileText as FileText,
  IconMenu2 as Menu, IconEdit as PenLine, IconUpload as Upload, IconX as X,
} from "@tabler/icons-react";

const copy = {
  de: {
    navHow: "So funktioniert’s", navFeatures: "Funktionen", navPricing: "Preise", navFaq: "FAQ", signIn: "Anmelden", register: "Registrieren",
    eyebrow: "IHR FALL. KLAR STRUKTURIERT.",
    testedIn: "Getestet und verbessert in Verfahren beim",
    title: <>Findet Klarheit und die Wahrheit</>,
    intro: "Ordnen Sie Ihre Unterlagen, verstehen Sie rechtliche Zusammenhänge und erstellen Sie Dokumententwürfe – auf Deutsch oder Englisch.",
    start: "Fall anlegen", demo: "Demo ansehen", meta: "Deutsch & Englisch  ·  Aktenzeichen  ·  Dokumententwürfe",
    badge: "Beispielfall", overview: "Übersicht", documents: "Dokumente", assistant: "Assistent", drafts: "Entwürfe",
    caseTitle: "Mietangelegenheit – Wohnung Berlin", inProgress: "In Bearbeitung", files: "Unterlagen", add: "Unterlagen hinzufügen",
    draft: "Schreiben vorbereiten", draftLabel: "Entwurf", missing: "Welche Unterlagen fehlen noch?", ask: "Frage zu Ihrem Fall …",
    stepsTitle: "In drei Schritten zum nächsten Schritt.", steps: [
      ["Fall beschreiben", "Schildern Sie kurz Ihr Anliegen und die wichtigsten Eckdaten."],
      ["Unterlagen hinzufügen", "Laden Sie relevante Dokumente sicher und übersichtlich hoch."],
      ["Entwurf vorbereiten", "Erhalten Sie verständliche Analysen und erstellen Sie Dokumententwürfe."],
    ],
    faqTitle: "Klarheit, bevor Sie starten.", faq: [["Ersetzt die Assistenz eine Rechtsberatung?", "Nein. Die Vorschläge dienen der Orientierung und ersetzen keine individuelle Beratung durch eine zugelassene Rechtsanwältin oder einen Rechtsanwalt."], ["Wo werden meine Unterlagen verarbeitet?", "Akten, Entwürfe und Dateien werden auf unserem Server gespeichert. Für eine KI-Recherche werden Ihre Frage, die Aktenangaben und die von Ihnen ausgewählten Dokumentauszüge an Google (Gemini API) übermittelt. Einzelheiten stehen in der Datenschutzerklärung."], ["Kann ich auf Deutsch und Englisch arbeiten?", "Ja. Wechseln Sie die Sprache oben rechts; Aktenzeichen, Dokumente und Entwürfe bleiben dabei im selben Fall zusammen." ]],
    modalStart: "Neuen Fall anlegen", modalIntro: "Geben Sie die wichtigsten Eckdaten ein. Diese Vorschau speichert Ihre Eingaben nur im Browser.", subject: "Betreff", description: "Kurzbeschreibung", create: "Fall erstellen", cancel: "Abbrechen", close: "Schließen",
    loginTitle: "Anmelden", loginText: "Die Anmeldung wird in der Produktionsversion mit Ihrer eigenen Authentifizierung verbunden.", preview: "Vorschau öffnen", saved: "Fall angelegt – Vorschau aktualisiert.", uploadSaved: "Datei auf dem Server gespeichert.", error: "Der Fall konnte nicht gespeichert werden. Läuft das Backend auf Port 8001?", uploadError: "Die Datei konnte nicht gespeichert werden.", noCase: "Legen Sie zuerst einen Fall an.", limit: "Demo: keine Rechtsberatung, keine echte Dokumentenspeicherung.",
  },
  en: {
    navHow: "How it works", navFeatures: "Features", navPricing: "Pricing", navFaq: "FAQ", signIn: "Sign in", register: "Register", eyebrow: "YOUR CASE. CLEARLY STRUCTURED.", testedIn: "Tested and refined in proceedings at",
    title: <>Clarity for your case.<br />Structure for the<br />next step.</>, intro: "Organise your documents, understand the legal context and prepare document drafts – in German or English.", start: "Start a case", demo: "View demo", meta: "German & English  ·  Case reference  ·  Document drafts",
    badge: "Example case", overview: "Overview", documents: "Documents", assistant: "Assistant", drafts: "Drafts", caseTitle: "Tenancy matter – Berlin flat", inProgress: "In progress", files: "Documents", add: "Add documents", draft: "Prepare a letter", draftLabel: "Draft", missing: "Which documents are still missing?", ask: "Ask about your case …", stepsTitle: "Three steps to your next step.",
    steps: [["Describe your case", "Briefly share your concern and the key facts."], ["Add documents", "Upload relevant documents securely and clearly."], ["Prepare a draft", "Receive understandable analysis and prepare document drafts."]], faqTitle: "Clarity before you start.", faq: [["Does the assistant replace legal advice?", "No. Suggestions are for orientation and do not replace individual advice from a qualified lawyer."], ["Where are my documents processed?", "Cases, drafts and files are stored on our server. For AI research, your question, the case particulars and the document excerpts you select are sent to Google (Gemini API). See the privacy notice for details."], ["Can I work in German and English?", "Yes. Switch language above; your reference, documents and drafts stay together in one case."]], modalStart: "Start a new case", modalIntro: "Share the key facts. This preview keeps your input in the browser only.", subject: "Subject", description: "Short description", create: "Create case", cancel: "Cancel", close: "Close", loginTitle: "Sign in", loginText: "Production will connect sign-in to your own authentication system.", preview: "Open preview", saved: "Case created – preview updated.", uploadSaved: "File saved on the server.", error: "The case could not be saved. Is the API running on port 8001?", uploadError: "The file could not be saved.", noCase: "Create a case first.", limit: "Demo: no legal advice and no real document storage.",
  },
};

const storageCopy = {
  de: {
    savedCases: "Gespeicherte Fälle", savedCase: "Gespeichert", localStorage: "Lokal gespeichert",
    loadingCases: "Fälle werden geladen …", loadError: "Gespeicherte Fälle konnten nicht geladen werden.", retry: "Erneut versuchen",
    noDocuments: "Noch keine Unterlagen. Bis zu 10 MB pro Datei.", noDrafts: "Noch keine Entwürfe gespeichert.",
    uploading: "Wird hochgeladen …", newDraft: "Neuer Entwurf", editDraft: "Entwurf bearbeiten", save: "Speichern",
    draftSaved: "Entwurf gespeichert.", draftError: "Entwurf konnte nicht gespeichert werden. Ihr Text bleibt im Editor.",
    uploadSaved: "Datei(en) gespeichert.", uploadError: "Upload fehlgeschlagen", error: "Speichern fehlgeschlagen. Bitte versuchen Sie es erneut.",
    modalIntro: "Akten und Unterlagen werden dauerhaft auf dem Server gespeichert.",
    saved: "Fall gespeichert.", limit: "Keine Rechtsberatung · Ergebnisse vor Verwendung prüfen.",
    downloadDraft: "Als Text herunterladen", draftBody: "Text des Entwurfs", oversized: "Datei überschreitet 10 MB", unsupported: "Dateityp nicht unterstützt",
  },
  en: {
    savedCases: "Saved cases", savedCase: "Saved", localStorage: "Stored locally",
    title: <>Find clarity and the truth</>,
    loadingCases: "Loading cases …", loadError: "Saved cases could not be loaded.", retry: "Try again",
    noDocuments: "No documents yet. Up to 10 MB per file.", noDrafts: "No drafts saved yet.",
    uploading: "Uploading …", newDraft: "New draft", editDraft: "Edit draft", save: "Save",
    draftSaved: "Draft saved.", draftError: "Could not save the draft. Your text stays in the editor.",
    uploadSaved: "file(s) saved.", uploadError: "Upload failed", error: "Could not save. Please try again.",
    modalIntro: "Cases and documents are stored persistently on the server.",
    saved: "Case saved.", limit: "No legal advice · Review results before use.",
    downloadDraft: "Download as text", draftBody: "Draft text", oversized: "File exceeds 10 MB", unsupported: "File type not supported",
  },
};

// Desk sections and sign-in dialogs the mobile app opens directly with ?open=<id>.
const OPEN_VIEWS = ["inbox", "parties", "cases", "documents", "drafts", "tasks", "costs", "routes", "research", "services", "team", "billing", "account"];
const OPEN_CASE_TABS = ["overview", "parties", "documents", "drafts", "tasks", "routes", "costs", "activity"];
const OPEN_AUTH = ["login", "register", "forgot"];

// Links from account emails (?reset=<token> / ?verify=<token>) and the mobile app (?open=<id>), read once per page load and removed from the address bar.
const emailLink = (() => {
  const params = new URLSearchParams(window.location.search);
  const open = params.get("open");
  const link = { reset: params.get("reset"), verify: params.get("verify"), verifyStarted: false,
    view: OPEN_VIEWS.includes(open) ? open : null, auth: OPEN_AUTH.includes(open) ? open : null,
    // ?open=case&case=<id>&tab=<tab>: one case file at a given tab (e.g. drafts or costs).
    caseId: open === "case" ? params.get("case") : null, caseTab: OPEN_CASE_TABS.includes(params.get("tab")) ? params.get("tab") : "overview" };
  if (link.reset || link.verify || open) {
    params.delete("reset"); params.delete("verify"); params.delete("open"); params.delete("case"); params.delete("tab");
    window.history.replaceState(null, "", window.location.pathname + (params.toString() ? `?${params}` : "") + window.location.hash);
  }
  return link;
})();

function Brand() { return <BrandLogo />; }

// Courts in whose proceedings the assistant was used and improved (names stay German in both languages).
const COURTS = ["Arbeitsgericht München", "Arbeitsgericht Offenbach", "Sozialgericht Köln", "Landessozialgericht NRW", "Landgericht München I", "Amtsgericht Wedding"];

function Dialog({ open, onClose, title, children, className = "", busy = false }) {
  const ref = useRef(null);
  const titleId = useId();
  useEffect(() => { const el = ref.current; if (!el) return; if (open && !el.open) el.showModal(); if (!open && el.open) el.close(); }, [open]);
  return <dialog ref={ref} aria-labelledby={titleId} className={`dialog ${className}`} onClose={onClose} onCancel={event => { if (busy) event.preventDefault(); else onClose(); }}><div className="dialog-card"><button className="dialog-close" disabled={busy} onClick={onClose} aria-label="Schließen / Close"><X size={18} /></button><div className="dialog-kicker">VIRTUELLE RECHTSASSISTENZ</div><h2 id={titleId}>{title}</h2>{children}</div></dialog>;
}


export function App() {
  const [lang, setLang] = useState(() => readPreference("schimmelpilz.language") === "en" ? "en" : "de");
  const t = { ...copy[lang], ...storageCopy[lang] };
  const auth = useAuth();
  const storage = useCaseStorage(Boolean(auth.user));
  const contacts = useContacts(auth.user?.id);
  const [view, setView] = useState(emailLink.view || "overview");
  const [authMode, setAuthMode] = useState("login");
  const [modal, setModal] = useState(null);
  const [registrationAudience, setRegistrationAudience] = useState('consumer');
  const [editingCase, setEditingCase] = useState(null);
  const [intakeSession, setIntakeSession] = useState(0);
  const [activeTab, setActiveTab] = useState("overview");
  const [menu, setMenu] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [toast, setToast] = useState("");
  const [savingCase, setSavingCase] = useState(false);
  const [caseError, setCaseError] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftId, setDraftId] = useState(null);
  const [savedDraft,setSavedDraft] = useState(null);
  const [draftResearchId,setDraftResearchId] = useState(null);
  const [draftLanguage, setDraftLanguage] = useState(lang);
  const [draftKind, setDraftKind] = useState("letter");
  const [draftRecipient, setDraftRecipient] = useState("");
  const [draftError, setDraftError] = useState("");
  const [useCurrentLetterhead, setUseCurrentLetterhead] = useState(true);
  const [uploadNotice, setUploadNotice] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [authNotice, setAuthNotice] = useState("");
  const [legalPage, setLegalPage] = useState(() => legalPageFromHash());
  const fileRef = useRef(null);
  const toastTimer = useRef(null);
  const generatedDraft = useRef(null);
  const dc = draftCopy[lang];
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = "Rechtsassistentin Schimmelpilz";
    writePreference("schimmelpilz.language", lang);
  }, [lang]);
  useEffect(() => () => window.clearTimeout(toastTimer.current), []);
  useEffect(() => {
    // Impressum, privacy notice and terms are reachable as #impressum, #datenschutz and #agb, signed in or not.
    const follow = () => setLegalPage(legalPageFromHash());
    window.addEventListener("hashchange", follow);
    return () => window.removeEventListener("hashchange", follow);
  }, []);
  useEffect(() => {
    if (!auth.user) { setModal(null); setDraftBody(""); setDraftId(null); setQuestion(""); setAnswer(""); }
  }, [auth.user?.id]);
  const showToast = message => {
    window.clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = window.setTimeout(() => setToast(""), 4500);
  };
  const selectCase = id => {
    storage.selectCase(id);
    setQuestion(""); setAnswer(""); setUploadNotice(""); setActiveTab("overview");
  };
  const openCase = () => {
    setEditingCase(null); setIntakeSession(value => value + 1);
    setCaseError("");
    if (!auth.user) { setAuthMode("register"); setModal("auth"); return; }
    setModal("case");
  };
  const editCase = item => { setEditingCase(item); setIntakeSession(value => value + 1); setCaseError(""); setModal("case"); };
  const onAuthenticated = user => { auth.setUser(user); setModal(null); setView(emailLink.view || "overview"); emailLink.view = null; setAuthNotice(""); };
  useEffect(() => {
    // Idempotent: React development mode runs effects twice.
    const { reset, verify } = emailLink;
    if (reset) { setResetToken(reset); setAuthMode("reset"); setModal("auth"); }
    else if (emailLink.auth) { setAuthMode(emailLink.auth); setModal("auth"); }
    if (verify && !emailLink.verifyStarted) {
      emailLink.verifyStarted = true;
      authRequest("verify-email/confirm", { token: verify })
        .then(() => { showToast(lang === "de" ? "E-Mail-Adresse bestätigt." : "Email address confirmed."); auth.refresh().catch(() => {}); })
        .catch(() => showToast(lang === "de" ? "Bestätigungslink ungültig oder abgelaufen. Fordern Sie im Profil einen neuen an." : "Confirmation link invalid or expired. Request a new one in your profile."));
    }
  }, []);
  // A desk section requested by the mobile app needs a sign-in first when the browser has no session yet.
  useEffect(() => { if (!auth.loading && !auth.user && (emailLink.view || emailLink.caseId)) { setAuthMode("login"); setModal("auth"); } }, [auth.loading]);
  // Visitors who are not signed in start on the landing page; its buttons come back here with ?open=login or ?open=register.
  useEffect(() => {
    if (auth.loading || auth.user || modal || legalPage || emailLink.reset || emailLink.verify) return;
    window.location.replace("/start/index.html");
  }, [auth.loading, auth.user, modal, legalPage]);
  // A case requested by the mobile app opens once the signed-in user's cases are loaded.
  useEffect(() => {
    if (!auth.user || !emailLink.caseId || !storage.cases.some(item => item.id === emailLink.caseId)) return;
    selectCase(emailLink.caseId); setActiveTab(emailLink.caseTab); setView("case");
    emailLink.caseId = null;
  }, [auth.user?.id, storage.cases]);
  const signOut = async () => { try { await auth.logout(); setModal(null); setQuestion(""); setAnswer(""); } catch { showToast(lang === "de" ? "Abmelden fehlgeschlagen. Bitte erneut versuchen." : "Sign-out failed. Please try again."); } };
  const startCase = async payload => {
    if (savingCase) return false;
    setSavingCase(true); setCaseError("");
    try {
      const created = editingCase ? await storage.updateCase(editingCase.id, payload) : await storage.createCase(payload);
      setModal(null); setView("case"); setUploadNotice(""); setActiveTab("overview"); setQuestion(""); setAnswer("");
      showToast((editingCase ? (lang === "de" ? "Akte aktualisiert." : "Case file updated.") : t.saved) + " " + created.reference);
      return true;
    } catch (error) { setCaseError(error.status === 409 ? intakeCopy[lang].duplicate : error.status === 422 ? intakeCopy[lang].invalid : t.error); return false; } finally { setSavingCase(false); }
  };
  const onFile = () => {
    if (!auth.user) { setAuthMode("login"); setModal("auth"); return; }
    if (!storage.selectedCase) { showToast(t.noCase); openCase(); return; }
    fileRef.current?.click();
  };
  const onFiles = async e => {
    const input = e.currentTarget;
    const selected = [...input.files];
    if (!selected.length || !storage.selectedCase || storage.uploading) return;
    setUploadNotice("");
    try {
      const results = await storage.uploadDocuments(selected);
      const saved = results.filter(result => result.ok).length;
      const failures = results.filter(result => !result.ok).map(result => result.name + ": " + (result.status === 413 ? t.oversized : result.status === 415 ? t.unsupported : t.uploadError));
      setUploadNotice([saved ? saved + " " + t.uploadSaved : "", ...failures].filter(Boolean).join(" · "));
    } finally { input.value = ""; }
  };
  const openDraft = (draft, caseItem = storage.selectedCase) => {
    if (!auth.user) { setAuthMode("login"); setModal("auth"); return; }
    if (!caseItem) { showToast(t.noCase); openCase(); return; }
    storage.selectCase(caseItem.id);
    setDraftId(draft?.id || null);
    setSavedDraft(draft?.id ? draft : null);
    setDraftResearchId(draft?.research_run_id || null);
    setUseCurrentLetterhead(!draft?.letterhead_id && Boolean(auth.user?.letterhead_id));
    setDraftLanguage(draft?.language || lang);
    setDraftKind(draft?.kind || "letter");
    setDraftRecipient(draft?.recipient || "");
    const initialBody = draft?.body || documentTemplate(caseItem, lang);
    generatedDraft.current = draft ? null : initialBody;
    setDraftBody(initialBody);
    setDraftError(""); setModal("draft");
  };
  const changeDraftSettings = (kind, language, recipient) => {
    setDraftKind(kind); setDraftLanguage(language); setDraftRecipient(recipient);
    if (storage.selectedCase && draftBody === generatedDraft.current) {
      const body = documentTemplate(storage.selectedCase, language, kind, recipient);
      generatedDraft.current = body; setDraftBody(body);
    }
  };
  const insertDraftTemplate = () => {
    const body = documentTemplate(storage.selectedCase, draftLanguage, draftKind, draftRecipient);
    generatedDraft.current = body; setDraftBody(body);
  };
  const saveDraft = async () => {
    if (!draftBody.trim() || storage.savingDraft) return;
    setDraftError("");
    try {
      const saved = await storage.saveDraft({ body: draftBody, language: draftLanguage, kind: draftKind, recipient: draftRecipient, use_current_letterhead:useCurrentLetterhead, expected_version:savedDraft?.version, ...(!draftId && draftResearchId ? {research_run_id:draftResearchId} : {}) }, draftId);
      setDraftId(saved.id);setSavedDraft(saved);setDraftBody(saved.body);setDraftRecipient(saved.recipient);setUseCurrentLetterhead(false);showToast(t.draftSaved);
    } catch (failure) { setDraftError(failure.status === 409 ? (lang === 'de' ? 'Diese Fassung wurde bereits geändert. Schließen und erneut öffnen; Ihre Änderungen werden nicht überschrieben.' : 'This version has already changed. Close and reopen; your changes have not overwritten it.') : t.draftError); }
  };
  const downloadDraft = () => {
    const url = URL.createObjectURL(new Blob([draftBody], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = (storage.selectedCase?.reference || "Entwurf") + ".txt";
    document.body.appendChild(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const askAssistant = () => { if (!question.trim()) return; setAnswer(lang === "de" ? "Melden Sie sich an und öffnen Sie Recherche. Dort steht der KI-Assistent für Ihre ausgewählte Akte bereit." : "Sign in and open Research to use the AI assistant for your selected case."); };
  if (legalPage) return <LegalPage page={legalPage} lang={lang} setLang={setLang} />;
  return <div className={auth.user ? "app-site" : modal === "auth" ? "site auth-only" : "site"}>{auth.loading ? <div className="startup-screen" role="status">{lang === "de" ? "Arbeitsbereich wird geladen …" : "Loading workspace …"}</div> : auth.user ? <Dashboard key={auth.user.id} contacts={contacts} lang={lang} setLang={setLang} t={t} user={auth.user} storage={storage} view={view} setView={setView} onNewCase={openCase} onLogout={signOut} onUserUpdated={auth.setUser} onAccountDeleted={() => { auth.setUser(null); setView("overview"); showToast(lang === "de" ? "Konto und alle Daten wurden gelöscht." : "Account and all data were deleted."); }} workspaceProps={{ activeTab, setActiveTab, onFile, onDraft: openDraft, onSelectCase: selectCase, onEdit: editCase, uploadNotice, question, setQuestion, answer, askAssistant }} /> : <>{auth.error && <div className="connection-notice" role="status">{lang === "de" ? "Anmeldung derzeit nicht erreichbar." : "Sign-in is currently unavailable."} <button onClick={auth.retry}>{t.retry}</button></div>}<a className="skip-link" href="#main">Zum Inhalt springen</a><header className="site-header"><nav className={menu ? "open" : ""}><a href="#how" onClick={() => setMenu(false)}>{t.navHow}</a><a href="#features" onClick={() => setMenu(false)}>{t.navFeatures}</a><a href="#pricing" onClick={() => setMenu(false)}>{t.navPricing}</a><a href="#faq" onClick={() => setMenu(false)}>{t.navFaq}</a><span className="nav-divider" /><button className={lang === "de" ? "language active" : "language"} onClick={() => setLang("de")}>DE</button><span className="language-sep">|</span><button className={lang === "en" ? "language active" : "language"} onClick={() => setLang("en")}>EN</button><button className="header-login" onClick={() => { setAuthMode("login"); setModal("auth"); }}>{t.signIn}</button><button className="header-register" onClick={() => { setMenu(false); setAuthMode("register"); setModal("auth"); }}>{t.register}</button></nav><button className="menu-toggle" aria-label="Menü" onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button></header>
    <main id="main"><section className="hero-brand" id="top"><BrandLogo className="brand-logo hero-logo" /><div className="tested-in"><p>{t.testedIn}</p><ul>{COURTS.map(court => <li key={court}>{court}</li>)}</ul></div></section>
      <section className="steps-section" id="how"><p className="section-kicker">{lang === "de" ? "SO FUNKTIONIERT’S" : "HOW IT WORKS"}</p><h2>{t.stepsTitle}</h2><div className="steps-grid">{t.steps.map(([title, text], i) => <div className="step" key={title}><div className="step-number">0{i + 1}</div><div className="step-icon">{i === 0 ? <FileText /> : i === 1 ? <Upload /> : <PenLine />}</div><div><h3>{title}</h3><p>{text}</p></div></div>)}</div></section>
      <FeatureOverview lang={lang} onDraft={() => openDraft()} />
      <PricingOverview lang={lang} onSelect={audience => {setRegistrationAudience(audience);setAuthMode('register');setModal('auth');}} />
      <section className="faq-section" id="faq"><div className="section-heading"><p className="section-kicker">FAQ</p><h2>{t.faqTitle}</h2></div><div className="faq-list">{t.faq.map(([q, a]) => <details key={q}><summary>{q}<ChevronDown size={19} /></summary><p>{a}</p></details>)}</div></section>
    </main><footer className="site-footer"><Brand /><span>{t.limit}</span><LegalLinks lang={lang} /></footer></>}
    <input ref={fileRef} className="visually-hidden" type="file" multiple accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.zip" onChange={onFiles} />
    <Dialog open={modal === "case"} onClose={() => { if (!savingCase) setModal(null); }} title={editingCase ? (lang === "de" ? "Aktenstammdaten bearbeiten" : "Edit case particulars") : t.modalStart} className="intake-dialog" busy={savingCase}><CaseIntake key={intakeSession} initialCase={editingCase} user={auth.user} lang={lang} t={t} saving={savingCase} error={caseError} onSubmit={startCase} onCancel={() => setModal(null)} /></Dialog>
    <Dialog open={modal === "auth"} onClose={() => { setModal(null); auth.retry(); }} title={authCopy[lang][authMode]} className="auth-dialog">{modal === "auth" && <AuthForm key={`${authMode}:${registrationAudience}`} initialAudience={registrationAudience} lang={lang} mode={authMode} setMode={mode => { setAuthNotice(""); setAuthMode(mode); }} onAuthenticated={onAuthenticated} resetToken={resetToken} notice={authNotice} onResetDone={() => { setResetToken(""); setTimeout(() => setAuthNotice(authCopy[lang].resetDone)); }} />}</Dialog>
    <Dialog open={modal === "draft"} onClose={() => { if (!storage.savingDraft) setModal(null); }} title={dc.title} className="draft-dialog" busy={storage.savingDraft}><p className="dialog-intro">{dc.hint}</p><fieldset className="draft-settings" disabled={storage.savingDraft}><div className="intake-grid"><label>{dc.kind}<select aria-label={dc.kind} value={draftKind} onChange={e => changeDraftSettings(e.target.value, draftLanguage, draftRecipient)}>{dc.types.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label>{dc.language}<select aria-label={dc.language} value={draftLanguage} onChange={e => changeDraftSettings(draftKind, e.target.value, draftRecipient)}><option value="de">Deutsch</option><option value="en">English</option></select></label><label className="span-two">{dc.recipient}<textarea rows={2} maxLength={500} value={draftRecipient} onChange={e => changeDraftSettings(draftKind, draftLanguage, e.target.value)} placeholder={dc.recipientPlaceholder} /></label></div><ContactRecipient lang={lang} contacts={contacts} caseId={storage.selectedCase?.id} onChoose={recipient => changeDraftSettings(draftKind, draftLanguage, recipient)} /><button className="small-action" onClick={insertDraftTemplate}>{dc.insert}</button><p className="field-help">{dc.replaceHint}</p>{draftKind === "claim" && <p className="field-help">{dc.courtHint} <a href="https://www.gesetze-im-internet.de/zpo/__253.html" target="_blank" rel="noreferrer">§ 253 ZPO ↗</a></p>}</fieldset><label htmlFor="draft-editor">{t.draftBody}</label><textarea id="draft-editor" aria-label={t.draftBody} className="draft-editor" value={draftBody} maxLength={50000} onChange={e => setDraftBody(e.target.value)} disabled={storage.savingDraft} />{draftError && <p className="storage-error" role="alert">{draftError}</p>}{draftId && <label className="desk-checkbox"><input type="checkbox" checked={useCurrentLetterhead} onChange={event => setUseCurrentLetterhead(event.target.checked)} />{lang === "de" ? "Aktuellen Briefkopf aus dem Kontoprofil übernehmen" : "Use the current letterhead from my profile"}</label>}{modal === "draft" && <DraftReview key={draftId || "new"} lang={lang} caseId={storage.selectedCase?.id} draft={savedDraft} busy={storage.savingDraft} dirty={Boolean(savedDraft && (draftBody.trim() !== savedDraft.body || draftRecipient.trim() !== savedDraft.recipient || draftLanguage !== savedDraft.language || draftKind !== savedDraft.kind || useCurrentLetterhead))} onUpdated={value => {setSavedDraft(current => current && (current.version > value.version || (current.version === value.version && current.review_revision > value.review_revision)) ? current : value);storage.applyDraft(value);}} />}{modal === "draft" && <><DraftPdfPreview lang={lang} caseId={storage.selectedCase?.id} draftId={draftId} body={draftBody} useCurrentLetterhead={useCurrentLetterhead} /><DraftSend lang={lang} caseItem={storage.selectedCase} draft={savedDraft} dirty={Boolean(savedDraft && (draftBody.trim() !== savedDraft.body || draftRecipient.trim() !== savedDraft.recipient || draftLanguage !== savedDraft.language || draftKind !== savedDraft.kind || useCurrentLetterhead))} onSent={() => storage.reload()} /></>}<button className="text-link" onClick={downloadDraft}>{t.downloadDraft}</button><div className="dialog-actions"><button className="secondary-button" disabled={storage.savingDraft} onClick={() => setModal(null)}>{t.cancel}</button><button className="primary-button" disabled={storage.savingDraft || !draftBody.trim()} onClick={saveDraft}><Check size={18} /> {storage.savingDraft ? "…" : t.save}</button></div></Dialog>
    {toast && <div className="toast" role="status"><Check size={17} />{toast}</div>}
  </div>;
}
