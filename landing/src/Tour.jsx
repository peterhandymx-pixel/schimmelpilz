import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { IconArrowLeft, IconArrowRight, IconX } from "@tabler/icons-react";
import { SchimmelpilzFigure, useTyped } from "./Schimmelpilz.jsx";
import "./tour.css";

// Guided tour for private persons: Frau Schimmelpilz walks to each part of the workspace and explains it.
// A step names a CSS selector (target), the view to open first, her pose and what she says.
export const CONSUMER_TOUR = {
  de: [
    { pose: "wave", text: "Hallo, ich bin Frau Schimmelpilz! In einer Minute zeige ich Ihnen, wie Sie mit mir Ihre Post erledigen. Sie können jederzeit überspringen." },
    { target: '[data-module="assistant"]', view: "assistant", pose: "point", text: "Hier fängt alles an: der Brief-Assistent. Immer wenn Post kommt – oder Sie selbst etwas verschickt haben – klicken Sie hier." },
    { target: ".letter-assistant .sp-replies", view: "assistant", pose: "think", text: "Ich frage Sie zuerst: Haben Sie einen Brief bekommen oder etwas verschickt? Dann fotografieren Sie den Brief – mehrere Seiten auf einmal gehen auch – oder tippen ihn ab." },
    { target: ".letter-assistant .sp-track", view: "assistant", pose: "read", text: "Dann arbeite ich wie in einer Kanzlei: Akte anlegen, Brief lesen, Angaben prüfen, ein paar Fragen, Frist notieren. Die Frist berechne ich nach festen Regeln – mit Wochenenden und Feiertagen." },
    { target: '[data-module="cases"]', pose: "file", text: "Meine Vorgänge: Für jede Sache gibt es eine Akte. Dort liegt alles beisammen – Briefe, Fristen und Ihre Schreiben." },
    { target: '[data-module="tasks"]', pose: "alarm", text: "Fristen & Termine: Hier steht, was bis wann erledigt sein muss. Ich erinnere Sie per E-Mail – einmal rechtzeitig vorher und noch einmal am Tag vor Ablauf." },
    { target: '[data-module="documents"]', pose: "read", text: "Meine Unterlagen: alle Briefe und Fotos. Mit „Ansehen“ öffnen Sie das Original – Seite für Seite." },
    { target: '[data-module="drafts"]', pose: "file", text: "Meine Schreiben: Antworten und Widersprüche, die ich für Sie vorbereite. Sie können alles ändern und als PDF oder Word speichern." },
    { target: '[data-module="samples"]', pose: "point", text: "Vorlagen: über 100 fertige Musterschreiben, schon mit Ihren Daten ausgefüllt – vom Widerspruch bis zur Kündigung." },
    { target: '[data-module="account"]', pose: "smile", text: "Mein Konto: Hier stehen Ihre Anschrift – die brauche ich für Ihre Schreiben – und die Einstellung für die E-Mail-Erinnerungen." },
    { target: ".desk-mode-switch", pose: "point", text: "Und wenn Sie mehr brauchen: Hier schalten Sie zur vollen Ansicht mit Recherche, Kostenprüfung und allen Werkzeugen um." },
    { target: ".tour-replay", pose: "smile", text: "Diesen Rundgang finden Sie hier jederzeit wieder." },
    { pose: "cheer", text: "Das war's schon! Sollen wir gleich Ihren ersten Brief anschauen?", finish: true },
  ],
  en: [
    { pose: "wave", text: "Hello, I'm Ms Schimmelpilz! In one minute I'll show you how we deal with your post together. You can skip at any time." },
    { target: '[data-module="assistant"]', view: "assistant", pose: "point", text: "Everything starts here: the letter assistant. Whenever post arrives – or you sent something yourself – click here." },
    { target: ".letter-assistant .sp-replies", view: "assistant", pose: "think", text: "First I ask: did you receive a letter or send one? Then take a photo – several pages at once work too – or type it in." },
    { target: ".letter-assistant .sp-track", view: "assistant", pose: "read", text: "Then I work like a law office: open a file, read the letter, check the details, ask a few questions, note the deadline – calculated by fixed rules, with weekends and holidays." },
    { target: '[data-module="cases"]', pose: "file", text: "My matters: every matter has its own file with all letters, deadlines and your replies." },
    { target: '[data-module="tasks"]', pose: "alarm", text: "Deadlines: what has to be done by when. I remind you by email – once in good time and again the day before." },
    { target: '[data-module="documents"]', pose: "read", text: "My documents: all letters and photos. “View” opens the original, page by page." },
    { target: '[data-module="drafts"]', pose: "file", text: "My letters: replies and objections I prepare for you. Change anything, save as PDF or Word." },
    { target: '[data-module="samples"]', pose: "point", text: "Templates: more than 100 ready-made sample letters, already filled in with your details." },
    { target: '[data-module="account"]', pose: "smile", text: "My account: your address – I need it for your letters – and the email reminder setting." },
    { target: ".desk-mode-switch", pose: "point", text: "Need more? Switch to the full view with research, cost review and all tools here." },
    { target: ".tour-replay", pose: "smile", text: "You can start this tour again here at any time." },
    { pose: "cheer", text: "That's it! Shall we look at your first letter right away?", finish: true },
  ],
};
const COPY = {
  de: { next: "Weiter", back: "Zurück", skip: "Überspringen", close: "Rundgang beenden", start: "Brief hochladen", later: "Später", of: (i, n) => `${i} / ${n}` },
  en: { next: "Next", back: "Back", skip: "Skip", close: "End tour", start: "Upload a letter", later: "Later", of: (i, n) => `${i} / ${n}` },
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
          ? <div className="tour-actions"><button type="button" className="sp-reply" onClick={onClose}>{c.later}</button><button type="button" className="sp-reply primary" onClick={() => { onClose(); onFinish?.(); }}>{c.start}</button></div>
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
