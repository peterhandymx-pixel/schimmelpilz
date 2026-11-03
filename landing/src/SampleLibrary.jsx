import { useMemo, useState } from "react";
import { IconCopy, IconDownload, IconEdit, IconPlus } from "@tabler/icons-react";
import { SAMPLES, SAMPLE_AREAS, sampleContext } from "./documentSamples.js";
import { draftCopy } from "./draftTemplates.js";
import { matches } from "./workbench.js";

// Library of German sample documents: pick one, preview it with a case's data, then copy, download or open it as a draft.
export function SampleLibrary({ lang, cases, selectedCase, query = "", onDraft, onNewCase, canEdit = true }) {
  const de = lang === "de";
  const active = cases.filter(item => !item.archived_at);
  const [area, setArea] = useState("all"), [chosen, setChosen] = useState(SAMPLES[0].id), [notice, setNotice] = useState("");
  const [caseId, setCaseId] = useState(selectedCase && active.some(item => item.id === selectedCase.id) ? selectedCase.id : active[0]?.id || "");
  const target = active.find(item => item.id === caseId) || null;
  const shown = SAMPLES.filter(sample => (area === "all" || sample.area === area) && matches(query, sample.title, sample.norms));
  const sample = SAMPLES.find(item => item.id === chosen) || SAMPLES[0];
  const body = useMemo(() => sample.body(sampleContext(target)), [sample, target]);
  const kindName = draftCopy[lang].types.find(([id]) => id === sample.kind)?.[1];
  const areaName = id => SAMPLE_AREAS.find(([key]) => key === id)?.[1];
  const copy = async () => { try { await navigator.clipboard.writeText(body); setNotice(de ? "Text in die Zwischenablage kopiert." : "Copied to clipboard."); } catch { setNotice(de ? "Kopieren nicht möglich – Text bitte markieren und kopieren." : "Copy failed – select the text and copy it manually."); } };
  const download = () => {
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: `Muster-${sample.id}.txt` });
    link.click(); URL.revokeObjectURL(url);
  };

  return <>
    <div className="desk-panel-heading"><div><h2>{de ? "Musterbibliothek" : "Sample library"}</h2><p>{de ? `${SAMPLES.length} Musterschreiben und Schriftsätze – mit den Daten Ihrer Akte vorausgefüllt` : `${SAMPLES.length} German sample letters and pleadings – prefilled with your case data`}</p></div></div>
    <div className="eakte-filter">
      <label>{de ? "Rechtsgebiet" : "Area of law"}<select value={area} onChange={event => setArea(event.target.value)}><option value="all">{de ? "Alle Rechtsgebiete" : "All areas"}</option>{SAMPLE_AREAS.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      <label>{de ? "Daten einsetzen aus Akte" : "Fill in data from case"}<select value={caseId} onChange={event => setCaseId(event.target.value)}><option value="">{de ? "Ohne Akte (nur Platzhalter)" : "No case (placeholders only)"}</option>{active.map(item => <option key={item.id} value={item.id}>{item.reference} · {item.title}</option>)}</select></label>
      <span>{shown.length} {de ? "Muster" : "samples"}</span>
    </div>
    {!de && <p className="field-help">The samples are written in German for German law.</p>}
    <div className="sample-library">
      <nav className="sample-list" aria-label={de ? "Muster" : "Samples"}>{SAMPLE_AREAS.filter(([id]) => shown.some(item => item.area === id)).map(([id, name]) => <div key={id}><h3>{name}</h3>
        {shown.filter(item => item.area === id).map(item => <button key={item.id} className={item.id === sample.id ? "active" : ""} aria-current={item.id === sample.id ? "true" : undefined} onClick={() => { setChosen(item.id); setNotice(""); }}><strong>{item.title}</strong><small>{item.norms}</small></button>)}</div>)}
        {!shown.length && <p className="desk-empty">{de ? "Kein Muster passt zur Suche." : "No sample matches the search."}</p>}
      </nav>
      <article className="sample-preview">
        <span className="desk-eyebrow">{areaName(sample.area)} · {kindName}</span>
        <h3>{sample.title}</h3>
        <p className="sample-norms">{sample.norms}</p>
        {sample.note && <p className="storage-notice">{sample.note}</p>}
        <div className="sample-actions">
          {target
            ? <button className="desk-button solid" disabled={!canEdit} onClick={() => onDraft({ body, language: "de", kind: sample.kind, recipient: "" }, target)}><IconEdit size={17} />{de ? "Als Entwurf in dieser Akte bearbeiten" : "Edit as draft in this case"}</button>
            : <button className="desk-button solid" disabled={!canEdit} onClick={onNewCase}><IconPlus size={17} />{de ? "Akte anlegen, um das Muster zu übernehmen" : "Create a case to use this sample"}</button>}
          <button className="desk-button" onClick={copy}><IconCopy size={17} />{de ? "Kopieren" : "Copy"}</button>
          <button className="desk-button" onClick={download}><IconDownload size={17} />{de ? "Als Textdatei" : "As text file"}</button>
        </div>
        {notice && <p className="storage-notice" role="status">{notice}</p>}
        <pre className="sample-text">{body}</pre>
        <p className="field-help">{de ? "Muster sind Ausgangspunkte, keine Rechtsberatung. Platzhalter in [Klammern] ergänzen; Normen, Fristen, Zuständigkeit und Form für den Einzelfall prüfen." : "Samples are starting points, not legal advice. Complete [placeholders]; check norms, deadlines, jurisdiction and form for the individual case."}</p>
      </article>
    </div>
  </>;
}
