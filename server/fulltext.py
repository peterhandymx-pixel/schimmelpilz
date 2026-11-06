"""Full-text search across the firm's files: particulars, document text page by page, drafts, tasks, contacts, research.

Every word of the query must occur in the same item (case, umlauts and ß/ss are ignored). Results are grouped by file,
carry a short excerpt and a target (tab) to open. Only files the user may see are searched. The query travels in the
request body, never in the URL, so names and IBANs do not end up in logs.
"""
import json
import re
import unicodedata

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

LIMIT_PER_CASE, LIMIT_CASES = 6, 40
DETAIL_LABELS = {"client_name": "Mandant", "opponent_name": "Gegner", "opponent_reference": "Az. Gegenseite", "court": "Gericht", "court_reference": "Az. Gericht",
                 "client_address": "Anschrift Mandant", "opponent_address": "Anschrift Gegner", "client_email": "E-Mail Mandant", "insurer_name": "Rechtsschutz",
                 "insurer_policy": "Versicherungsnummer", "insurer_claim": "Schadennummer", "objective": "Ziel", "responsible": "Sachbearbeitung", "deadline_note": "Fristnotiz"}


def fold(text: str) -> str:
    """Lower case without accents; ß -> ss; ä/ö/ü and ae/oe/ue alike. Same length is not kept, so matching uses folded copies."""
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char)).replace("ß", "ss")
    return text.replace("ae", "a").replace("oe", "o").replace("ue", "u")


def compact(text: str) -> str:
    # Markdown marks from AI answers (### **) and citation markers ([L1]) are noise in an excerpt.
    text = re.sub(r"\[(?:L|R)\d+\]|[#*_`]+", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def excerpt(text: str, words: list[str], width: int = 90) -> str:
    """A short passage around the first hit; located on a folded copy built character by character to keep positions."""
    plain = compact(text)
    folded_chars, index = [], []
    for position, char in enumerate(plain):
        piece = fold(char)
        folded_chars.append(piece)
        index.extend([position] * len(piece))
    folded = "".join(folded_chars)
    first = min((folded.find(word) for word in words if folded.find(word) >= 0), default=-1)
    start = index[first] if 0 <= first < len(index) else 0
    left, right = max(0, start - width), min(len(plain), start + width)
    return ("… " if left else "") + plain[left:right] + (" …" if right < len(plain) else "")


def matches(text: str, words: list[str]) -> bool:
    folded = fold(compact(text))
    return all(word in folded for word in words)


def search(connection, user: dict, query: str) -> dict:
    words = [fold(word) for word in re.findall(r"[^\s]+", query) if len(fold(word)) >= 2][:8]
    if not words:
        return {"query": query, "groups": [], "total": 0}
    allowed = user.get("allowed_cases")
    cases = {row["id"]: row for row in connection.execute("SELECT id, reference, title, description, details, archived_at FROM cases WHERE user_id = ?", (user["id"],))
             if allowed is None or row["id"] in allowed}
    hits: dict[str, list] = {}

    def add(case_id, kind, label, text, tab, target=None):
        if case_id in cases and len(hits.setdefault(case_id, [])) < LIMIT_PER_CASE:
            hits[case_id].append({"kind": kind, "label": label, "excerpt": excerpt(text, words), "tab": tab, "target": target})

    for case_id, row in cases.items():
        details = json.loads(row["details"] or "{}")
        particulars = [row["reference"], row["title"], row["description"]] + [str(details.get(key) or "") for key in DETAIL_LABELS]
        if matches(" ".join(particulars), words):
            labelled = " · ".join(f"{DETAIL_LABELS[key]}: {details[key]}" for key in DETAIL_LABELS if details.get(key) and matches(str(details[key]), words[:1]))
            add(case_id, "case", "Aktendaten", labelled or f"{row['reference']} · {row['title']} · {row['description']}", "overview")
    for row in connection.execute("""SELECT d.id, d.case_id, d.original_name, p.unit_no, COALESCE(p.reviewed_text, p.original_text) AS text
                                     FROM documents d LEFT JOIN document_pages p ON p.document_id = d.id
                                     WHERE d.case_id IN (SELECT id FROM cases WHERE user_id = ?) AND d.inbox_reassigned_at IS NULL ORDER BY d.created_at, p.unit_no""", (user["id"],)):
        text = f"{row['original_name']} {row['text'] or ''}"
        if matches(text, words):
            add(row["case_id"], "document", f"{row['original_name']}" + (f", S. {row['unit_no']}" if row["unit_no"] else ""), row["text"] or row["original_name"], "documents", row["id"])
    for row in connection.execute("SELECT id, case_id, kind, recipient, body FROM drafts WHERE case_id IN (SELECT id FROM cases WHERE user_id = ?)", (user["id"],)):
        if matches(f"{row['recipient']} {row['body']}", words):
            add(row["case_id"], "draft", "Schriftsatz" + (f" an {compact(row['recipient']).split(' ')[0]}" if row["recipient"] else ""), row["body"], "drafts", row["id"])
    for row in connection.execute("SELECT id, case_id, title, note, due_on FROM tasks WHERE case_id IN (SELECT id FROM cases WHERE user_id = ?)", (user["id"],)):
        if matches(f"{row['title']} {row['note']}", words):
            add(row["case_id"], "task", "Frist/Aufgabe" + (f" {row['due_on']}" if row["due_on"] else ""), f"{row['title']} {row['note']}", "tasks", row["id"])
    for row in connection.execute("SELECT id, case_id, question, answer FROM research_runs WHERE status = 'completed' AND case_id IN (SELECT id FROM cases WHERE user_id = ?)", (user["id"],)):
        if matches(f"{row['question']} {row['answer']}", words):
            add(row["case_id"], "research", "Recherche: " + compact(row["question"])[:60], f"{row['question']} {row['answer']}", "research", row["id"])
    contacts = []
    for row in connection.execute("SELECT id, name, address, email, phone, note FROM contacts WHERE user_id = ?", (user["id"],)):
        if matches(" ".join(str(row[key] or "") for key in ("name", "address", "email", "phone", "note")), words):
            contacts.append({"id": row["id"], "name": row["name"], "excerpt": excerpt(" · ".join(str(row[key] or "") for key in ("address", "email", "phone", "note")) or row["name"], words)})
    groups = [{"case_id": case_id, "reference": cases[case_id]["reference"], "title": cases[case_id]["title"], "archived": bool(cases[case_id]["archived_at"]), "hits": items}
              for case_id, items in hits.items()]
    groups.sort(key=lambda group: (group["archived"], -len(group["hits"]), group["reference"]))
    return {"query": query, "groups": groups[:LIMIT_CASES], "contacts": contacts[:20], "total": sum(len(group["hits"]) for group in groups) + len(contacts)}


class SearchQuery(BaseModel):
    q: str = Field(min_length=2, max_length=200)


def router(db, require_user):
    routes = APIRouter()

    @routes.post("/api/search")
    def fulltext_search(payload: SearchQuery, user: dict = Depends(require_user)):
        with db() as connection:
            return search(connection, user, payload.q)

    return routes
