import { IconHome, IconFileText, IconEdit, IconMessageCircle, IconUpload, IconDownload } from "@tabler/icons-react";
import { API_BASE, letterTemplate } from "./useCaseStorage.js";
import { CaseFacts } from "./CaseIntake.jsx";
import { draftCopy } from "./draftTemplates.js";

const demoDocuments = [
  { id: "demo1", original_name: "Mietvertrag.pdf", size_bytes: 2100000 },
  { id: "demo2", original_name: "Schriftverkehr.pdf", size_bytes: 1400000 },
  { id: "demo3", original_name: "Fotos.zip", size_bytes: 12800000 },
];

export function CaseWorkspace({ lang, t, activeTab, setActiveTab, onFile, onDraft, storage, question, setQuestion, answer, askAssistant, onSelectCase, uploadNotice, appMode = false }) {
  const item = storage.selectedCase;
  const reference = item?.reference || "SCH-2026-000123";
  const documents = item ? item.documents : demoDocuments;
  const drafts = item?.drafts || [];
  const tabs = [["overview", t.overview, IconHome], ["documents", t.documents, IconFileText], ["drafts", t.drafts, IconEdit], ["assistant", t.assistant, IconMessageCircle]];
  const isBusy = storage.uploading || storage.savingDraft;

  const filePanel = <section className="panel file-panel">
    <div className="panel-title"><h4>{t.files}</h4><button disabled={storage.uploading} className="small-action" onClick={onFile}><IconUpload size={15} />{storage.uploading ? t.uploading : t.add}</button></div>
    {!documents.length && <p className="storage-empty">{t.noDocuments}</p>}
    {documents.map(document => {
      const extension = document.original_name.split(".").pop().toUpperCase();
      const mb = (document.size_bytes / 1000000).toLocaleString(lang, { maximumFractionDigits: 1 });
      const contents = <><span className={`file-icon ${extension === "ZIP" ? "blue" : "red"}`}><IconFileText size={16} /></span><span className="file-name">{document.original_name}</span><small>{extension} · {mb} MB</small>{item && <IconDownload size={16} />}</>;
      return item
        ? <a key={document.id} className="file-row" href={`${API_BASE}/api/cases/${item.id}/documents/${document.id}/download`} download>{contents}</a>
        : <div key={document.id} className="file-row">{contents}</div>;
    })}
    {uploadNotice && <p className="storage-notice" role="status">{uploadNotice}</p>}
  </section>;

  const draftPanel = <section className="panel draft-panel">
    <div className="panel-title"><h4>{t.draft}</h4><span className="draft-chip">{t.draftLabel}</span></div>
    {item ? <>
      <p className="draft-snippet">{drafts[0]?.body || letterTemplate(item, lang)}</p>
      <button className="text-link" onClick={() => onDraft(drafts[0])}>{drafts.length ? t.editDraft : t.newDraft}</button>
    </> : <>
      <p>{lang === "de" ? "Sehr geehrte Damen und Herren," : "Dear Sir or Madam,"}</p>
      <p>{lang === "de" ? "hiermit nehme ich Bezug auf den bestehenden Mietvertrag und die aufgetretenen Mängel in der Wohnung." : "I am writing regarding the tenancy agreement and the defects in the flat."}</p>
      <p>{lang === "de" ? "Bitte lassen Sie mir eine schriftliche Stellungnahme zukommen." : "Please provide a written response."}</p>
      <button className="text-link" onClick={() => onDraft()}>{t.newDraft}</button>
    </>}
  </section>;

  return <div className={`workspace-shell ${appMode ? "app-workspace" : ""}`} id="preview">
    <div className="workspace-sidebar">
      <img className="brand-logo" src="/assets/schimmelpilz-logo.png" alt="Virtuelle Rechtsassistenz Schimmelpilz" />
      <div className="workspace-nav">{tabs.map(([id, label, Icon]) => <button key={id} aria-label={label} className={activeTab === id ? "selected" : ""} onClick={() => setActiveTab(id)}><Icon size={18} />{label}</button>)}</div>
      <div className="sidebar-foot">{t.localStorage}</div>
    </div>
    <div className="workspace-content">
      <div className="workspace-topline"><div><div className="small-label">{reference}</div><h2>{lang === "de" ? "Ihre Fallübersicht" : "Your case overview"}</h2></div><span className="case-badge">{item ? t.savedCase : t.badge}</span></div>
      <div className="storage-toolbar">
        <label htmlFor="saved-case">{t.savedCases}</label>
        <select id="saved-case" value={item?.id || ""} disabled={storage.loading || isBusy} onChange={e => onSelectCase(e.target.value)}>
          {!appMode && <option value="">{t.badge}</option>}
          {storage.cases.map(saved => <option value={saved.id} key={saved.id}>{saved.reference} · {saved.title}</option>)}
        </select>
      </div>
      {storage.loading && <p className="storage-notice" role="status">{t.loadingCases}</p>}
      {storage.loadError && <p className="storage-notice storage-error" role="alert">{t.loadError} <button onClick={() => storage.reload()}>{t.retry}</button></p>}
      <div className="case-heading"><div><h3>{item?.title || t.caseTitle}</h3><div className="case-subline">{reference} <span className="status-pill">{t.inProgress}</span></div></div></div>
      <div className="case-tabs">{tabs.slice(0, 3).map(([id, label]) => <button key={id} className={activeTab === id ? "active" : ""} onClick={() => setActiveTab(id)}>{label}</button>)}</div>
      {activeTab === "overview" && <>{item && <CaseFacts item={item} lang={lang} />}{filePanel}{draftPanel}</>}
      {activeTab === "documents" && filePanel}
      {activeTab === "drafts" && <section className="panel draft-panel">
        <div className="panel-title"><h4>{t.drafts}</h4><button className="small-action" onClick={() => onDraft()}>{t.newDraft}</button></div>
        {!drafts.length && <p className="storage-empty">{t.noDrafts}</p>}
        {drafts.map(draft => <button className="saved-draft" key={draft.id} onClick={() => onDraft(draft)}><IconEdit size={17} /><span>{draftCopy[lang].types.find(([id]) => id === draft.kind)?.[1] || t.draftLabel} · {draft.language.toUpperCase()}<small>{draft.recipient || draft.body.slice(0, 80)}</small></span></button>)}
      </section>}
      {activeTab === "assistant" && <section className="panel assistant-panel"><div className="assistant-title"><span className="assistant-avatar"><IconMessageCircle size={17} /></span><h4>{lang === "de" ? "Ihr KI-Assistent" : "Your AI assistant"}</h4></div><div className="assistant-answer">{answer || t.missing}</div><div className="assistant-input"><input aria-label={t.ask} value={question} onChange={e => setQuestion(e.target.value)} placeholder={t.ask} onKeyDown={e => e.key === "Enter" && askAssistant()} /><button onClick={askAssistant} aria-label={lang === "de" ? "Frage senden" : "Send question"}>➤</button></div><small className="demo-note">{t.limit}</small></section>}
    </div>
    {!appMode && <button className="workspace-chat" onClick={() => setActiveTab("assistant")}><div className="chat-head"><span className="assistant-avatar"><IconMessageCircle size={16} /></span><strong>{lang === "de" ? "Ihr KI-Assistent" : "Your AI assistant"}</strong></div><div className="chat-suggestion">{t.missing}</div><div className="chat-input"><span>{t.ask}</span><span>➤</span></div></button>}
  </div>;
}
