// A dictation "tape" in the browser: 16 kHz mono PCM with a cursor, like a classic dictation device.
// Recording at the cursor either overwrites what follows or inserts; playback starts at the cursor,
// and rewind / fast-forward move it sample-exact. The finished tape is uploaded as a 16-bit WAV.

export const TAPE_RATE = 16000;
const RECORDER_WORKLET = `
class TapeInput extends AudioWorkletProcessor {
  constructor() { super(); this.buffer = []; this.size = 0; }
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) { this.buffer.push(channel.slice(0)); this.size += channel.length; }
    if (this.size >= 2048) { const out = new Float32Array(this.size); let at = 0; for (const part of this.buffer) { out.set(part, at); at += part.length; } this.port.postMessage(out, [out.buffer]); this.buffer = []; this.size = 0; }
    return true;
  }
}
registerProcessor("tape-input", TapeInput);`;

export function formatTime(samples, rate = TAPE_RATE) {
  const total = Math.max(0, Math.floor(samples / rate));
  const hours = Math.floor(total / 3600), minutes = Math.floor(total / 60) % 60, seconds = total % 60;
  return `${hours ? `${hours}:${String(minutes).padStart(2, "0")}` : minutes}:${String(seconds).padStart(2, "0")}`;
}

// Reads a PCM WAV (as produced by encodeWav or any 16-bit recorder) into mono samples.
export function decodeWav(arrayBuffer) {
  const view = new DataView(arrayBuffer);
  const text = (at, length) => String.fromCharCode(...new Uint8Array(arrayBuffer, at, length));
  if (text(0, 4) !== "RIFF" || text(8, 4) !== "WAVE") throw new Error("wav_required");
  let at = 12, rate = TAPE_RATE, channels = 1, bits = 16, data = null;
  while (at + 8 <= view.byteLength) {
    const id = text(at, 4), size = view.getUint32(at + 4, true);
    if (id === "fmt ") { channels = view.getUint16(at + 10, true); rate = view.getUint32(at + 12, true); bits = view.getUint16(at + 22, true); }
    if (id === "data") { data = [at + 8, Math.min(size, view.byteLength - at - 8)]; break; }
    at += 8 + size + (size & 1);
  }
  if (!data || bits !== 16) throw new Error("pcm16_wav_required");
  const frames = Math.floor(data[1] / (2 * channels)), samples = new Int16Array(frames);
  for (let frame = 0; frame < frames; frame++) samples[frame] = view.getInt16(data[0] + frame * 2 * channels, true);
  return { samples, rate };
}

export function encodeWav(samples, rate = TAPE_RATE) {
  const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer);
  const write = (at, value) => { for (let index = 0; index < value.length; index++) view.setUint8(at + index, value.charCodeAt(index)); };
  write(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, samples.length * 2, true);
  new Int16Array(buffer, 44).set(samples);
  return new Blob([buffer], { type: "audio/wav" });
}

export class DictationTape {
  constructor({ samples = new Int16Array(0), rate = TAPE_RATE, onChange = () => {} } = {}) {
    this.rate = rate;
    this.data = new Int16Array(Math.max(samples.length, rate * 60));
    this.data.set(samples);
    this.length = samples.length;
    this.position = 0;
    this.state = "idle";       // idle | playing | recording
    this.mode = "overwrite";   // overwrite | insert
    this.speed = 1;
    this.level = 0;
    this.error = "";
    this.pending = null;       // samples recorded in insert mode, spliced in when recording stops
    this.onChange = onChange;
    this.context = null; this.stream = null; this.source = null; this.worklet = null; this.player = null;
  }

  get duration() { return this.length + (this.pending ? this.pending.length : 0); }
  get dirty() { return this.duration > 0; }
  // Where the cursor stands right now, including audio being inserted or played.
  get cursor() { return this.state === "recording" ? this.position + (this.pending ? this.pending.length : 0) : this.current(); }
  samples() { return this.data.subarray(0, this.length); }
  emit() { this.onChange(this); }

  async audio() {
    if (!this.context) this.context = new AudioContext();
    if (this.context.state === "suspended") await this.context.resume();
    return this.context;
  }

  ensure(size) {
    if (size <= this.data.length) return;
    const grown = new Int16Array(Math.max(size, this.data.length * 2));
    grown.set(this.data.subarray(0, this.length));
    this.data = grown;
  }

  // Microphone frames arrive at the device rate; they are averaged down to 16 kHz.
  take(frames, inputRate) {
    const ratio = inputRate / this.rate, count = Math.floor(frames.length / ratio);
    const converted = new Int16Array(count);
    let peak = 0;
    for (let index = 0; index < count; index++) {
      const from = Math.floor(index * ratio), to = Math.min(frames.length, Math.floor((index + 1) * ratio));
      let sum = 0; for (let at = from; at < to; at++) sum += frames[at];
      const value = Math.max(-1, Math.min(1, sum / Math.max(1, to - from)));
      peak = Math.max(peak, Math.abs(value));
      converted[index] = value < 0 ? value * 0x8000 : value * 0x7fff;
    }
    this.level = peak;
    if (this.mode === "insert") {
      const merged = new Int16Array(this.pending.length + count);
      merged.set(this.pending); merged.set(converted, this.pending.length); this.pending = merged;
    } else {
      this.ensure(this.position + count);
      this.data.set(converted, this.position);
      this.length = Math.max(this.length, this.position + count);
      this.position += count;
    }
    this.emit();
  }

  async record() {
    if (this.state === "recording") return;
    this.stop();
    this.error = "";
    if (!navigator.mediaDevices?.getUserMedia) { this.error = "insecure"; this.emit(); throw new Error(this.error); }
    const context = await this.audio();
    if (!this.stream) this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } }).catch(problem => { this.error = "microphone"; this.emit(); throw problem; });
    if (!this.worklet) {
      const url = URL.createObjectURL(new Blob([RECORDER_WORKLET], { type: "application/javascript" }));
      try { await context.audioWorklet.addModule(url); } finally { URL.revokeObjectURL(url); }
      this.worklet = new AudioWorkletNode(context, "tape-input");
      this.worklet.port.onmessage = event => { if (this.state === "recording") this.take(event.data, context.sampleRate); };
      // A silent path to the output keeps the browser pulling audio through the worklet.
      const silent = context.createGain(); silent.gain.value = 0;
      this.worklet.connect(silent).connect(context.destination);
    }
    this.source = context.createMediaStreamSource(this.stream);
    if (this.state === "playing") this.stop();
    this.source.connect(this.worklet);
    if (this.mode === "insert") this.pending = new Int16Array(0);
    this.state = "recording";
    this.emit();
  }

  finishRecording() {
    this.source?.disconnect(); this.source = null;
    if (this.pending) {
      const inserted = this.pending; this.pending = null;
      this.ensure(this.length + inserted.length);
      this.data.copyWithin(this.position + inserted.length, this.position, this.length);
      this.data.set(inserted, this.position);
      this.length += inserted.length;
      this.position += inserted.length;
    }
    this.level = 0;
  }

  current() {
    if (this.state !== "playing" || !this.player) return this.position;
    const moved = (this.context.currentTime - this.player.startedAt) * this.rate * this.speed;
    return Math.min(this.length, Math.round(this.player.from + moved));
  }

  async play() {
    if (this.state === "playing") return;
    this.stop();
    if (this.position >= this.length) this.position = 0;
    if (!this.length) return;
    const context = await this.audio();
    const part = this.data.subarray(this.position, this.length);
    const buffer = context.createBuffer(1, part.length, this.rate), channel = buffer.getChannelData(0);
    for (let index = 0; index < part.length; index++) channel[index] = part[index] / 0x8000;
    const node = context.createBufferSource();
    node.buffer = buffer; node.playbackRate.value = this.speed; node.connect(context.destination);
    this.player = { node, from: this.position, startedAt: context.currentTime };
    node.onended = () => { if (this.player?.node === node) { this.position = this.length; this.player = null; this.state = "idle"; this.emit(); } };
    node.start();
    this.state = "playing";
    this.emit();
  }

  stop() {
    if (this.state === "recording") this.finishRecording();
    if (this.state === "playing" && this.player) {
      this.position = this.current();
      const { node } = this.player; this.player = null;
      node.onended = null; try { node.stop(); } catch { /* already ended */ }
    }
    this.state = "idle";
    this.emit();
  }

  toggle() { if (this.state === "playing") this.stop(); else this.play(); }

  seek(samples) {
    const resume = this.state === "playing";
    this.stop();
    this.position = Math.max(0, Math.min(this.length, Math.round(samples)));
    this.emit();
    if (resume) this.play();
  }

  skip(seconds) { this.seek(this.current() + seconds * this.rate); }

  setMode(mode) { if (this.state !== "recording") { this.mode = mode; this.emit(); } }
  setSpeed(speed) { const resume = this.state === "playing"; this.stop(); this.speed = speed; this.emit(); if (resume) this.play(); }

  clear() { this.stop(); this.length = 0; this.position = 0; this.emit(); }
  wav() { this.stop(); return encodeWav(this.samples(), this.rate); }

  close() {
    this.stop();
    this.worklet?.disconnect(); this.worklet = null;
    this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
    this.context?.close().catch(() => {}); this.context = null;
  }
}

// Classic dictation keys. Holding F6 / F7 spools continuously (keyboard auto-repeat); playback
// pauses while spooling and resumes when the key is released, like a foot pedal.
export const DICTATION_KEYS = { F4: "stop", F5: "play", F6: "rewind", F7: "forward", F8: "record", Insert: "mode" };

export function bindDictationKeys(tape, { record = false, autoRewind = () => 0 } = {}) {
  let resumeAfterSpool = false;
  const down = event => {
    const action = DICTATION_KEYS[event.key];
    if (!action || (action === "record" && !record) || (action === "mode" && !record)) return;
    if (action === "mode" && /input|textarea|select/i.test(event.target?.tagName || "")) return;
    event.preventDefault();
    if (action === "play") {
      if (tape.state === "playing") { tape.stop(); const back = autoRewind(); if (back) tape.skip(-back); } else tape.play();
    } else if (action === "stop") tape.stop();
    else if (action === "record") { if (tape.state === "recording") tape.stop(); else tape.record().catch(() => tape.emit()); }
    else if (action === "mode") tape.setMode(tape.mode === "overwrite" ? "insert" : "overwrite");
    else {
      if (tape.state === "recording") return;
      if (tape.state === "playing") { resumeAfterSpool = true; tape.stop(); }
      tape.skip((action === "rewind" ? -1 : 1) * (event.repeat ? 1 : 2));
    }
  };
  const up = event => {
    if ((event.key === "F6" || event.key === "F7") && resumeAfterSpool) { resumeAfterSpool = false; tape.play(); }
  };
  window.addEventListener("keydown", down);
  window.addEventListener("keyup", up);
  return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
}
