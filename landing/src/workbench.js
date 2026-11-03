export const statusLabels = {
  de: { active: "In Bearbeitung", waiting: "Wartet auf Rückmeldung", closed: "Abgeschlossen" },
  en: { active: "Active", waiting: "Awaiting response", closed: "Closed" },
};

export const activityLabels = {
  de: { inbox_corrected: "Posteingangszuordnung berichtigt", document_ocr: "Lokale Texterkennung ausgeführt", route_plan_saved: "Verfahrensplan gespeichert", case_archived: "Akte archiviert", case_restored: "Akte aus Archiv wiederhergestellt", cost_review_saved: "Kostenprüfung gespeichert", inbox_assigned: "Posteingang der Akte zugeordnet", contact_linked: "Kontakt zugeordnet", contact_unlinked: "Kontaktzuordnung entfernt", contact_updated: "Kontakt aktualisiert", draft_review_begin: "Entwurfsprüfung begonnen", draft_review_check: "Prüfvermerk gespeichert", draft_review_approve: "Eigene Freigabe gespeichert", draft_review_reopen: "Entwurfsprüfung wieder geöffnet", case_created: "Akte angelegt", case_updated: "Stammdaten aktualisiert", document_uploaded: "Dokument hinzugefügt", draft_created: "Entwurf erstellt", draft_updated: "Entwurf bearbeitet", task_created: "Aufgabe angelegt", task_updated: "Aufgabe bearbeitet", task_completed: "Aufgabe erledigt", task_reopened: "Aufgabe wieder geöffnet", task_deleted: "Aufgabe gelöscht", document_deleted: "Dokument gelöscht", draft_deleted: "Entwurf gelöscht", draft_sent: "Entwurf per E-Mail versendet", research_answer: "KI-Rechercheantwort gespeichert", document_extracted: "Dokumentauslesen bearbeitet", document_text_reviewed: "Dokumenttext geprüft", document_text_unreviewed: "Dokumenttext ohne Freigabe gespeichert" },
  en: { inbox_corrected: "Incoming assignment corrected", document_ocr: "Local OCR processed", route_plan_saved: "Procedural route plan saved", case_archived: "Case archived", case_restored: "Case restored from archive", cost_review_saved: "Cost review saved", inbox_assigned: "Incoming file assigned to case", contact_linked: "Contact linked", contact_unlinked: "Contact unlinked", contact_updated: "Contact updated", draft_review_begin: "Draft review started", draft_review_check: "Review note saved", draft_review_approve: "User approval saved", draft_review_reopen: "Draft review reopened", case_created: "Case opened", case_updated: "Particulars updated", document_uploaded: "Document added", draft_created: "Draft created", draft_updated: "Draft edited", task_created: "Task created", task_updated: "Task edited", task_completed: "Task completed", task_reopened: "Task reopened", task_deleted: "Task deleted", document_deleted: "Document deleted", draft_deleted: "Draft deleted", draft_sent: "Draft sent by email", research_answer: "AI research answer saved", document_extracted: "Document extraction processed", document_text_reviewed: "Document text reviewed", document_text_unreviewed: "Document text saved without approval" },
};

export function localToday(value = new Date()) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export function dateLabel(value, lang, includeTime = false) {
  if (!value) return "—";
  const date = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  const options = {
    timeZone: "Europe/Berlin",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  };
  return includeTime ? date.toLocaleString(lang === "de" ? "de-DE" : "en-GB", options) : date.toLocaleDateString(lang === "de" ? "de-DE" : "en-GB", options);
}

// Typed dates: German TT.MM.JJJJ (English UI DD/MM/YYYY); the API keeps ISO YYYY-MM-DD.
export function formatDateInput(iso, lang) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!match) return "";
  return lang === "de" ? `${match[3]}.${match[2]}.${match[1]}` : `${match[3]}/${match[2]}/${match[1]}`;
}

export function parseDateInput(text) {
  const value = (text || "").trim();
  if (!value) return "";
  let day, month, year;
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value);
  const local = /^(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})$/.exec(value);
  if (iso) [, year, month, day] = iso.map(Number);
  else if (local) {
    [, day, month, year] = local.map(Number);
    if (year < 100) year += 2000;
  } else return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
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
