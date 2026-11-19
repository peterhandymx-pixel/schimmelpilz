"""Letter assistant regression check: realistic letters through the real reading path (rules + configured AI).

Run before every update:  .venv\\Scripts\\python.exe -m server.check_letters   (optional: ids)
Per letter it checks the recognised letter kind, the legal area, the norm of the computed deadline and the court a claim
would go to (None where an objection, not a claim, is the remedy). Throw-away database, synthetic letters only.
"""
import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

CHECKS = Path(__file__).with_name("letter_checks.json")
CLIENT = {"client_address": "Max Beispiel\nTeststraße 1\n50667 Köln", "opponent_address": "Gegenseite\nDomstraße 3\n50668 Köln", "dispute_value": 2500}


def main(selected):
    from fastapi.testclient import TestClient
    from server import app as api, court_lookup

    checks = [item for item in json.loads(CHECKS.read_text(encoding="utf-8")) if not selected or item["id"] in selected]
    failures = 0
    with TemporaryDirectory() as folder:
        api.DATA_DIR = Path(folder); api.UPLOAD_DIR = api.DATA_DIR / "uploads"; api.DB_PATH = api.DATA_DIR / "app.db"
        with TestClient(api.app) as client:
            client.headers["X-Schimmelpilz-Request"] = "1"
            account = {"email": "letter-check@example.invalid", "password": "Synthetic-check-password-2026!", "audience": "consumer", "full_name": "Max Beispiel",
                       "street": "Teststraße 1", "postal_code": "50667", "city": "Köln", "country": "Deutschland"}
            if client.post("/api/auth/register", json=account).status_code not in (200, 201):
                print("Registrierung des Prüfkontos fehlgeschlagen"); return 2
            print(f"Modell: {api.ai_status().get('provider')} / {api.AI_MODEL}\n")
            for number, item in enumerate(checks):
                if number:
                    time.sleep(5)  # free API tiers limit requests per minute
                problems = []
                read = client.post("/api/letter-assistant/analyze", json={"text": item["text"], "use_ai": True})
                if read.status_code != 200:
                    print(f"FEHLER  {item['id']:<20} Lesen: HTTP {read.status_code}"); failures += 1; continue
                data = read.json()
                kind, area = data["kind"]["id"], data["kind"].get("legal_area")
                if kind not in item["kind"]:
                    problems.append(f"Briefart {kind}, erwartet {' / '.join(item['kind'])}")
                if item["area"] and area != item["area"]:
                    problems.append(f"Rechtsgebiet {area}, erwartet {item['area']}")
                fields = {**data["fields"], "legal_area": area}
                outcome = client.post("/api/letter-assistant/evaluate", json={"kind": kind, "fields": fields, "answers": {"received_on": "2026-11-04"}}).json()
                deadline = outcome.get("deadline") or {}
                if item["norm"] and item["norm"] not in (deadline.get("norm") or ""):
                    problems.append(f"Frist-Norm „{deadline.get('norm') or '—'}“, erwartet mit {item['norm']}")
                court = court_lookup.suggest(CLIENT, area)
                court_name = court.get("court", "") if court.get("ok") else None
                if item["court"] is None and court_name:
                    problems.append(f"Gericht {court_name.split(',')[0]} – erwartet: keine Klage (Einspruch)")
                elif item["court"] and not (court_name or "").startswith(item["court"]):
                    problems.append(f"Gericht {(court_name or court.get('message', '—')).split(',')[0][:60]}, erwartet {item['court']}")
                summary = f"{kind} · {area} · Frist {deadline.get('date', '—')} ({deadline.get('norm', '—')}) · {(court_name or 'kein Gericht').split(',')[0]}"
                print(("OK    " if not problems else "FEHLER") + f"  {item['id']:<20} {summary}" + ("" if data.get("ai") else "  [ohne KI gelesen]"))
                for problem in problems:
                    print("        - " + problem)
                failures += bool(problems)
    print(f"\n{len(checks) - failures} von {len(checks)} Prüfbriefen bestanden.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(set(sys.argv[1:])))
