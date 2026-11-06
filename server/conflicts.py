"""Conflict-of-interest search (§ 43a Abs. 4 BRAO): does a new client or opponent already appear in another file?

Matching is deliberately tolerant (case, umlauts, punctuation, legal forms, word order) and errs towards reporting:
a lawyer dismisses a false hit in seconds, a missed conflict can cost the mandate. Archived files count too.
"""
import json
import re
import unicodedata

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

LEGAL_FORMS = {"gmbh", "mbh", "ag", "kg", "ohg", "ug", "haftungsbeschrankt", "haftungsbeschrnkt", "ek", "ev", "gbr", "partg", "se", "co", "kgaa", "ltd", "inc", "llc", "sa",
               "und", "the", "fa", "firma", "herr", "frau", "dr", "prof"}
SIDES = {"client": "client", "opponent": "opponent"}


def tokens(name: str) -> list[str]:
    text = unicodedata.normalize("NFKD", (name or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char)).replace("ß", "ss")
    # "Müller" and "Mueller" are the same name: fold the transcribed umlaut too (applied to both sides alike).
    text = text.replace("ae", "a").replace("oe", "o").replace("ue", "u")
    words = re.findall(r"[a-z0-9]+", text)
    return [word for word in words if word not in LEGAL_FORMS and len(word) > 1]


def same_party(left: str, right: str) -> bool:
    """True when all words of the shorter name occur in the longer one (at least two words, or one word of 5+ letters)."""
    a, b = set(tokens(left)), set(tokens(right))
    if not a or not b:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if not short <= long:
        return False
    return len(short) >= 2 or len(next(iter(short))) >= 5


def search(connection, user, client: str, opponent: str, exclude_case: str = "") -> dict:
    """Hits for the new client and opponent; kind 'conflict' when they appear on the other side elsewhere."""
    parties = []  # (case row, side, name)
    rows = {row["id"]: row for row in connection.execute("SELECT id, reference, title, details, archived_at FROM cases WHERE user_id = ?", (user["id"],))}
    for row in rows.values():
        details = json.loads(row["details"] or "{}")
        if details.get("client_name"):
            parties.append((row, "client", details["client_name"]))
        if details.get("opponent_name"):
            parties.append((row, "opponent", details["opponent_name"]))
    for link in connection.execute("SELECT cc.case_id, cc.role, co.name FROM contact_cases cc JOIN contacts co ON co.id = cc.contact_id WHERE co.user_id = ?", (user["id"],)):
        if link["role"] in SIDES and link["case_id"] in rows:
            parties.append((rows[link["case_id"]], SIDES[link["role"]], link["name"]))
    allowed = user.get("allowed_cases")
    hits, seen = [], set()
    for searched_side, name in (("client", client), ("opponent", opponent)):
        if not tokens(name):
            continue
        for row, side, other in parties:
            key = (searched_side, row["id"], side)
            if row["id"] == exclude_case or key in seen or not same_party(name, other):
                continue
            seen.add(key)
            visible = allowed is None or row["id"] in allowed
            hits.append({
                "searched": searched_side, "name": other if visible else "", "side": side,
                "kind": "conflict" if side != searched_side else "known",
                "case_id": row["id"] if visible else None, "reference": row["reference"], "title": row["title"] if visible else "",
                "archived": bool(row["archived_at"]),
            })
    hits.sort(key=lambda hit: (hit["kind"] != "conflict", hit["reference"]))
    return {"hits": hits, "conflict": any(hit["kind"] == "conflict" for hit in hits)}


class ConflictQuery(BaseModel):
    client: str = Field(default="", max_length=160)
    opponent: str = Field(default="", max_length=160)
    exclude_case: str = Field(default="", max_length=64)


def router(db, require_user):
    routes = APIRouter()

    # POST, not GET: party names must not end up in URLs or access logs.
    @routes.post("/api/conflicts/check")
    def conflict_search(payload: ConflictQuery, user: dict = Depends(require_user)):
        with db() as connection:
            return search(connection, user, payload.client, payload.opponent, payload.exclude_case)

    return routes
