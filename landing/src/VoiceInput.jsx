import { useEffect, useRef, useState } from "react";
import { IconLoader2, IconMicrophone, IconPlayerStopFilled } from "@tabler/icons-react";
import { request } from "./useCaseStorage.js";

const MAX_SECONDS = 300;
const pickType = () => ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find(type => window.MediaRecorder?.isTypeSupported?.(type)) || "";
export const voiceSupported = () => typeof window !== "undefined" && Boolean(window.MediaRecorder && navigator.mediaDevices?.getUserMedia);

// Microphone button: record, stop, the server turns speech into text, onText receives it. Audio is not stored.
export function VoiceButton({ lang = "de", disabled, onText, onError, className = "" }) {
  const de = lang === "de";
  const [state, setState] = useState("idle"), [seconds, setSeconds] = useState(0);
  const recorder = useRef(null), chunks = useRef([]), timer = useRef(null), stream = useRef(null);

  const cleanup = () => { clearInterval(timer.current); stream.current?.getTracks().forEach(track => track.stop()); stream.current = null; };
  useEffect(() => () => { if (recorder.current?.state === "recording") recorder.current.onstop = null; recorder.current?.state === "recording" && recorder.current.stop(); cleanup(); }, []);

  const send = async blob => {
    setState("working");
    try {
      const form = new FormData();
      form.append("file", blob, "speech");
      form.append("language", lang === "en" ? "en" : "de");
      const result = await request("/speech/transcribe", { method: "POST", body: form });
      if (result.text) onText(result.text); else onError?.(de ? "Ich habe nichts verstanden. Bitte noch einmal sprechen." : "Nothing recognised. Please try again.");
    } catch (error) {
      onError?.(error.status === 429 ? (de ? "Zu viele Spracheingaben in kurzer Zeit. Bitte kurz warten." : "Too many voice inputs. Please wait a moment.")
        : error.detail === "audio_too_short" ? (de ? "Die Aufnahme war zu kurz." : "The recording was too short.")
        : error.detail === "ai_paused_by_operator" ? (de ? "Die KI ist derzeit pausiert." : "AI is currently paused.")
        : (de ? "Spracheingabe fehlgeschlagen. Bitte erneut versuchen oder tippen." : "Voice input failed. Please try again or type."));
    } finally { setState("idle"); }
  };

  const start = async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      onError?.(de ? "Kein Zugriff auf das Mikrofon. Bitte im Browser erlauben." : "No microphone access. Please allow it in the browser.");
      return;
    }
    const type = pickType();
    const rec = new MediaRecorder(stream.current, type ? { mimeType: type } : undefined);
    chunks.current = [];
    rec.ondataavailable = event => event.data.size && chunks.current.push(event.data);
    rec.onstop = () => { cleanup(); send(new Blob(chunks.current, { type: (rec.mimeType || type || "audio/webm").split(";")[0] })); };
    recorder.current = rec;
    rec.start(1000);
    setSeconds(0); setState("recording");
    timer.current = setInterval(() => setSeconds(value => {
      if (value + 1 >= MAX_SECONDS) rec.state === "recording" && rec.stop();
      return value + 1;
    }), 1000);
  };
  const stop = () => recorder.current?.state === "recording" && recorder.current.stop();

  if (!voiceSupported()) return null;
  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  return state === "recording"
    ? <button type="button" className={`voice-btn recording ${className}`} onClick={stop} aria-label={de ? "Aufnahme beenden und in Text umwandeln" : "Stop and transcribe"}>
        <span className="voice-dot" /><IconPlayerStopFilled size={14} />{clock}</button>
    : <button type="button" className={`voice-btn ${className}`} onClick={start} disabled={disabled || state === "working"}
        aria-label={de ? "Frage einsprechen" : "Speak your question"} title={de ? "Frage einsprechen – wird in Text umgewandelt" : "Speak – converted to text"}>
        {state === "working" ? <IconLoader2 size={18} className="la-spin" /> : <IconMicrophone size={18} />}</button>;
}
