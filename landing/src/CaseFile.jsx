import { RoutePlanner } from './RoutePlanner.jsx';
import { CaseTools } from './CaseTools.jsx';
import { CostReview } from './CostReview.jsx';
import { ContactBook } from './ContactBook.jsx';
import { useState } from "react";
import { IconArrowLeft, IconEdit, IconFileText, IconUpload, IconHash } from "@tabler/icons-react";
import { CaseFacts, intakeCopy } from "./CaseIntake.jsx";
import { ActivityList, DocumentList, DraftList, Status, TaskBoard } from "./DeskComponents.jsx";
import { dateLabel } from "./workbench.js";
import { DeadlineCalculator } from "./DeadlineCalculator.jsx";

export function CaseFile({ item, lang, storage, workspace, open, back, contacts, canDelete = false }) {
  const de = lang === "de", c = intakeCopy[lang], d = item.details || {};
  const tabs = de ? [["overview", "Aktenübersicht"], ["parties", "Beteiligte"], ["documents", "Dokumente"], ["drafts", "Schriftsätze"], ["tasks", "Fristen & Aufgaben"], ["costs", "Kostenprüfung"], ["routes", "Verfahrenswege"], ["activity", "Verlauf"]] : [["overview", "Case overview"], ["parties", "Parties"], ["documents", "Documents"], ["drafts", "Drafts"], ["tasks", "Deadlines & tasks"], ["costs", "Cost review"], ["routes", "Procedural routes"], ["activity", "Activity"]];
  return <div className="desk-case-file"><button className="desk-link desk-back" onClick={back}><IconArrowLeft size={16} />{de ? "Aktenbestand" : "Case register"}</button><header className="desk-case-header"><div><span className="desk-reference">{item.reference}</span>{storage.changeReference && <ReferenceEditor item={item} lang={lang} storage={storage} />}<h2>{item.title}</h2><div className="desk-case-meta"><Status item={item} lang={lang} /><span>{c.areas.find(([id]) => id === d.legal_area)?.[1] || c.areas[0][1]}</span><span>{d.jurisdiction || "DE"}</span><span>{c.stages.find(([id]) => id === d.stage)?.[1] || c.stages[0][1]}</span></div></div><div className="desk-case-actions"><button className="desk-button" onClick={() => workspace.onEdit(item)}><IconEdit size={17} />{de ? "Stammdaten bearbeiten" : "Edit particulars"}</button><button className="desk-button solid" onClick={() => workspace.onDraft(undefined, item)}><IconFileText size={17} />{de ? "Schriftsatz erstellen" : "Prepare document"}</button></div></header>
    {item.documents.some(document=>document.inbox_reassigned_at) && <p className="storage-notice">{de ? "Eine Posteingangszuordnung wurde berichtigt. Frühere Dokumente bleiben als Nachweis erhalten. Bereits gespeicherte Antworten, Schriftsätze und eigene Freigaben vor weiterer Verwendung anhand des Berichtigungsverlaufs erneut prüfen." : "An incoming document assignment was corrected. Previous documents remain as records. Recheck existing answers, drafts and self-declared approvals against the correction history before further use."}</p>}
    <CaseTools item={item} lang={lang} onChanged={storage.reload} canDelete={canDelete} onDeleted={async () => { await storage.reload(); back(); }} />
    <nav className="desk-tabs" aria-label={de ? "Aktenregister" : "Case sections"}>{tabs.map(([id, title]) => <button key={id} aria-current={workspace.activeTab === id ? "page" : undefined} className={workspace.activeTab === id ? "active" : ""} onClick={() => workspace.setActiveTab(id)}>{title}{id === "documents" && <span>{item.documents.length}</span>}{id === "drafts" && <span>{item.drafts.length}</span>}</button>)}</nav>
    {workspace.activeTab === "overview" && <><div className="desk-case-columns"><div><section className="desk-panel"><div className="desk-panel-heading"><h2>{de ? "Angelegenheit & Auftrag" : "Matter & instructions"}</h2><span className="desk-tag">{de ? "Angelegt" : "Opened"} {dateLabel(item.created_at, lang)}</span></div><div className="desk-matter"><h3>{de ? "Sachverhalt" : "Facts"}</h3><p>{item.description}</p><h3>{c.objective}</h3><p>{d.objective || (de ? "Noch kein Auftrag / Ziel hinterlegt." : "No instructions / objective recorded yet.")}</p></div><dl className="desk-particulars"><div><dt>{de ? "Eigene Partei / Mandant" : "Own party / client"}</dt><dd>{d.client_name || "—"}</dd></div><div><dt>{c.opponent}</dt><dd>{d.opponent_name || "—"}</dd></div><div><dt>{c.court}</dt><dd>{d.court || "—"}</dd></div><div><dt>{c.courtReference}</dt><dd>{d.court_reference || "—"}</dd></div><div><dt>{de ? "Sachbearbeitung" : "Responsible person"}</dt><dd>{d.responsible || "—"}</dd></div><div><dt>{c.value}</dt><dd>{d.dispute_value != null ? `${Number(d.dispute_value).toLocaleString(lang, { minimumFractionDigits: 2 })} ${d.currency || "EUR"}` : "—"}</dd></div></dl></section><section className="desk-panel"><TaskBoard caseId={item.id} cases={[item]} lang={lang} open={open} saveTask={storage.saveTask} compact /></section></div><div><section className="desk-panel"><div className="desk-panel-heading"><h2>{de ? "Dokumente & Schriftsätze" : "Documents & drafts"}</h2></div><div className="desk-case-shortcuts"><button onClick={() => workspace.setActiveTab("documents")}><IconUpload size={21} /><span>{de ? "Dokumentenablage" : "Document storage"}<small>{item.documents.length} {de ? "Dateien" : "files"}</small></span><span>→</span></button><button onClick={() => workspace.setActiveTab("drafts")}><IconFileText size={21} /><span>{de ? "Schriftsätze" : "Drafts"}<small>{item.drafts.length} {de ? "Gespeicherte Entwürfe" : "saved drafts"}</small></span><span>→</span></button></div></section><section className="desk-panel"><div className="desk-panel-heading"><h2>{de ? "Letzte Bearbeitungsschritte" : "Recent activity"}</h2></div><ActivityList cases={[item]} lang={lang} open={open} limit={5} /></section></div></div><CaseFacts item={item} lang={lang} /></>}
    {workspace.activeTab === "parties" && <><ContactBook key={item.id} caseId={item.id} contacts={contacts} cases={storage.cases} lang={lang} open={open} onSaved={() => storage.reload()} canDelete={canDelete} /><button className="desk-button" onClick={() => workspace.onEdit(item)}>{de ? "Beteiligte in Aktenstammdaten bearbeiten" : "Edit parties in case particulars"}</button></>}
    {workspace.activeTab === "documents" && <section className="desk-panel"><DocumentList cases={[item]} lang={lang} open={open} onFile={workspace.onFile} uploading={storage.uploading} notice={workspace.uploadNotice} onRefresh={storage.reload} canDelete={canDelete} /></section>}
    {workspace.activeTab === "drafts" && <section className="desk-panel"><DraftList cases={[item]} lang={lang} open={open} onDraft={workspace.onDraft} onNew={() => workspace.onDraft(undefined, item)} onChanged={storage.reload} canDelete={canDelete} /></section>}
    {workspace.activeTab === "tasks" && <section className="desk-panel"><TaskBoard key={item.id} caseId={item.id} cases={[item]} lang={lang} open={open} saveTask={storage.saveTask} onChanged={storage.reload} canDelete={canDelete} /></section>}{workspace.activeTab === "tasks" && <DeadlineCalculator key={`deadline-${item.id}`} lang={lang} cases={[item]} caseId={item.id} saveTask={storage.saveTask} />}
    {workspace.activeTab === "routes" && <RoutePlanner cases={storage.cases} lang={lang} caseId={item.id} onChanged={storage.reload} onDraft={workspace.onDraft} />}
    {workspace.activeTab === "costs" && <CostReview key={item.id} caseId={item.id} lang={lang} cases={storage.cases} onChanged={() => storage.reload()} onDraft={workspace.onDraft} />}
    {workspace.activeTab === "activity" && <section className="desk-panel"><div className="desk-panel-heading"><h2>{de ? "Aktenverlauf" : "Case activity"}</h2><p>{de ? "Gespeicherte Bearbeitungsschritte seit Einführung des Verlaufs" : "Recorded changes since activity tracking was introduced"}</p></div><ActivityList cases={[item]} lang={lang} open={open} /></section>}
  </div>;
}

// A firm taking over a case from the system gives it its own file number: typed in, or allocated automatically.
function ReferenceEditor({ item, lang, storage }) {
  const de = lang === "de";
  const [open, setOpen] = useState(false), [mode, setMode] = useState("existing"), [value, setValue] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const save = async event => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await storage.changeReference(item.id, mode === "existing" ? { mode, reference: value.trim() } : { mode });
      setOpen(false); setValue("");
    } catch (failure) {
      setError(failure.status === 409 ? (de ? "Dieses Aktenzeichen ist bereits vergeben." : "This reference is already in use.") : (de ? "Aktenzeichen konnte nicht geändert werden." : "The reference could not be changed."));
    } finally { setBusy(false); }
  };
  if (!open) return <button type="button" className="desk-link reference-change" onClick={() => setOpen(true)}><IconHash size={14} />{de ? "Aktenzeichen ändern" : "Change reference"}</button>;
  return <form className="reference-editor" onSubmit={save}>
    <fieldset><legend>{de ? "Aktenzeichen für diese Akte" : "File reference for this case"}</legend>
      <label className="desk-checkbox"><input type="radio" name={`ref-${item.id}`} checked={mode === "existing"} onChange={() => setMode("existing")} />{de ? "Eigenes Aktenzeichen der Kanzlei eintragen" : "Enter the firm's own reference"}</label>
      {mode === "existing" && <input autoFocus required maxLength={100} value={value} onChange={event => setValue(event.target.value)} placeholder={de ? "z. B. 123/26" : "e.g. 123/26"} aria-label={de ? "Neues Aktenzeichen" : "New reference"} />}
      <label className="desk-checkbox"><input type="radio" name={`ref-${item.id}`} checked={mode === "generate"} onChange={() => setMode("generate")} />{de ? "Automatisch neu vergeben (fortlaufende Nummer)" : "Allocate automatically (running number)"}</label>
    </fieldset>
    <p className="field-help">{de ? `Bisher: ${item.reference}. Das alte Aktenzeichen bleibt im Verlauf vermerkt; bereits erstellte Schreiben behalten ihr Aktenzeichen.` : `Currently: ${item.reference}. The old reference stays in the activity log; existing letters keep their reference.`}</p>
    {error && <p role="alert" className="storage-error">{error}</p>}
    <span className="reference-actions"><button className="desk-button solid" disabled={busy || (mode === "existing" && !value.trim())}>{de ? "Übernehmen" : "Apply"}</button>
      <button type="button" className="desk-link" onClick={() => { setOpen(false); setError(""); }}>{de ? "Abbrechen" : "Cancel"}</button></span>
  </form>;
}
