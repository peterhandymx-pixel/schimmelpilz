# Source provenance

Upstream: https://github.com/borghei/AI-Skills-German-Law

Pinned commit: `6a3de501823e8a630a767f91951d50dbdd14e894`; retrieved 2026-10-04. This was found as a public source corresponding to the named package. The user-created Codex plugin itself did not expose readable skills in this session; installing this project package does not claim that plugin is connected.

Reviewed upstream materials:

- `prozessrecht/skills/klageschrift-zivilprozess/SKILL.md`: party/court/request/evidence structure and separate procedural review.
- `kostenrecht-rvg/skills/rvg-gebuehrenberechnung/SKILL.md`: distinction between legal fee/value judgments and deterministic arithmetic, table-version checks.
- `kostenrecht-rvg/agents/researcher.md`: source classification and explicit unverified-citation markers.
- `mietrecht/skills/betriebskostenabrechnung/SKILL.md`: separation of invoice inputs, evidence, formal/material questions and recalculation.
- `NOTICE` and `LICENSE-MIT`: upstream attribution and reuse permission.

The project-specific references are rewritten for Schimmelpilz's real data model, its three audiences, bilingual output, manual tools and local Ollama research chat. The backend supplies the selected workflow to the model as working instructions, not verified authority. Upstream legal values, example calculations and case citations are not imported as verified rules. No upstream scripts or agents have been installed or executed. The MIT option is used; the accompanying licence retains the upstream notice.

Google Drive was searched for `AI-Skills-German-Law`, `AI-Skills`, `German-Law` and `Schimmelpilz`. No matching skill package or Schimmelpilz source documents were identified. No private documents were copied into this repository.

Primary source entry points: [German federal law](https://www.gesetze-im-internet.de/), [EUR-Lex](https://eur-lex.europa.eu/), [federal decisions](https://www.rechtsprechung-im-internet.de/), [state/court decision directories](https://www.justiz.de/onlinedienste/rechtsprechung/index.php), [justice directories](https://www.justiz.de/service/verzeichnisse/index.php). Reading these entry points is not a complete legal verification. Every substantive case assessment must inspect the applicable text and cite the passage supporting its conclusion.

## Update 2026-11-05: full skill set at runtime

The complete upstream skill set (319 `SKILL.md` files, commit `b962266e0081baa39447899d633ce84b17083976`, retrieved 2026-11-05) is vendored under `server/law_skills/upstream/` together with `LICENSE`, `LICENSE-MIT`, `LICENSE-APACHE`, `NOTICE` and `skills.json` (Apache-2.0 OR MIT; the NOTICE is retained). `server/law_skills.py` picks the best-matching skill per research question (legal terms, statutes found, case legal area) or per letter kind and supplies it to the model as working instructions. The skill text is not treated as a verified source; its case citations are not cited unless the same decision is supplied by nu:legal, and every citation in an answer is checked there.
