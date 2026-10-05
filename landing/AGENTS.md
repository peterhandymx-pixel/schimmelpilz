# Prototype Instructions

Product decisions: serve consumers, businesses and law firms (including legal research). Case intake should resemble a structured legal file, with a choice to generate or retain a file reference, separate court/opponent references, parties, legal area, objectives, procedural stage, dates and costs. Show concrete law/research/case-law/cost/jurisdiction/procedural capabilities and clearly identify implemented tools versus planned automatic analyses. Provide editable claim, application, objection and correspondence drafts for courts, authorities, law firms and other recipients. Keep the ivory, green and serif visual direction of the supplied mockup.

Registration/sign-in comes before real case creation. Collect account/contact data there; after sign-in show a separate software workspace with a sidebar and generous content area. Keep public mock-preview cards out of the authenticated workspace. The public German headline is: “Klarheit und die Wahrheit – damit Sie keine Angst mehr vor Großkanzleien haben müssen.”

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

The authenticated workspace should resemble law-office software: compact searchable file tables, global parties/documents/drafts/tasks registers, editable case particulars and per-case tabs for overview, parties, files, drafts, manual deadlines/tasks and activity. Keep internal references unchanged during edits. Research MUST contain the AI bot prominently, connected to the actual local model, with case selection, persistent account-owned history, German/English answers and adoption as editable drafts. Use the project-specific German-law skill workflows; distinguish local AI suggestions from verified legal sources. PDF text layers and DOCX body sections can now be extracted, corrected and explicitly selected after transcription review. Clearly state excerpt limits and preserve per-answer provenance. Do not claim OCR, complete file analysis or automatic internet research. Google Drive in the development chat is separate from website authentication.

Use the supplied Virtuelle Rechtsassistenz Schimmelpilz logo consistently on the landing page and workspace. It is bundled through BrandLogo rather than a separately requested public asset, so cached UI and missing asset requests cannot drop the brand mark.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.
