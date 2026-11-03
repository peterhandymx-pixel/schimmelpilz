import { useEffect, useRef, useState } from "react";
import { IconCalendar } from "@tabler/icons-react";
import { formatDateInput, parseDateInput } from "./workbench";

// Native date pickers follow the browser's locale (mm/dd/yyyy in an English browser).
// This field always shows TT.MM.JJJJ in German, keeps ISO for forms/API and still offers the system calendar.
export function DateInput({ value, defaultValue, onChange, name, required, min, max, disabled, lang, id, ...rest }) {
  const language = lang || document.documentElement.lang || "de";
  const de = language === "de";
  const controlled = value !== undefined;
  const [iso, setIso] = useState(controlled ? value || "" : defaultValue || "");
  const [text, setText] = useState(formatDateInput(controlled ? value : defaultValue, language));
  const picker = useRef(null);
  const field = useRef(null);
  const current = controlled ? value || "" : iso;

  useEffect(() => {
    if (controlled && parseDateInput(text) !== (value || "")) setText(formatDateInput(value, language));
  }, [value, language]);

  useEffect(() => {
    // Uncontrolled forms call form.reset() after saving; return to the initial date like a native field would.
    const form = field.current?.form;
    if (controlled || !form) return undefined;
    const restore = () => { setIso(defaultValue || ""); setText(formatDateInput(defaultValue, language)); field.current?.setCustomValidity(""); };
    form.addEventListener("reset", restore);
    return () => form.removeEventListener("reset", restore);
  }, [controlled, defaultValue, language]);

  const commit = next => {
    if (!controlled) setIso(next);
    onChange?.({ target: { value: next, name } });
  };

  const validate = next => {
    const message = next === null ? (de ? "Bitte Datum als TT.MM.JJJJ eingeben." : "Enter the date as DD/MM/YYYY.")
      : next && min && next < min ? (de ? `Frühestens ${formatDateInput(min, language)}.` : `No earlier than ${formatDateInput(min, language)}.`)
      : next && max && next > max ? (de ? `Spätestens ${formatDateInput(max, language)}.` : `No later than ${formatDateInput(max, language)}.`) : "";
    field.current?.setCustomValidity(message);
  };

  return <span className="date-input">
    <input ref={field} id={id} type="text" inputMode="numeric" autoComplete="off" placeholder={de ? "TT.MM.JJJJ" : "DD/MM/YYYY"} value={text} required={required} disabled={disabled} {...rest}
      onChange={e => { setText(e.target.value); const next = parseDateInput(e.target.value); validate(next); if (next !== null) commit(next); }}
      onBlur={() => { const next = parseDateInput(text); if (next) setText(formatDateInput(next, language)); }} />
    {name && <input type="hidden" name={name} value={current} />}
    <button type="button" className="date-input-picker" disabled={disabled} aria-label={de ? "Kalender öffnen" : "Open calendar"} onClick={() => { try { picker.current?.showPicker(); } catch { picker.current?.focus(); } }}><IconCalendar size={18} stroke={1.8} aria-hidden="true" /></button>
    <input ref={picker} type="date" className="date-input-native" tabIndex={-1} aria-hidden="true" value={current} min={min} max={max} disabled={disabled}
      onChange={e => { setText(formatDateInput(e.target.value, language)); validate(e.target.value); commit(e.target.value); }} />
  </span>;
}
