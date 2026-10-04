import assert from "node:assert/strict";
import test from "node:test";
import { caseMatches, localToday, partyRows, taskRows } from "../src/workbench.js";
import { researchBrief } from "../src/legalWorkflows.js";

test("parties merge only when name, role and contact particulars match", () => {
  const cases = [
    { id: "a", details: { client_name: "Test Person", client_address: "Address one", opponent_name: "Other Person" } },
    { id: "b", details: { client_name: "test person", client_address: "Address one", opponent_name: "Test Person" } },
    { id: "c", details: { client_name: "Test Person", client_address: "Address two", opponent_name: "Other Person" } },
  ];
  const rows = partyRows(cases);
  assert.equal(rows.length, 5);
  assert.deepEqual(rows.find(row => row.address === "Address one").cases.map(item => item.id), ["a", "b"]);
});

test("pending tasks sort by date and priority before completed tasks; undated last", () => {
  const rows = taskRows([{ id: "a", tasks: [
    { id: "done", due_on: "2020-01-01", completed: true },
    { id: "no-date", due_on: null, priority: "high", completed: false },
    { id: "normal", due_on: "2026-10-08", priority: "normal", completed: false },
    { id: "high", due_on: "2026-10-08", priority: "high", completed: false },
  ] }]);
  assert.deepEqual(rows.map(row => row.id), ["high", "normal", "no-date", "done"]);
  assert.equal(rows[0].caseItem.id, "a");
});

test("search combines terms across case particulars including court reference", () => {
  const item = { reference: "AZ-2026", title: "Mietvertrag Berlin", details: { client_name: "Test Person", court_reference: "12 O 345/26" } };
  assert.equal(caseMatches(item, " berlin  Test "), true);
  assert.equal(caseMatches(item, "345/26"), true);
  assert.equal(caseMatches(item, "Unknown"), false);
  assert.equal(localToday(new Date(2026, 9, 4, 0, 10)), "2026-10-04");
});

test("research working papers keep reference types distinct and declare unfinished review", () => {
  const item = { reference: "INTERNAL-42", title: "Test case", description: "A synthetic case description.", details: { jurisdiction: "MX", court_reference: "COURT-7", opponent_reference: "OTHER-9" } };
  for (const lang of ["de", "en"]) {
    const body = researchBrief(item, lang, "jurisdiction");
    assert.ok(body.includes("INTERNAL-42"));
    assert.ok(body.includes("COURT-7"));
    assert.ok(body.includes("OTHER-9"));
    assert.ok(body.includes("MX"));
    assert.ok(body.includes(lang === "de" ? "keine automatische Analyse durchgeführt" : "no automatic analysis has been performed"));
  }
  assert.throws(() => researchBrief(item, "de", "unknown"));
});
