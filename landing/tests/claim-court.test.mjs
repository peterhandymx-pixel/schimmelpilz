import test from "node:test";
import assert from "node:assert/strict";
import { documentTemplate } from "../src/draftTemplates.js";

const item = { reference: "SCH-1", title: "Kaufpreis", description: "Sachverhalt", details: { client_name: "A", opponent_name: "B", opponent_address: "Weg 1\n50667 Köln" } };

test("claim draft names the determined court and its jurisdiction", () => {
  const withCourt = { ...item, details: { ...item.details, court: "Amtsgericht Köln, Luxemburger Straße 101, 50939 Köln" } };
  const body = documentTemplate(withCourt, "de", "claim", "", { ok: true, name: "Amtsgericht Köln", basis: "Sachlich: Streitwert bis 10.000 € (§ 23 Nr. 1 GVG)." });
  assert.match(body, /Amtsgericht Köln\nLuxemburger Straße 101\n50939 Köln/);
  assert.match(body, /Das angerufene Gericht ist zuständig\. Sachlich: Streitwert bis 10\.000 €/);
});

test("claim draft says plainly what is missing instead of an empty court", () => {
  const body = documentTemplate(item, "de", "claim", "", { ok: false, message: "Die Anschrift der Gegenseite fehlt." });
  assert.match(body, /\[GERICHT FEHLT – Die Anschrift der Gegenseite fehlt\.\]/);
});

test("a claim against a social-security decision goes to the social court structure", () => {
  const social = { reference: "SCH-9", title: "Bescheid einer Behörde – Versorgungsamt Köln", description: "GdB zu niedrig festgesetzt.",
    details: { legal_area: "social", client_name: "Kläger", client_address: "Weg 1\n51371 Leverkusen", opponent_name: "Versorgungsamt Köln", opponent_reference: "447872077174-8-75", court: "Sozialgericht Köln, Blumenthalstraße 33, 50670 Köln" } };
  const body = documentTemplate(social, "de", "claim", "", { ok: true, area: "sozial", name: "Sozialgericht Köln", basis: "Sachlich: Rechtsweg zu den Sozialgerichten (§ 51 SGG)." });
  assert.match(body, /^Kläger\nWeg 1\n51371 Leverkusen\n\nAn das\nSozialgericht Köln/);
  assert.match(body, /Az\. der Behörde: 447872077174-8-75/);
  assert.match(body, /in Gestalt des Widerspruchsbescheids vom \[Datum\] aufzuheben/);
  assert.match(body, /§ 87 Abs\. 1, 2 SGG/);
  assert.match(body, /gerichtskostenfrei \(§ 183 SGG\)/);
  assert.doesNotMatch(body, /Streitwert|ZPO/);
});
