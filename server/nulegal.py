"""Case law and citation checks from nu:legal Deutsches Recht (recht.nulegal.eu, free, keyless, read-only).

Terms of use: no personal data in requests (no names, no case facts), cache answers, identify the client.
Every query sent from here is therefore built from statute headings, our own letter-kind labels and a
fixed legal vocabulary, and the citation check sends only citation strings extracted by pattern.
"""
import json
import os
import re
import sys
import threading
import time
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE_URL = os.getenv("NULEGAL_BASE_URL", "https://recht.nulegal.eu").rstrip("/")
TIMEOUT = 8
CACHE_SECONDS = 3600
_cache, _lock = {}, threading.Lock()


def enabled():
    # Off under the test runner unless a test patches it on; NULEGAL=off disables it on a server.
    if "pytest" in sys.modules and not os.getenv("NULEGAL_IN_TESTS"):
        return False
    return os.getenv("NULEGAL", "on").strip().lower() not in ("off", "0", "false", "no")


def user_agent():
    contact = os.getenv("OPERATOR_EMAIL", "").strip() or os.getenv("PUBLIC_APP_URL", "").strip()
    return "Schimmelpilz-Rechtsassistentin/1.0" + (f" (+{contact})" if contact else "")


def _call(method, path, params=None, body=None):
    url = BASE_URL + path + ("?" + urlencode(params) if params else "")
    key = (method, url, json.dumps(body, sort_keys=True) if body is not None else "")
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"User-Agent": user_agent(), "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(Request(url, data=data, headers=headers, method=method), timeout=TIMEOUT) as response:
        value = json.loads(response.read(2 * 1024 * 1024))
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = (time.time() + CACHE_SECONDS, value)
    return value


def _decision(item, attribution=None):
    snippet = (item.get("snippet") or item.get("leitsatz") or "").strip()
    return {"court": item.get("court", ""), "decided": item.get("decided", ""), "aktenzeichen": item.get("aktenzeichen", ""),
            "kind": item.get("doktyp") or "", "snippet": snippet[:420], "url": item.get("url", ""),
            "attribution": item.get("attribution") or attribution or ""}


def case_search(query, limit=4):
    """Decisions for a legal search phrase (never user text)."""
    if not enabled() or len(query.strip()) < 2:
        return []
    try:
        result = _call("GET", "/v1/case-search", {"q": query.strip()[:200], "limit": max(1, min(limit, 10))})
    except (URLError, OSError, TimeoutError, ValueError):
        return []
    attribution = (result.get("source") or {}).get("attribution")
    return [_decision(item, attribution) for item in result.get("results") or [] if isinstance(item, dict) and item.get("aktenzeichen")]


def norm_key(title):
    """'§ 536 BGB · Mietminderung …' -> ('BGB', '536', 'Mietminderung …')."""
    match = re.match(r"§+\s*(\d+[a-z]?)\s+(.+?)\s+·\s+(.+)", title or "")
    return (match.group(2), match.group(1), match.group(3)) if match else None


def case_law_for(norm_titles, keywords=(), limit=4):
    """Leading decisions for the statutes found, searched by their heading plus fixed legal keywords."""
    found, seen = [], set()
    for title in norm_titles[:2]:
        parts = norm_key(title)
        if not parts:
            continue
        law, number, heading = parts
        # Short phrases rank best: the everyday legal term first, then the key word of the heading.
        query = " ".join([*keywords, *[word for word in re.findall(r"[^\W\d_]+", heading) if len(word) > 4][:1]]) if keywords else f"{heading} § {number} {law}"
        for item in case_search(query, limit=3):
            if item["aktenzeichen"] not in seen:
                seen.add(item["aktenzeichen"]); found.append(item)
    for index, item in enumerate(found[:limit], 1):
        item["citation_id"] = f"R{index}"
    return found[:limit]


NORM_PATTERN = re.compile(r"§§?\s*\d+[a-z]?(?:\s+(?:Abs\.|Absatz)\s*\d+[a-z]?)?(?:\s+(?:S\.|Satz)\s*\d+)?(?:\s+Nr\.\s*\d+[a-z]?)?(?:\s+(?:lit\.|Buchst\.)\s*[a-z])?\s+(?!(?:Abs|Absatz|Satz|Nr|Buchst|lit)\b)(?:[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]{1,11})(?:\s+[IVX]{1,4}\b)?")
DOCKET_PATTERN = re.compile(r"\b(?:BGH|BAG|BVerwG|BVerfG|BFH|BSG|OLG\s+[A-ZÄÖÜ][\wäöüß-]+|LG\s+[A-ZÄÖÜ][\wäöüß-]+|AG\s+[A-ZÄÖÜ][\wäöüß-]+)?[,\s]*(?:(?:Urteil|Beschluss)\s+vom\s+\d{1,2}\.\d{1,2}\.\d{4}\s*[–-]\s*)?"
                            r"(?:[IVX]{1,5}[a-z]?|\d{1,3})\s+(?:[A-Z][A-Za-z]{0,4})\s+\d{1,5}/\d{2}\b")


def extract_citations(text):
    """Statute and docket citations as a model writes them; nothing else from the answer leaves the server."""
    found = []
    for match in [*NORM_PATTERN.finditer(text or ""), *DOCKET_PATTERN.finditer(text or "")]:
        value = re.sub(r"\s+", " ", match.group(0)).strip(" ,")
        if value not in found:
            found.append(value)
    return found[:40]


def check_citations(text):
    """Each citation in an answer, with whether nu:legal knows it: resolved, unknown, ambiguous …"""
    citations = extract_citations(text)
    if not enabled() or not citations:
        return []
    try:
        result = _call("POST", "/v1/resolve", body={"citations": citations})
    except (URLError, OSError, TimeoutError, ValueError):
        return []
    checked = []
    for item in result.get("results") or []:
        if not isinstance(item, dict):
            continue
        check = item.get("citation_check") or {}
        mismatch = check and (check.get("court_matches") is False or check.get("date_matches") is False)
        checked.append({"citation": item.get("input", ""), "kind": item.get("citation_kind", ""), "status": "mismatch" if mismatch else item.get("status", "unknown"),
                        "url": item.get("url") or "", "actual_date": check.get("actual_date") or "", "actual_court": check.get("actual_court") or ""})
    return checked


def law_url(law, ref):
    return f"{BASE_URL}/gesetze/{quote(law)}/{quote(ref)}"
