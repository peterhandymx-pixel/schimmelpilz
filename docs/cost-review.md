# Kostenprüfung / Cost review

Available in the authenticated sidebar/module launcher and the Kostenprüfung tab of each case. Enter a title, invoice type, issuer, date, number, currency and manual items. Link an existing owned case document and record evidence pages, fee codes, contractual basis, table version and unresolved legal questions.

Each line uses **net unit amount × quantity or multiplier**. Optional billed net amounts are compared with recalculated line amounts. Net lines round half-up to cents. Tax is calculated on the sum of rounded net lines within each tax-rate group, rounded half-up to cents. Gross advances/credits are deducted afterwards. Tax-affecting credits belong in negative net lines with the relevant entered tax rate. The invoice's payable amount is compared with calculated payable; a positive difference means the invoice asks for more. A line difference can remain even when total differences cancel.

Use comma or decimal point without thousands separators in the UI. API numeric fields are decimal strings; currency amounts for totals have at most two decimal places, line price/quantity/tax rate at most four. EUR/USD/MXN are display/accounting currencies, with no currency conversion or inferred jurisdiction. Enter rates explicitly; zero is the initial value, not a finding of tax exemption.

“Nachrechnen” calculates without saving. “Prüfung zur Akte speichern” recalculates on the server, stores the inputs/result and creates an immutable version. Updates require the expected version and cannot move a saved review to another case. Case and document ownership are enforced. Saved PDFs can be downloaded per version. Editing inputs hides the previous calculation and its report/draft controls until a new calculation/save. The saved list still offers the original versions.

“Klärungsanschreiben entwerfen” opens the existing draft editor with saved invoice figures and evidence references. Choose/complete the recipient, review the text and save it separately. No correspondence is dispatched. PDF reports are calculation working papers, independent of the letter-paper export used for correspondence.

## Scope

This is arithmetic based on manual inputs. It does not extract invoices automatically, calculate statutory fee tables, choose the applicable law, assess fee entitlement, confirm tax applicability, allocate operating costs or find objection deadlines. Other rounding conventions may produce a different tax total and must be considered separately. “Arithmetic matches” does not establish legal validity or completeness of the invoice.

For lawyer invoices verify the relevant value, fee code, multiplier, agreement, credits and applicable statutory version. Current primary references checked on 2026-10-12: [RVG § 13](https://www.gesetze-im-internet.de/rvg/__13.html) (value fees), [RVG § 60](https://www.gesetze-im-internet.de/rvg/__60.html) (transition rules). Invoice date alone does not establish which fee version applies. Court demands require their own applicable [GKG](https://www.gesetze-im-internet.de/gkg_2004/) / [FamGKG](https://www.gesetze-im-internet.de/famgkg/) basis. No fee-table amounts are embedded in this module.

## Validation

Five dedicated backend tests cover decimal/tax-group rounding, negative taxable credits, multipliers, gross advances, item and total differences, invalid/nonfinite/oversized input, private case/document links, restart persistence, concurrent-edit conflicts, immutable versions, historical PDF content and case activity. Browser QA uses only synthetic data in `data/desk-preview`.
