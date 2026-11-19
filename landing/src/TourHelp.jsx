import { useEffect, useRef, useState } from "react";
import { IconCheck, IconPlayerPlay, IconX } from "@tabler/icons-react";
import figureUrl from "./assets/frau-schimmelpilz.webp";
import { readPreference, writePreference } from "./useCaseStorage.js";
import { Tour } from "./Tour.jsx";
import { toursFor, tourKey } from "./tours.js";

// All tours of an audience: auto-start at first login, "Hilfe & Rundgänge" list, one-time offer on a section's first visit.
export function TourCenter({ lang = "de", user, view, ready, onView, onFinish }) {
  const de = lang === "de";
  const tours = toursFor(user.audience);
  const done = id => Boolean(readPreference(tourKey(user.id, id)) || (id === "consumer" && readPreference("schimmelpilz.tour.v1." + user.id)));
  const [active, setActive] = useState(null), [open, setOpen] = useState(false), [offer, setOffer] = useState(null), [, refresh] = useState(0);
  const menu = useRef(null);

  useEffect(() => {
    if (!ready || active) return;
    const first = tours.find(tour => tour.auto && !done(tour.id));
    if (first) setActive(first);
  }, [ready]);
  useEffect(() => {
    if (active) return;
    const candidate = tours.find(tour => tour.offerOn?.includes(view) && !done(tour.id) && !readPreference(tourKey(user.id, tour.id) + ".offered"));
    setOffer(candidate || null);
  }, [view, active]);
  useEffect(() => {
    if (!open) return undefined;
    const away = event => { if (!menu.current?.contains(event.target)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const close = () => { writePreference(tourKey(user.id, active.id), "1"); setActive(null); refresh(value => value + 1); };
  const start = tour => { setOpen(false); setOffer(null); setActive(tour); };
  const dismissOffer = () => { writePreference(tourKey(user.id, offer.id) + ".offered", "1"); setOffer(null); };

  return <>
    <div className="tour-help" ref={menu}>
      <button type="button" className="tour-replay" aria-expanded={open} onClick={() => tours.length === 1 ? start(tours[0]) : setOpen(!open)}>
        <img src={figureUrl} alt="" />{tours.length === 1 ? (de ? "Rundgang mit Frau Schimmelpilz" : "Tour with Ms Schimmelpilz") : (de ? "Hilfe & Rundgänge" : "Help & tours")}</button>
      {open && <ul className="tour-help-list">{tours.map(tour => <li key={tour.id}><button type="button" onClick={() => start(tour)}>
        {done(tour.id) ? <IconCheck size={15} className="done" /> : <IconPlayerPlay size={15} />}{tour.title[lang] || tour.title.de}</button></li>)}</ul>}
    </div>
    {offer && !active && <div className="tour-offer" role="dialog" aria-label={offer.title[lang] || offer.title.de}>
      <img src={figureUrl} alt="" /><div><strong>Frau Schimmelpilz</strong>
        <p>{de ? `Kurz zeigen, wie „${offer.title.de}“ funktioniert? Dauert eine Minute.` : `Shall I quickly show how “${offer.title.en}” works? Takes a minute.`}</p>
        <span><button type="button" className="sp-reply primary" onClick={() => { dismissOffer(); start(offer); }}>{de ? "Ja, zeigen" : "Yes, show me"}</button>
          <button type="button" className="sp-reply" onClick={dismissOffer}>{de ? "Nein, danke" : "No, thanks"}</button></span></div>
      <button type="button" className="tour-offer-close" onClick={dismissOffer} aria-label={de ? "Schließen" : "Close"}><IconX size={16} /></button></div>}
    {active && <Tour lang={lang} steps={active.steps[lang] || active.steps.de} onClose={close} onView={onView} onFinish={onFinish} />}
  </>;
}
