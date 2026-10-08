# Classic office workspace QA — 2026-10-07

Status: passed for the requested layout adaptation and tested navigation. This is a Schimmelpilz workspace inspired by the supplied classic office screenshot, not a reproduction of RA-MICRO's service integrations.

## Reference and comparison

Reference: user-supplied `codex-clipboard-b056eefe-dd3f-4abd-84b4-0f93415dbb2e.png`, 1914 × 1030. Compared side by side in the same inspection output with the authenticated Online Services implementation at a 1914 × 1030 viewport. The reference's native Windows title bar is excluded from the web implementation.

Evidence is saved locally under `C:/Users/Shadow/.codex/visualizations/2026/10/03/01a1032b-d071-7842-904b-5966af3494f6/`:

- `classic-office-2026-10-07.png`: final desktop comparison.
- `classic-office-mobile-2026-10-07.png`: 390 × 844.
- `classic-office-tablet-2026-10-07.png`: 900 × 900.

## Findings and fixes

1. P2 layout/color: older workspace rules initially expanded the sidebar to 248 px and retained the ivory background. Strengthened the scoped root selector; final DOM measurement is 198 px and RGB 249/249/250. Re-captured and compared against the source.
2. P2 mobile behavior: an inherited search order placed search below the account row. Reset order to zero; re-capture confirms search above the scrollable navigation. Mobile navigation targets have at least 44 px height.

## Final visual checks

- Layout/surfaces: narrow white sidebar, yellow search, pale selected navigation, light grey main surface, centered sans-serif heading and five-column/four-row desktop launcher. Tiles use open space rather than raised rounded cards.
- Typography/spacing: Source Sans 3, 42 px desktop heading, 21 px launcher labels and compact 12 px sidebar labels. This deliberately uses the project's existing font rather than an unknown proprietary desktop font. Long labels wrap without collisions at tablet/mobile widths.
- Icons/assets: consistent Tabler icon family, 62 px desktop/46 px mobile module icons and semantic colors. Original Schimmelpilz logo is retained with its aspect ratio. RA-MICRO/provider logos are replaced by our actual modules and official-source links; unavailable credit-check, payment, SMS and billing integrations are not presented as working tools.
- Responsive layout: five columns desktop, four tablet and two at 390 px. Document scroll width is 1899/885/375 px at viewport widths 1914/900/390 respectively, allowing the browser's vertical scrollbar without horizontal page overflow. Horizontal sidebar navigation is intentionally scrollable on mobile. Tablet and mobile screenshots were visually inspected.
- Accessibility: semantic buttons/links, named search field, current navigation state, bilingual labels, hidden decorative icons, retained skip link and visible CSS focus indicators. No new motion. Module controls have large practical hit areas. This is a focused browser review, not a comprehensive assistive-technology audit.
- Copy: internal modules open workspace tools; external tiles are identified as external links with a note explaining that they do not calculate fees or transmit case particulars. The initial workspace and Online Services share the module launcher; recent statistics/files remain available under Aktuelle Akten.

## Functional verification

Used only the isolated `data/desk-preview` account and synthetic case data on API 8002/web 4174.

- Reloaded the public preview and signed in successfully; no unreachable-sign-in banner.
- Opened Akten from a launcher tile; searched TEST-QUELLEN, reducing the register to its matching synthetic case; opened its details and existing case tabs.
- Opened E-Akte and verified stored document rows/download controls.
- Opened Schriftverkehr and verified saved draft versions and review status.
- Opened Recherche and verified the prominent local AI chat, selected synthetic case, existing history and source controls; no new legal answer was generated for this visual change.
- Opened new-case form and verified the choice between generating and retaining a reference, then closed without writing data.
- Switched DE → EN → DE and verified translated module labels.
- Inspected all ten external anchors: explicit official HTTPS destination, new-tab target, noreferrer, and no case-data query parameters. Provider availability/authentication is outside this layout check.
- Production build and all six existing frontend tests passed. The PowerShell launcher parsed without errors, a repeated launch reused the running preview services, and direct/API-proxy health endpoints responded. Independent services survived the launching command's completion.

No remaining P0/P1/P2 findings in the new launcher and exercised flows. The existing large-bundle build warning remains; billing, team permissions, OCR and automated legal review remain outside this change.
