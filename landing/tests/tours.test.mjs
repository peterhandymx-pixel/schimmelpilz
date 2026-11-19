import test from "node:test";
import assert from "node:assert/strict";
import { TOURS, toursFor } from "../src/tours.js";

test("each audience gets its tours; dictation only for law firms", () => {
  assert.deepEqual(toursFor("consumer").map(tour => tour.id), ["consumer"]);
  assert.deepEqual(toursFor("law_firm").map(tour => tour.id), ["first-firm", "dictation"]);
  assert.deepEqual(toursFor("business").map(tour => tour.id), ["first-business"]);
  assert.ok(!toursFor("business").some(tour => tour.steps.de.some(step => step.target === '[data-module="dictate"]')));
});

test("every tour exists in German and English with the same steps and ends with an action", () => {
  for (const tour of TOURS) {
    assert.equal(tour.steps.de.length, tour.steps.en.length, tour.id);
    tour.steps.de.forEach((step, index) => assert.equal(step.target, tour.steps.en[index].target, `${tour.id} ${index}`));
    assert.ok(tour.steps.de.at(-1).finish, tour.id);
    assert.ok(tour.steps.de.every(step => step.text.length < 420), tour.id);
  }
});
