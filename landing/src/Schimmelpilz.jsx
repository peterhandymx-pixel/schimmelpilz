import { useEffect, useState } from "react";
import "./schimmelpilz-guide.css";

import figureUrl from "./assets/frau-schimmelpilz.webp";

// Frau Schimmelpilz, the office's comic assistant. One drawing; a small sign next to her shows
// what she is doing at each step (reading, thinking, alarmed, pleased).
const SIGNS = {
  read: <g><circle cx="22" cy="22" r="13" fill="#fff" stroke="#263e31" strokeWidth="4" /><path d="M32 32 L46 46" stroke="#263e31" strokeWidth="7" strokeLinecap="round" /></g>,
  file: <g><path d="M6 14 h14 l4 -5 h14 l4 5 h10 v32 h-46 Z" fill="#e3c27e" stroke="#263e31" strokeWidth="3" strokeLinejoin="round" /><path d="M16 30 h26 M16 38 h18" stroke="#263e31" strokeWidth="3" strokeLinecap="round" /></g>,
  think: <text x="26" y="44" fontSize="46" fontWeight="900" textAnchor="middle" fill="#0b5a46" stroke="#fff" strokeWidth="2" paintOrder="stroke">?</text>,
  alarm: <text x="26" y="46" fontSize="50" fontWeight="900" textAnchor="middle" fill="#c0392b" stroke="#fff" strokeWidth="2" paintOrder="stroke">!</text>,
  cheer: <g fill="#e8b83a" stroke="#fff" strokeWidth="1.5"><path d="M22 4 l5 13 l13 5 l-13 5 l-5 13 l-5 -13 l-13 -5 l13 -5 Z" /><path d="M42 32 l3 7 l7 3 l-7 3 l-3 7 l-3 -7 l-7 -3 l7 -3 Z" /></g>,
};

export function SchimmelpilzFigure({ pose = "wave", talking = false, size = 150, title = "Frau Schimmelpilz, Ihre Rechtsassistentin" }) {
  const sign = SIGNS[pose];
  return <span className={`sp-figure${talking ? " talking" : ""}`} style={{ width: size }}>
    <img src={figureUrl} alt={title} width="572" height="640" draggable="false" />
    {sign && <svg className="sp-sign" viewBox="0 0 52 52" aria-hidden="true">{sign}</svg>}
  </span>;
}

// Speech bubble that writes its text like someone talking; click or reduced motion shows it at once.
export function useTyped(text) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const quiet = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (quiet) { setShown(text.length); return undefined; }
    setShown(0);
    let at = 0;
    const timer = setInterval(() => { at = Math.min(text.length, at + 2); setShown(at); if (at >= text.length) clearInterval(timer); }, 22);
    return () => clearInterval(timer);
  }, [text]);
  return [text.slice(0, shown), shown < text.length, () => setShown(text.length)];
}

export function AssistantSays({ pose, mood, text, note, children, compact = false }) {
  const [typed, typing, finish] = useTyped(text);
  return <div className={`sp-guide${compact ? " compact" : ""}`}>
    <div className="sp-figure-wrap"><SchimmelpilzFigure pose={pose} talking={typing} size={compact ? 110 : 170} /></div>
    <div className="sp-bubble" onClick={finish}>
      <span className="sp-name">Frau Schimmelpilz</span>
      <p aria-hidden="true">{typed}{typing && <span className="sp-caret">▍</span>}</p>
      <p className="sp-sr" aria-live="polite">{text}</p>
      {note && !typing && <small>{note}</small>}
      {children && <div className={`sp-replies${typing ? " waiting" : ""}`}>{children}</div>}
    </div>
  </div>;
}

// The way a law office handles incoming post, shown as a track the assistant walks along.
export function OfficeTrack({ steps, current, busy = false }) {
  return <ol className="sp-track" aria-label="Ablauf">
    {steps.map((label, index) => <li key={label} className={index < current ? "done" : index === current ? `now${busy ? " busy" : ""}` : ""} aria-current={index === current ? "step" : undefined}>
      <span>{index < current ? "✓" : index + 1}</span><em>{label}</em></li>)}
  </ol>;
}
