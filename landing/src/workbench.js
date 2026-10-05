export const statusLabels = {
  de: { active: "In Bearbeitung", waiting: "Wartet auf Rückmeldung", closed: "Abgeschlossen" },
  en: { active: "Active", waiting: "Awaiting response", closed: "Closed" },
};

export const activityLabels = {
  de: { case_created: "Akte angelegt", case_updated: "Stammdaten aktualisiert", document_uploaded: "Dokument hinzugefügt", draft_created: "Entwurf erstellt", draft_updated: "Entwurf bearbeitet", task_created: "Aufgabe angelegt", task_updated: "Aufgabe bearbeitet", task_completed: "Aufgabe erledigt", task_reopened: "Aufgabe wieder geöffnet", research_answer: "KI-Rechercheantwort gespeichert", document_extracted: "Dokumentauslesen bearbeitet", document_text_reviewed: "Dokumenttext geprüft", document_text_unreviewed: "Dokumenttext ohne Freigabe gespeichert" },
  en: { case_created: "Case opened", case_updated: "Particulars updated", document_uploaded: "Document added", draft_created: "Draft created", draft_updated: "Draft edited", task_created: "Task created", task_updated: "Task edited", task_completed: "Task completed", task_reopened: "Task reopened", research_answer: "AI research answer saved", document_extracted: "Document extraction processed", document_text_reviewed: "Document text reviewed", document_text_unreviewed: "Document text saved without approval" },
};

export function localToday(value = new Date()) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export function dateLabel(value, lang, includeTime = false) {
  if (!value) return "—";
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return includeTime ? date.toLocaleString(lang === "de" ? "de-DE" : "en-GB", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : date.toLocaleDateString(lang === "de" ? "de-DE" : "en-GB");
}

export function matches(query, ...values) {
  const text = values.filter(Boolean).join(" ").toLocaleLowerCase();
  return query.trim().toLocaleLowerCase().split(/\s+/).every(word => text.includes(word));
}

export function caseMatches(item, query) {
  return matches(query, item.reference, item.title, item.details?.client_name, item.details?.opponent_name, item.details?.court_reference, item.details?.responsible);
}

export function taskRows(cases) {
  return cases.flatMap(item => (item.tasks || []).map(task => ({ ...task, caseItem: item }))).sort((a, b) => Number(a.completed) - Number(b.completed) || (a.due_on || "9999").localeCompare(b.due_on || "9999") || Number(b.priority === "high") - Number(a.priority === "high"));
}

// A name alone is insufficient to merge records belonging to different people.
export function partyRows(cases) {
  const grouped = new Map();
  for (const item of cases) {
    const d = item.details || {};
    for (const role of ["client", "opponent"]) {
      const name = d[`${role}_name`];
      if (!name) continue;
      const email = d[`${role}_email`] || "";
      const address = d[`${role}_address`] || "";
      const key = JSON.stringify([role, name.trim().toLocaleLowerCase(), email.trim().toLocaleLowerCase(), address.trim().toLocaleLowerCase(), email || address ? "" : item.id]);
      if (!grouped.has(key)) grouped.set(key, { key, name, role, email, address, cases: [] });
      grouped.get(key).cases.push(item);
    }
  }
  return [...grouped.values()];
}

export function activityRows(cases) {
  return cases.flatMap(item => (item.activities?.length ? item.activities : [{ id: `created-${item.id}`, action: "case_created", created_at: item.created_at, detail: "" }]).map(event => ({ ...event, caseItem: item }))).sort((a, b) => b.created_at.localeCompare(a.created_at));
}
