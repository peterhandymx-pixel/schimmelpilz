import assert from "node:assert/strict";
import test from "node:test";
import { dateLabel, formatDateInput, parseDateInput } from "../src/workbench.js";

test("German date labels always use two-digit day and month", () => {
  assert.equal(dateLabel("2026-11-05", "de"), "05.11.2026");
  assert.equal(dateLabel("2026-11-05", "en"), "05/11/2026");
  assert.equal(dateLabel(null, "de"), "—");
});

test("typed dates accept German input and keep ISO for the API", () => {
  assert.equal(formatDateInput("2026-11-05", "de"), "05.11.2026");
  assert.equal(formatDateInput("2026-11-05", "en"), "05/11/2026");
  for (const typed of ["05.11.2026", "5.11.2026", "5.11.26", "05/11/2026", "2026-11-05"]) assert.equal(parseDateInput(typed), "2026-11-05", typed);
  assert.equal(parseDateInput(""), "");
  for (const invalid of ["31.02.2026", "11/31/2026", "morgen", "2026-13-01", "05.11"]) assert.equal(parseDateInput(invalid), null, invalid);
});
