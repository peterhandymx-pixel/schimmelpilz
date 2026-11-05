import test from "node:test";
import assert from "node:assert/strict";
import { DictationTape, decodeWav, encodeWav, formatTime } from "../src/dictationTape.js";

// Feeds "microphone" frames at 16 kHz with a constant value, without a real audio device.
function speak(tape, value, samples) {
  tape.state = "recording";
  if (tape.mode === "insert" && !tape.pending) tape.pending = new Int16Array(0);
  tape.take(new Float32Array(samples).fill(value), 16000);
  tape.finishRecording();
  tape.state = "idle";
}
const values = tape => [...new Set(tape.samples())];

test("overwrite replaces from the cursor and keeps the rest", () => {
  const tape = new DictationTape();
  speak(tape, 0.5, 16000);
  tape.seek(4000);
  speak(tape, -0.5, 4000);
  assert.equal(tape.length, 16000);
  assert.equal(tape.position, 8000);
  assert.ok(tape.samples()[3999] > 0 && tape.samples()[4000] < 0 && tape.samples()[7999] < 0 && tape.samples()[8000] > 0);
});

test("insert pushes the rest back and overwrite past the end extends the tape", () => {
  const tape = new DictationTape();
  speak(tape, 0.5, 8000);
  tape.seek(2000); tape.setMode("insert");
  speak(tape, -0.5, 1000);
  assert.equal(tape.length, 9000);
  assert.equal(tape.position, 3000);
  assert.ok(tape.samples()[2999] < 0 && tape.samples()[3000] > 0);
  tape.setMode("overwrite"); tape.seek(9000);
  speak(tape, 0.25, 1000);
  assert.equal(tape.length, 10000);
});

test("rewind and fast-forward stay inside the tape; 48 kHz input is reduced to 16 kHz", () => {
  const tape = new DictationTape();
  tape.state = "recording"; tape.take(new Float32Array(48000).fill(0.1), 48000); tape.finishRecording(); tape.state = "idle";
  assert.equal(tape.length, 16000);
  tape.skip(-5); assert.equal(tape.position, 0);
  tape.skip(2); assert.equal(tape.position, 32000 > tape.length ? tape.length : 32000);
  assert.equal(formatTime(16000 * 75), "1:15");
  assert.equal(formatTime(16000 * 3725), "1:02:05");
});

test("WAV round trip", async () => {
  const tape = new DictationTape();
  speak(tape, 0.5, 1600);
  const blob = encodeWav(tape.samples());
  const { samples, rate } = decodeWav(await blob.arrayBuffer());
  assert.equal(rate, 16000);
  assert.deepEqual([...samples], [...tape.samples()]);
  assert.deepEqual(values(tape).length, 1);
});
