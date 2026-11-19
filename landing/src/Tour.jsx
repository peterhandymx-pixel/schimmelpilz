import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { IconArrowLeft, IconArrowRight, IconX } from "@tabler/icons-react";
import { SchimmelpilzFigure, useTyped } from "./Schimmelpilz.jsx";
import "./tour.css";

// Plays one guided tour (see tours.js): Frau Schimmelpilz walks to each target and explains it.
const COPY = {
  de: { next: "Weiter", back: "Zurück", skip: "Überspringen", close: "Rundgang beenden", later: "Später", of: (i, n) => `${i} / ${n}`,
    finish: { assistant: "Brief hochladen", "new-case": "Akte anlegen", dictate: "Jetzt diktieren" } },
  en: { next: "Next", back: "Back", skip: "Skip", close: "End tour", later: "Later", of: (i, n) => `${i} / ${n}`,
    finish: { assistant: "Upload a letter", "new-case": "Create a file", dictate: "Dictate now" } },
};
const PAD = 8, FIGURE = 120, CARD = 340;

// Where the spotlight, Frau Schimmelpilz and her bubble go for the current target.
function layout(element) {
  const width = window.innerWidth, height = window.innerHeight, narrow = width < 700;
  if (!element) return { spot: null, place: narrow ? "bottom" : "center", narrow };
  const box = element.getBoundingClientRect();
  const spot = { left: box.left - PAD, top: box.top - PAD, width: box.width + 2 * PAD, height: box.height + 2 * PAD };
  if (narrow) return { spot, place: box.top + box.height / 2 > height / 2 ? "top" : "bottom", narrow };
  const right = box.right + PAD + 16, roomRight = width - right;
  const left = roomRight >= CARD + FIGURE ? right : Math.max(16, box.left - CARD - FIGURE - 24);
  const top = Math.min(Math.max(16, box.top + box.height / 2 - 110), height - 260);
  return { spot, place: "beside", left, top, narrow };
}

export function Tour({ lang = "de", steps, onClose, onView, onFinish }) {
  const c = COPY[lang] || COPY.de;
  const [index, setIndex] = useState(0), [geometry, setGeometry] = useState({ spot: null, place: "center" });
  const step = steps[index];
  const [typed, typing, finishTyping] = useTyped(step.text);

  // Open the step's view, then find its target (it may render a moment later) and measure it.
  const measure = useCallback(() => {
    const element = step.target ? document.querySelector(step.target) : null;
    setGeometry(layout(element));
  }, [step]);
  const viewRef = useRef(onView); viewRef.current = onView;
  useEffect(() => { if (step.view) viewRef.current?.(step.view); }, [step]);
  useLayoutEffect(() => {
    let tries = 0, timer;
    const find = () => {
      const element = step.target ? document.querySelector(step.target) : null;
      if (element) element.scrollIntoView({ block: "nearest", behavior: "smooth" });
      if (step.target && !element && tries++ < 10) { timer = setTimeout(find, 120); return; }
      setTimeout(measure, 260);
      measure();
    };
    find();
    return () => clearTimeout(timer);
  }, [step, measure]);
  useEffect(() => {
    window.addEventListener("resize", measure); window.addEventListener("scroll", measure, true);
    return () => { window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure, true); };
  }, [measure]);

  const next = () => { if (typing) { finishTyping(); return; } if (index + 1 < steps.length) setIndex(index + 1); else onClose(); };
  const back = () => index > 0 && setIndex(index - 1);
  useEffect(() => {
    const keys = event => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight" || event.key === "Enter") { event.preventDefault(); next(); }
      if (event.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  });

  const { spot, place } = geometry;
  const guideStyle = place === "beside" ? { left: geometry.left, top: geometry.top } : {};
  return <div className="tour" role="dialog" aria-modal="true" aria-label={c.close}>
    {spot ? <div className="tour-spot" style={spot} /> : <div className="tour-dim" />}
    <div className={`tour-guide ${place}`} style={guideStyle} key={place === "beside" ? "beside" : place}>
      <div className="tour-figure" key={index}><SchimmelpilzFigure pose={step.pose} talking={typing} size={FIGURE} /></div>
      <div className="tour-card" onClick={finishTyping}>
        <span className="sp-name">Frau Schimmelpilz <em>{c.of(index + 1, steps.length)}</em></span>
        <p aria-hidden="true">{typed}{typing && <span className="sp-caret">▍</span>}</p>
        <p className="sp-sr" aria-live="polite">{step.text}</p>
        <div className="tour-dots" aria-hidden="true">{steps.map((_, dot) => <i key={dot} className={dot === index ? "on" : dot < index ? "done" : ""} />)}</div>
        {step.finish
          ? <div className="tour-actions"><button type="button" className="sp-reply" onClick={onClose}>{c.later}</button><button type="button" className="sp-reply primary" onClick={() => { onClose(); onFinish?.(step.finish); }}>{c.finish[step.finish] || c.next}</button></div>
          : <div className="tour-actions">
            <button type="button" className="tour-skip" onClick={onClose}>{c.skip}</button>
            <span>{index > 0 && <button type="button" className="sp-reply" onClick={back}><IconArrowLeft size={16} />{c.back}</button>}
              <button type="button" className="sp-reply primary" onClick={next}>{c.next}<IconArrowRight size={16} /></button></span>
          </div>}
      </div>
      <button type="button" className="tour-close" onClick={onClose} aria-label={c.close}><IconX size={18} /></button>
    </div>
  </div>;
}
