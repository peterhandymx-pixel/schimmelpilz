"""Expert working instructions from AI-Skills-German-Law (borghei, Apache-2.0 OR MIT), chosen per question.

Each of the 319 skills describes how a German lawyer works one topic (e.g. Mietminderung, Mahnverfahren).
The best-matching skill is handed to the model as working instructions, never as a verified source:
its statements carry the upstream legal state (October 2026) and its case citations may be unverified.
"""
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "law_skills" / "upstream"
LIMIT = 12000
_index, _lock = None, threading.Lock()

# Letter kinds of the letter assistant -> the skill that covers them.
KIND_SKILLS = {
    "mahnbescheid": "prozessrecht/mahnverfahren", "vollstreckungsbescheid": "prozessrecht/mahnverfahren",
    "klage": "prozessrecht/klageschrift-zivilprozess", "gerichtsvollzieher": "prozessrecht/zwangsvollstreckung-grundlagen",
    "pfaendung": "prozessrecht/zwangsvollstreckung-grundlagen", "inkasso": "vertragsrecht/verzug-mahnung",
    "zahlungsaufforderung": "vertragsrecht/verzug-mahnung", "kuendigung_wohnung": "mietrecht/eigenbedarfskuendigung",
    "mieterhoehung": "mietrecht/mieterhoehung-558-bgb", "betriebskosten": "mietrecht/betriebskostenabrechnung",
    "kuendigung_arbeit": "arbeitsrecht/kuendigungsschutzklage", "abmahnung_arbeit": "arbeitsrecht/abmahnung",
    "eigenkuendigung": "arbeitsrecht/kuendigungs-pruefung", "abmahnung_urheber": "urheber-medienrecht/urheberrechtsverletzung-abmahnung",
    "bussgeld": "verkehrsrecht/ordnungswidrigkeit-stvo", "anhoerung": "verkehrsrecht/ordnungswidrigkeit-stvo",
    "strafbefehl": "strafrecht/strafbefehl-pruefung", "steuerbescheid": "steuerrecht/einspruch-finanzamt",
    "betriebspruefung": "steuerrecht/aussenpruefung-betriebspruefung", "bescheid": "verwaltungsrecht/widerspruchsverfahren-vwgo",
    "versicherung_ablehnung": "versicherungsrecht/versicherungsfall-deckungspruefung",
}
# Case legal area -> the skill domains that fit it.
AREA_DOMAINS = {
    "tenancy": {"mietrecht", "wohnungseigentumsrecht"}, "employment": {"arbeitsrecht"}, "contract": {"vertragsrecht", "prozessrecht"},
    "consumer": {"vertragsrecht", "reise-fluggastrecht"}, "commercial": {"handelsrecht", "gesellschaftsrecht", "vertragsrecht"},
    "family": {"familienrecht", "erbrecht"}, "social": {"sozialrecht"}, "administrative": {"verwaltungsrecht"}, "criminal": {"strafrecht", "verkehrsrecht"},
}
NORM = re.compile(r"§+\s*(\d+[a-z]?)(?:\s+(?:Abs\.|S\.|Satz|Nr\.)\s*\S+)*\s+([A-Z][A-Za-z]{1,9})")
STOP = {"und", "oder", "der", "die", "das", "des", "für", "fuer", "bei", "nach", "use", "when", "rechtsstand", "oktober", "prüfung", "pruefung"}


def _fold(word):
    # Skill names spell umlauts as ae/oe/ue, questions use ä/ö/ü: both end up as plain vowels.
    word = word.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
    return word.replace("ae", "a").replace("oe", "o").replace("ue", "u")


def _stem(word):
    for suffix in ("ungen", "ung", "en", "er", "es", "e", "s", "n"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _words(text):
    return {_stem(_fold(word)) for word in re.findall(r"[^\W\d_]{4,}", text) if _fold(word) not in STOP}


def _frontmatter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    head = match.group(1) if match else ""
    name = re.search(r"^name:\s*(.+)$", head, re.M)
    description = re.search(r'^description:\s*"?(.*?)"?\s*$', head, re.M)
    return (name.group(1).strip() if name else ""), (description.group(1).strip() if description else ""), text[match.end():] if match else text


def _hit(term, word):
    # Compound words: "gebuhr" matches "gebuhrenberechn", "anwaltsvergut" matches "rechtsanwaltsvergut".
    return word.startswith(term) or (len(term) >= 6 and term in word) or (len(word) >= 6 and word in term)


def index():
    global _index
    with _lock:
        if _index is None:
            items = []
            for path in sorted(ROOT.glob("*/skills/*/SKILL.md")):
                name, description, _ = _frontmatter(path.read_text(encoding="utf-8"))
                domain = path.parts[-4]
                items.append({"id": f"{domain}/{path.parent.name}", "domain": domain, "name": name or path.parent.name, "description": description,
                              "words": _words(name.replace("-", " ") + " " + description), "name_words": _words(path.parent.name.replace("-", " ")),
                              "norms": {(number, law) for number, law in NORM.findall(description)}, "path": path})
            _index = items
    return _index


def find(skill_id):
    return next((item for item in index() if item["id"] == skill_id), None)


def select(question="", norm_titles=(), legal_area=None, kind=None):
    """The skill that best fits a question (by its legal terms and the statutes found) or a letter kind."""
    if kind and kind in KIND_SKILLS:
        return find(KIND_SKILLS[kind])
    from .legal_catalogue import question_terms
    terms = {_stem(_fold(term)) for term in question_terms(question)} if question else set()
    norms = set()
    for title in norm_titles:
        match = re.match(r"§+\s*(\d+[a-z]?)\s+(\S+)", title or "")
        if match:
            norms.add((match.group(1), match.group(2)))
    domains = AREA_DOMAINS.get(legal_area or "", set())
    best, best_score = None, 0
    for item in index():
        score = 4 * len(norms & item["norms"])
        score += sum(2 if any(_hit(term, word) for word in item["name_words"]) else 1 for term in terms if len(term) >= 4 and any(_hit(term, word) for word in item["words"]))
        if item["domain"] in domains:
            score += 2
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= 3 else None


def instructions(item, limit=LIMIT):
    """The skill's working text without frontmatter and agent wiring, cut at a section boundary."""
    _, _, body = _frontmatter(item["path"].read_text(encoding="utf-8"))
    body = re.sub(r"\n## Sub-Agent-Architektur\n.*?(?=\n## )", "\n", body, flags=re.S)
    if len(body) > limit:
        cut = body.rfind("\n## ", 0, limit)
        body = body[: cut if cut > limit // 2 else limit] + "\n\n[… gekürzt]"
    return body.strip()


def label(item):
    return {"id": item["id"], "name": item["name"], "title": re.split(r"\s[–-]\s|\.\s", item["description"], 1)[0][:140],
            "source": "AI-Skills-German-Law (borghei), Rechtsstand Oktober 2026",
            "url": f"https://github.com/borghei/AI-Skills-German-Law/tree/main/{item['domain']}/skills/{item['id'].split('/', 1)[1]}"}
