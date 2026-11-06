"""Research regression check: real questions through the real research path, against the configured AI.

Run before every update:  .venv\\Scripts\\python.exe -m server.check_research   (optional: ids, e.g. "gdb-ausland kaution")
Uses a throw-away database with a synthetic account; nothing touches the real data. Exit code 1 if a check fails.
Checks: the expected statutes were supplied as sources, required statements are in the answer, wrong ones are not.
"""
import json
import re
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

CHECKS = Path(__file__).with_name("research_checks.json")


def norm_found(norm, sources, answer):
    titles = [str(source.get("title", "")) for source in sources]
    return any(title == norm or title.startswith(norm + " ·") for title in titles) or re.search(re.escape(norm) + r"(?![0-9a-z])", answer) is not None


def main(selected):
    from fastapi.testclient import TestClient
    from server import app as api

    checks = [item for item in json.loads(CHECKS.read_text(encoding="utf-8")) if not selected or item["id"] in selected]
    failures = 0
    with TemporaryDirectory() as folder:
        api.DATA_DIR = Path(folder); api.UPLOAD_DIR = api.DATA_DIR / "uploads"; api.DB_PATH = api.DATA_DIR / "app.db"
        with TestClient(api.app) as client:
            client.headers["X-Schimmelpilz-Request"] = "1"
            account = {"email": "research-check@example.invalid", "password": "Synthetic-check-password-2026!", "audience": "law_firm", "full_name": "Synthetic Check", "organisation": "Prüfkanzlei (synthetisch)",
                       "street": "Testweg 1", "postal_code": "10115", "city": "Berlin", "country": "Deutschland"}
            if client.post("/api/auth/register", json=account).status_code not in (200, 201):
                print("Registrierung des Prüfkontos fehlgeschlagen"); return 2
            print(f"Modell: {api.ai_status().get('provider')} / {api.AI_MODEL}\n")
            for number, item in enumerate(checks):
                if number:
                    time.sleep(6)  # free API tiers limit requests per minute
                case = client.post("/api/cases", json={"title": "Prüffrage " + item["id"], "description": "Synthetische Prüfakte ohne Mandantendaten.",
                                                         "details": {"audience": "law_firm", "legal_area": item["area"]}}).json()
                body = {"request_id": str(uuid.uuid4()), "question": item["question"], "use_legal_catalogue": True}
                for attempt in range(3):
                    reply = client.post(f"/api/cases/{case['id']}/research", json=body)
                    if reply.status_code not in (429, 503) or attempt == 2:
                        break
                    body["request_id"] = str(uuid.uuid4()); time.sleep(20)
                problems = []
                if reply.status_code != 201:
                    problems.append(f"HTTP {reply.status_code}: {reply.text[:120]}")
                    run = {}
                else:
                    run = reply.json()
                answer, sources = run.get("answer", ""), run.get("legal_sources", [])
                if run and not any(norm_found(norm, sources, answer) for norm in item["norms_any"]):
                    problems.append("keine der erwarteten Normen: " + ", ".join(item["norms_any"]))
                for needed in item["answer_all"]:
                    if run and not re.search(needed, answer, re.IGNORECASE):
                        problems.append(f"fehlt in der Antwort: {needed}")
                for wrong in item["answer_none"]:
                    if run and wrong in answer:
                        problems.append(f"falsch in der Antwort: {wrong.strip()}")
                used = sorted({source["title"].split(" · ")[0] for source in sources})
                print(("OK    " if not problems else "FEHLER") + f"  {item['id']:<20} Quellen: {', '.join(used) or '—'}")
                for problem in problems:
                    print("        - " + problem)
                failures += bool(problems)
    print(f"\n{len(checks) - failures} von {len(checks)} Prüffragen bestanden.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(set(sys.argv[1:])))
