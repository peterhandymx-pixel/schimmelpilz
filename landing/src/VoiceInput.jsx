import { useEffect, useRef, useState } from "react";
import { IconLoader2, IconMicrophone, IconPlayerStopFilled } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";

const MAX_SECONDS = 300;
const DEVICE_KEY = "schimmelpilz.voice.device";
const SILENT = 0.012; // peak RMS below this means the microphone delivered no usable sound
const pickType = () => ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find(type => window.MediaRecorder?.isTypeSupported?.(type)) || "";
const remembered = () => { try { return localStorage.getItem(DEVICE_KEY) || ""; } catch { return ""; } };
const remember = id => { try { id ? localStorage.setItem(DEVICE_KEY, id) : localStorage.removeItem(DEVICE_KEY); } catch { /* storage blocked */ } };
export const voiceSupported = () => typeof window !== "undefined" && Boolean(window.MediaRecorder && navigator.mediaDevices?.getUserMedia);

// Microphone button: record with a live level meter, refuse silent takes, the server turns speech into text. Audio is not stored.
export function VoiceButton({ lang = "de", disabled, onText, onError, className = "" }) {
  const de = lang === "de";
  const [state, setState] = useState("idle"), [seconds, setSeconds] = useState(0), [level, setLevel] = useState(0);
  const [devices, setDevices] = useState([]), [deviceId, setDeviceId] = useState(remembered), [pick, setPick] = useState(false);
  const recorder = useRef(null), chunks = useRef([]), timer = useRef(null), stream = useRef(null), audio = useRef(null), peak = useRef(0), frame = useRef(0);

  const cleanup = () => {
    clearInterval(timer.current); clearInterval(frame.current);
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null;
    audio.current?.close?.().catch(() => {}); audio.current = null; setLevel(0);
  };
  useEffect(() => () => { if (recorder.current) recorder.current.onstop = null; if (recorder.current?.state === "recording") recorder.current.stop(); cleanup(); }, []);

  const loadDevices = async () => {
    try { setDevices((await navigator.mediaDevices.enumerateDevices()).filter(item => item.kind === "audioinput")); } catch { setDevices([]); }
  };

  const send = async blob => {
    setState("working");
    try {
      const form = new FormData();
      form.append("file", blob, "speech");
      form.append("language", lang === "en" ? "en" : "de");
      const result = await request("/speech/transcribe", { method: "POST", body: form });
      if (result.text) onText(result.text);
      else onError?.(de ? "Ich habe keine Sprache erkannt. Bitte deutlich und etwas näher am Mikrofon sprechen." : "No speech recognised. Please speak clearly and closer to the microphone.");
    } catch (error) {
      onError?.(error.status === 429 ? (de ? "Zu viele Spracheingaben in kurzer Zeit. Bitte kurz warten." : "Too many voice inputs. Please wait a moment.")
        : error.detail === "audio_too_short" ? (de ? "Die Aufnahme war zu kurz." : "The recording was too short.")
        : error.detail === "ai_paused_by_operator" ? (de ? "Die KI ist derzeit pausiert." : "AI is currently paused.")
        : (de ? "Spracheingabe fehlgeschlagen. Bitte erneut versuchen oder tippen." : "Voice input failed. Please try again or type."));
    } finally { setState("idle"); }
  };

  const meter = () => {
    const context = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    context.createMediaStreamSource(stream.current).connect(analyser);
    audio.current = context;
    // A suspended context reads zeros; then the meter cannot judge silence, so it must not block sending.
    context.resume?.().catch(() => {}).finally(() => { if (context.state !== "running") peak.current = 1; });
    const samples = new Float32Array(analyser.fftSize);
    const tick = () => {
      analyser.getFloatTimeDomainData(samples);
      const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
      peak.current = Math.max(peak.current, rms);
      setLevel(Math.min(1, rms * 8));
    };
    // A timer, not requestAnimationFrame: animation frames stop in background tabs and would fake silence.
    frame.current = setInterval(tick, 80);
  };

  const start = async () => {
    setPick(false); onError?.("");
    try {
      const constraints = { echoCancellation: true, noiseSuppression: true, autoGainControl: true, ...(deviceId ? { deviceId: { exact: deviceId } } : {}) };
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: constraints }).catch(error => {
        if (deviceId && error.name === "OverconstrainedError") { remember(""); setDeviceId(""); return navigator.mediaDevices.getUserMedia({ audio: true }); }
        throw error;
      });
    } catch {
      onError?.(de ? "Kein Zugriff auf das Mikrofon. Bitte im Browser (Schloss-Symbol in der Adresszeile) erlauben." : "No microphone access. Please allow it in the browser (lock icon in the address bar).");
      return;
    }
    loadDevices();
    const type = pickType();
    const rec = new MediaRecorder(stream.current, type ? { mimeType: type } : undefined);
    chunks.current = []; peak.current = 0;
    try { meter(); } catch { peak.current = 1; /* no meter available: do not block sending */ }
    rec.ondataavailable = event => event.data.size && chunks.current.push(event.data);
    rec.onstop = () => {
      const heard = peak.current;
      cleanup();
      if (heard < SILENT) {
        setState("idle"); setPick(true);
        onError?.(de ? "Ich höre nichts – das Mikrofon liefert keinen Ton. Ist es stummgeschaltet oder das falsche gewählt? Bitte das richtige Mikrofon auswählen." : "I hear nothing – the microphone delivers no sound. Is it muted or the wrong one? Please choose the right microphone.");
        return;
      }
      send(new Blob(chunks.current, { type: (rec.mimeType || type || "audio/webm").split(";")[0] }));
    };
    recorder.current = rec;
    rec.start(1000);
    setSeconds(0); setState("recording");
    timer.current = setInterval(() => setSeconds(value => {
      if (value + 1 >= MAX_SECONDS && rec.state === "recording") rec.stop();
      return value + 1;
    }), 1000);
  };
  const stop = () => { if (recorder.current?.state === "recording") recorder.current.stop(); };
  const choose = id => { setDeviceId(id); remember(id); setPick(false); onError?.(""); };

  if (!voiceSupported()) return null;
  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const bars = [0.15, 0.35, 0.55, 0.75, 0.9];
  return <span className="voice-wrap">
    {state === "recording"
      ? <button type="button" className={`voice-btn recording ${className}`} onClick={stop} aria-label={de ? "Aufnahme beenden und in Text umwandeln" : "Stop and transcribe"}>
          <span className="voice-level" aria-hidden="true">{bars.map(bar => <i key={bar} className={level >= bar ? "on" : ""} />)}</span>
          <IconPlayerStopFilled size={14} />{clock}</button>
      : <button type="button" className={`voice-btn ${className}`} onClick={start} disabled={disabled || state === "working"}
          onContextMenu={event => { event.preventDefault(); loadDevices(); setPick(!pick); }}
          aria-label={de ? "Frage einsprechen" : "Speak your question"} title={de ? "Frage einsprechen (Rechtsklick: Mikrofon wählen)" : "Speak (right-click: choose microphone)"}>
          {state === "working" ? <IconLoader2 size={18} className="la-spin" /> : <IconMicrophone size={18} />}</button>}
    {pick && <span className="voice-pick" role="dialog" aria-label={de ? "Mikrofon wählen" : "Choose microphone"}>
      <strong>{de ? "Mikrofon" : "Microphone"}</strong>
      {devices.length ? devices.map((item, index) => <button type="button" key={item.deviceId || index} className={(deviceId || "default") === (item.deviceId || "default") ? "on" : ""} onClick={() => choose(item.deviceId === "default" ? "" : item.deviceId)}>
        {item.label || `${de ? "Mikrofon" : "Microphone"} ${index + 1}`}</button>)
        : <small>{de ? "Keine Mikrofone gefunden. Bitte Mikrofonzugriff erlauben." : "No microphones found. Please allow microphone access."}</small>}
      <small>{de ? "Auch prüfen: Windows-Einstellungen → System → Sound → Eingabe (Lautstärke, Stummschaltung)." : "Also check your system sound input settings (volume, mute)."}</small>
    </span>}
  </span>;
}
