import test from "node:test";
import assert from "node:assert/strict";
import { documentTemplate } from "../src/draftTemplates.js";

const matter = { reference: "24/2026-MÜ", title: "Synthetischer Test", description: "Die konkreten Falldaten stehen hier.", details: { client_name: "Testperson", client_address: "Teststraße 1", opponent_name: "Gegenseite", court_reference: "12 O 123/26", objective: "Einen Vertrag prüfen", dispute_value: 1250.50, currency: "EUR" } };

test("claim uses file facts but requires actual relief and verified grounds", () => {
  const text = documentTemplate(matter, "de", "claim", "Testgericht\nTeststraße 2");
  assert.match(text, /Unser Aktenzeichen: 24\/2026-MÜ/);
  assert.match(text, /Gericht \/ Behörde: 12 O 123\/26/);
  assert.match(text, /Die konkreten Falldaten stehen hier/);
  assert.match(text, /\[Bestimmten Klageantrag/);
  assert.match(text, /Streitwert ist nicht automatisch die Klageforderung/);
  assert.match(text, /Testgericht\nTeststraße 2/);
});

test("respondent is not silently relabelled claimant and missing amounts stay placeholders", () => {
  const text = documentTemplate({ ...matter, details: { client_role: "respondent" } }, "de", "claim");
  assert.match(text, /Rollen prüfen/);
  assert.match(text, /\[Wert ergänzen \/ klären\]/);
  assert.doesNotMatch(text, /1250/);
});

test("all correspondence types support any recipient and both working languages", () => {
  for (const language of ["de", "en"]) for (const kind of ["letter", "application", "objection", "response"]) {
    const text = documentTemplate(matter, language, kind, "Eine Behörde / Regierung");
    assert.match(text, /Eine Behörde \/ Regierung/);
    assert.match(text, /24\/2026-MÜ/);
    assert.match(text, /Einen Vertrag prüfen/);
    assert.match(text, /Die konkreten Falldaten stehen hier/);
    assert.ok(text.includes(language === "de" ? "Anlagen:" : "Attachments:"));
  }
});
