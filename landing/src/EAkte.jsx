import { useEffect, useState } from "react";
import { IconDownload, IconEdit, IconFileText, IconFolderOpen, IconMailForward, IconUpload } from "@tabler/icons-react";
import { API_BASE } from "./useCaseStorage.js";
import { reviewLabels } from "./DraftReview.jsx";
import { draftSubject } from "./draftTemplates.js";
import { DocumentViewer } from "./DocumentViewer.jsx";
import { dateLabel, matches } from "./workbench.js";

const KINDS = {
  de: { letter: "Anschreiben", claim: "Klage", application: "Antrag", objection: "Widerspruch", response: "Erwiderung" },
  en: { letter: "Letter", claim: "Claim", application: "Application", objection: "Objection", response: "Response" },
};

// One case's electronic file: everything that came in and went out, in the order it was added, numbered like sheets.
export function EAkte({ cases, selectedCase, lang, query = "", open, onSelectCase, onFile, uploading, notice, onDraft, onRefresh }) {
  const de = lang === "de";
  const [filter, setFilter] = useState("all");
  const [viewing, setViewing] = useState(null);
  const active = cases.filter(item => !item.archived_at);
  const current = selectedCase && cases.some(item => item.id === selectedCase.id) ? selectedCase : active[0] || cases[0] || null;
  // The upload button files into the selected case, so the case shown here must also be the selected one.
  useEffect(() => { if (current && current.id !== selectedCase?.id) onSelectCase(current.id); }, [current?.id]);
  const reading = Boolean(current?.documents.some(doc => ["queued", "running"].includes(doc.auto_text_status)));
  useEffect(() => { if (!reading || !onRefresh) return undefined; const timer = window.setTimeout(onRefresh, 3000); return () => window.clearTimeout(timer); }, [reading, onRefresh, cases]);

  if (!current) return <><div className="desk-panel-heading"><div><h2>E-Akte</h2><p>{de ? "Alle Eingänge und Schriftsätze einer Akte in zeitlicher Reihenfolge" : "Everything filed in a case, in order"}</p></div></div><p className="desk-empty">{de ? "Noch keine Akte. Legen Sie zuerst eine Akte an." : "No case yet. Create a case first."}</p></>;

  const sheets = [
    ...current.documents.map(doc => ({ type: "in", id: doc.id, date: doc.created_at, title: doc.original_name, doc })),
    ...(current.drafts || []).map(draft => ({ type: "out", id: draft.id, date: draft.created_at, title: draftSubject(draft.body) || KINDS[lang][draft.kind] || KINDS[lang].letter, draft })),
  ].sort((a, b) => a.date.localeCompare(b.date)).map((sheet, index) => ({ ...sheet, no: index + 1 }));
  const shown = sheets.filter(sheet => (filter === "all" || filter === sheet.type) && matches(query, sheet.title, sheet.draft?.recipient));
  const docState = doc => ["queued", "running"].includes(doc.auto_text_status) ? (de ? "Text wird gelesen …" : "Reading text …")
    : doc.reviewed_units ? (de ? "Text geprüft" : "Text reviewed") : doc.extraction_status === "ready" ? (de ? "Text ungeprüft" : "Text not reviewed") : "";

  return <>
    <div className="desk-panel-heading"><div><h2>E-Akte</h2><p>{de ? "Alle Eingänge und Schriftsätze einer Akte in zeitlicher Reihenfolge, Blatt für Blatt" : "Everything filed in a case, in order, sheet by sheet"}</p></div>
      <div className="eakte-actions"><button className="desk-button" onClick={onFile} disabled={uploading}><IconUpload size={17} />{uploading ? (de ? "Wird hochgeladen …" : "Uploading …") : (de ? "Dokument zur Akte" : "Add to file")}</button><button className="desk-link" onClick={() => open(current.id)}><IconFolderOpen size={16} />{de ? "Akte öffnen" : "Open case"}</button></div></div>
    <div className="eakte-filter">
      <label>{de ? "Akte" : "Case"}<select value={current.id} onChange={event => onSelectCase(event.target.value)}>{cases.map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}{item.archived_at ? (de ? " (archiviert)" : " (archived)") : ""}</option>)}</select></label>
      <label>{de ? "Anzeigen" : "Show"}<select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">{de ? "Alles" : "Everything"}</option><option value="in">{de ? "Eingänge / Dokumente" : "Incoming / documents"}</option><option value="out">{de ? "Schriftsätze" : "Drafts"}</option></select></label>
      <span>{de ? `${sheets.length} Blatt in dieser Akte` : `${sheets.length} sheets in this case`}</span>
    </div>
    {notice && <p className="storage-notice" role="status">{notice}</p>}
    {viewing && <DocumentViewer key={viewing.id} lang={lang} caseId={current.id} document={viewing} onClose={() => setViewing(null)} />}
    {shown.length ? <div className="desk-table-scroll"><table className="desk-table eakte-table"><thead><tr><th>{de ? "Bl." : "No."}</th><th>{de ? "Datum" : "Date"}</th><th>{de ? "Art" : "Type"}</th><th>{de ? "Bezeichnung" : "Title"}</th><th>{de ? "Aktion" : "Action"}</th></tr></thead>
      <tbody>{shown.map(sheet => <tr key={sheet.type + sheet.id}>
        <td className="eakte-no">{sheet.no}</td>
        <td>{dateLabel(sheet.date, lang, true)}</td>
        <td><span className={`eakte-type eakte-${sheet.type}`}>{sheet.type === "in" ? <><IconFileText size={15} />{de ? "Eingang" : "Incoming"}</> : <><IconMailForward size={15} />{de ? "Schriftsatz" : "Draft"}</>}</span></td>
        <td><strong className="eakte-title">{sheet.title}</strong>{sheet.type === "in"
          ? docState(sheet.doc) && <small>{docState(sheet.doc)}</small>
          : <small>{sheet.draft.recipient ? sheet.draft.recipient.split("\n")[0] + " · " : ""}{reviewLabels[lang][sheet.draft.review_status || "draft"]} · v{sheet.draft.version || 1}</small>}</td>
        <td className="eakte-links">{sheet.type === "in"
          ? <><button className="desk-link" onClick={() => setViewing(viewing?.id === sheet.id ? null : sheet.doc)}>{de ? "Ansehen" : "View"}</button><a className="desk-link" href={`${API_BASE}/api/cases/${current.id}/documents/${sheet.id}/download`} download><IconDownload size={15} />{de ? "Herunterladen" : "Download"}</a><button className="desk-link" onClick={() => open(current.id, "documents")}>{de ? "Text prüfen" : "Review text"}</button></>
          : <><button className="desk-link" onClick={() => onDraft(sheet.draft, current)}><IconEdit size={15} />{de ? "Bearbeiten" : "Edit"}</button><a className="desk-link" href={`${API_BASE}/api/cases/${current.id}/drafts/${sheet.id}/pdf`} target="_blank" rel="noreferrer">PDF</a></>}</td>
      </tr>)}</tbody></table></div>
      : <p className="desk-empty">{sheets.length ? (de ? "Nichts in dieser Auswahl." : "Nothing in this selection.") : (de ? "Diese Akte ist noch leer. Laden Sie das erste Dokument hoch oder erstellen Sie einen Schriftsatz." : "This file is still empty. Upload a first document or create a draft.")}</p>}
  </>;
}
