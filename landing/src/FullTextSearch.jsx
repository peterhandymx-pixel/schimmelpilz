import { useEffect, useState } from "react";
import { IconFileText, IconFolder, IconCalendarEvent, IconScale, IconMail, IconUser, IconSearch } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";

const ICONS = { case: IconFolder, document: IconFileText, draft: IconMail, task: IconCalendarEvent, research: IconScale };

// Full-text results across all files; the query goes in the request body, never the URL.
export function FullTextSearch({ lang, query, open }) {
  const de = lang === "de";
  const [result, setResult] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) { setResult(null); return undefined; }
    const timer = setTimeout(async () => {
      setBusy(true); setError("");
      try { setResult(await request("/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ q: text }) })); }
      catch { setError(de ? "Suche fehlgeschlagen. Bitte erneut versuchen." : "Search failed. Please retry."); }
      finally { setBusy(false); }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);
  const kindLabel = { case: de ? "Akte" : "File", document: de ? "Dokument" : "Document", draft: de ? "Schriftsatz" : "Draft", task: de ? "Frist/Aufgabe" : "Task", research: de ? "Recherche" : "Research" };

  return <section className="desk-panel fulltext">
    <div className="desk-panel-heading"><div><h2>{de ? "Volltextsuche" : "Full-text search"}</h2>
      <p>{de ? "Aktendaten, Dokumenttexte (Seite für Seite), Schriftsätze, Fristen, Recherchen und Adressen – alle Wörter müssen vorkommen." : "Particulars, document text (page by page), drafts, tasks, research and contacts – all words must occur."}</p></div></div>
    {query.trim().length < 2 && <p className="desk-empty">{de ? "Suchbegriff oben links eingeben, z. B. Name, Aktenzeichen der Gegenseite, IBAN oder ein Wort aus einem Brief." : "Enter a term top left, e.g. a name, the other side's reference, an IBAN or a word from a letter."}</p>}
    {busy && <p role="status" className="desk-empty">{de ? "Suche läuft …" : "Searching …"}</p>}
    {error && <p role="alert" className="storage-error">{error}</p>}
    {result && !busy && <>
      <p className="fulltext-count">{result.total ? (de ? `${result.total} Treffer für „${result.query}“` : `${result.total} hits for “${result.query}”`) : (de ? `Keine Treffer für „${result.query}“. Hinweis: Dokumente ohne Textschicht (Scan ohne Texterkennung) sind nicht durchsuchbar.` : `No hits for “${result.query}”. Documents without a text layer cannot be searched.`)}</p>
      {result.groups.map(group => <article key={group.case_id} className="fulltext-group">
        <header><button type="button" className="desk-link" onClick={() => open(group.case_id)}><strong>{group.reference}</strong> · {group.title}</button>{group.archived && <span className="desk-tag">{de ? "Archiv" : "Archive"}</span>}</header>
        <ul>{group.hits.map((hit, index) => { const Icon = ICONS[hit.kind] || IconSearch; return <li key={index}>
          <button type="button" onClick={() => open(group.case_id, hit.tab === "research" ? "research-context" : hit.tab)}>
            <Icon size={16} /><span><small>{kindLabel[hit.kind]} · {hit.label}</small><span className="fulltext-excerpt">{hit.excerpt}</span></span></button></li>; })}</ul>
      </article>)}
      {result.contacts?.length > 0 && <article className="fulltext-group"><header><strong>{de ? "Adressen" : "Contacts"}</strong></header>
        <ul>{result.contacts.map(contact => <li key={contact.id}><button type="button" onClick={() => open(null, "parties")}><IconUser size={16} /><span><small>{contact.name}</small><span className="fulltext-excerpt">{contact.excerpt}</span></span></button></li>)}</ul></article>}
    </>}
  </section>;
}
