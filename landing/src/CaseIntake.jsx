import { useState } from "react";
import { IconArrowRight, IconBriefcase, IconBuildingBank, IconUser } from "@tabler/icons-react";

export const intakeCopy = {
  de: {
    intro: "Legen Sie eine strukturierte Akte an. Pflichtfelder sind mit * markiert; weitere Angaben können Sie zunächst offenlassen.",
    audience: "Für wen wird die Akte geführt?", consumer: "Verbraucher", business: "Unternehmen", law_firm: "Anwaltskanzlei",
    consumerHint: "Ihr persönliches Anliegen", businessHint: "Geschäftliche Angelegenheit", law_firmHint: "Mandatsakte & Recherche",
    referenceHeading: "01 · Aktenführung", generate: "Aktenzeichen anlegen", existing: "Aktenzeichen übernehmen",
    generateHint: "Neue, fortlaufende Nummer: SCH-JAHR-000001. Die endgültige Nummer wird beim Speichern vergeben.",
    existingHint: "Übernehmen Sie Ihre vorhandene Aktennummer unverändert. Ein gerichtliches Aktenzeichen gehört in das separate Feld unten.",
    reference: "Vorhandenes Aktenzeichen *", referencePlaceholder: "z. B. 24/2026-MÜ",
    partiesHeading: "02 · Beteiligte", person: "Betroffene Person *", company: "Unternehmen / Organisation *", client: "Mandant / Mandantin *",
    clientRole: "Rolle im Verfahren", clientEmail: "Kontakt-E-Mail", clientAddress: "Anschrift der eigenen Partei", opponent: "Gegenseite / weitere Beteiligte", opponentAddress: "Anschrift der Gegenseite", opponentReference: "Aktenzeichen der Gegenseite",
    matterHeading: "03 · Angelegenheit & Ziel", title: "Kurzbezeichnung der Akte *", description: "Sachverhalt / Chronologie *", descriptionHint: "Was ist wann passiert? Welche Unterlagen und Beweise liegen vor?", objective: "Gewünschtes Ergebnis / Auftrag", objectiveHint: "z. B. Forderung durchsetzen, Kündigung prüfen oder Recherche zu einer Rechtsfrage",
    legalArea: "Rechtsgebiet", jurisdiction: "Rechtsordnung / Bezug", stage: "Verfahrensstand",
    procedureHeading: "04 · Verfahren & Fristen", court: "Gericht / Behörde (falls bekannt)", courtReference: "Gerichtliches / behördliches Aktenzeichen", receivedOn: "Eingang der Angelegenheit", deadline: "Bekannte Frist / Wiedervorlage", deadlineNote: "Fristgrund / Herkunft", deadlineHint: "Manuell erfasste Angaben; Fristen werden derzeit weder automatisch berechnet noch überwacht.",
    costsHeading: "05 · Wert & Kosten", value: "Streit- / Gegenstandswert", currency: "Währung", feeBasis: "Vergütungsgrundlage", conflict: "Interessenkollision – manuelle Prüfung", conflictHint: "Dokumentiert den angegebenen Prüfstatus. Das System führt keine automatische Kollisionsprüfung durch.",
    facts: "Aktenstammdaten", noEntry: "Nicht angegeben", duplicate: "Dieses Aktenzeichen ist bereits vergeben. Wählen Sie eine andere Nummer oder öffnen Sie die bestehende Akte über die Fallauswahl.", invalid: "Bitte prüfen Sie Ihre Angaben und die Feldlängen.",
    roles: [["other", "Noch offen / andere Rolle"], ["claimant", "Anspruchsteller / Kläger"], ["respondent", "Anspruchsgegner / Beklagter"], ["applicant", "Antragsteller"]],
    areas: [["general", "Allgemeine Rechtsfrage"], ["consumer", "Verbraucherrecht"], ["tenancy", "Mietrecht"], ["contract", "Vertrags- & Zivilrecht"], ["commercial", "Handels- & Gesellschaftsrecht"], ["employment", "Arbeitsrecht"], ["family", "Familienrecht"], ["social", "Sozialrecht"], ["administrative", "Verwaltungsrecht"], ["criminal", "Strafrecht"]],
    jurisdictions: [["DE", "Deutschland"], ["EU", "Europäische Union / grenzüberschreitend"], ["MX", "Mexiko"], ["other", "Andere / noch zu klären"]],
    stages: [["initial", "Erstaufnahme / Recherche"], ["out_of_court", "Außergerichtlich"], ["court", "Gerichtliches Verfahren"], ["appeal", "Rechtsmittelverfahren"], ["enforcement", "Vollstreckung"]],
    fees: [["unknown", "Noch offen"], ["statutory", "Gesetzliche Gebühren (z. B. RVG)"], ["hourly", "Stundenhonorar"], ["agreement", "Vergütungsvereinbarung"]],
    conflicts: [["pending", "Noch nicht geprüft"], ["checked", "Manuell geprüft"], ["conflict", "Möglicher Konflikt vermerkt"]],
  },
  en: {
    intro: "Open a structured case file. Fields marked * are required; other details may remain open for now.",
    audience: "Who is this case file for?", consumer: "Consumer", business: "Business", law_firm: "Law firm",
    consumerHint: "Your personal matter", businessHint: "A business matter", law_firmHint: "Client file & research",
    referenceHeading: "01 · File reference", generate: "Create a reference", existing: "Use an existing reference",
    generateHint: "New sequential number: SCH-YEAR-000001. The final number is assigned when you save.",
    existingHint: "Keep your existing file number unchanged. Enter a court reference in the separate field below.",
    reference: "Existing file reference *", referencePlaceholder: "e.g. 24/2026-SM",
    partiesHeading: "02 · Parties", person: "Person concerned *", company: "Business / organisation *", client: "Client *",
    clientRole: "Role in proceedings", clientEmail: "Contact email", clientAddress: "Own party’s address", opponent: "Opposing party / other parties", opponentAddress: "Opposing party’s address", opponentReference: "Opposing party’s reference",
    matterHeading: "03 · Matter & objective", title: "Case file title *", description: "Facts / chronology *", descriptionHint: "What happened and when? What documents and evidence are available?", objective: "Desired outcome / instructions", objectiveHint: "e.g. recover a debt, review a termination or research a legal question",
    legalArea: "Area of law", jurisdiction: "Legal system / connection", stage: "Procedural stage",
    procedureHeading: "04 · Proceedings & deadlines", court: "Court / authority (if known)", courtReference: "Court / authority reference", receivedOn: "Date received", deadline: "Known deadline / follow-up", deadlineNote: "Reason / source of deadline", deadlineHint: "Manually entered dates. Deadlines are currently neither calculated nor monitored automatically.",
    costsHeading: "05 · Value & costs", value: "Value in dispute / matter value", currency: "Currency", feeBasis: "Fee basis", conflict: "Conflict of interest – manual review", conflictHint: "Records the supplied review status. The system does not perform an automatic conflict check.",
    facts: "Case particulars", noEntry: "Not provided", duplicate: "This reference is already in use. Choose another number or open the existing file using the case selector.", invalid: "Please check your entries and field lengths.",
    roles: [["other", "Undetermined / other"], ["claimant", "Claimant"], ["respondent", "Respondent / defendant"], ["applicant", "Applicant"]],
    areas: [["general", "General legal question"], ["consumer", "Consumer law"], ["tenancy", "Tenancy law"], ["contract", "Contract & civil law"], ["commercial", "Commercial & company law"], ["employment", "Employment law"], ["family", "Family law"], ["social", "Social law"], ["administrative", "Administrative law"], ["criminal", "Criminal law"]],
    jurisdictions: [["DE", "Germany"], ["EU", "European Union / cross-border"], ["MX", "Mexico"], ["other", "Other / to be clarified"]],
    stages: [["initial", "Initial intake / research"], ["out_of_court", "Out of court"], ["court", "Court proceedings"], ["appeal", "Appeal proceedings"], ["enforcement", "Enforcement"]],
    fees: [["unknown", "Undetermined"], ["statutory", "Statutory fees (e.g. RVG)"], ["hourly", "Hourly fee"], ["agreement", "Fee agreement"]],
    conflicts: [["pending", "Not yet reviewed"], ["checked", "Manually reviewed"], ["conflict", "Possible conflict noted"]],
  },
};

function SelectField({ label, name, options, defaultValue }) {
  return <label>{label}<select aria-label={label} name={name} defaultValue={defaultValue}>{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>;
}

export function CaseIntake({ lang, t, saving, error, onSubmit, onCancel, user }) {
  const c = intakeCopy[lang];
  const [audience, setAudience] = useState(user?.audience || "consumer");
  const ownAccount = audience === user?.audience && audience !== "law_firm";
  const profileAddress = user ? `${user.street}\n${user.postal_code} ${user.city}\n${user.country}` : "";
  const [referenceMode, setReferenceMode] = useState("generate");
  const submit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = Object.fromEntries(new FormData(form));
    const { title, description, reference, ...details } = fields;
    for (const key of ["received_on", "deadline"]) details[key] = details[key] || null;
    details.dispute_value = details.dispute_value === "" ? null : Number(details.dispute_value);
    // Unchecked/disabled reference fields never enter the persisted payload.
    delete details.reference_mode;
    const saved = await onSubmit({ title, description, language: lang, reference_mode: referenceMode, ...(referenceMode === "existing" ? { reference } : {}), details });
    if (saved) { form.reset(); setReferenceMode("generate"); }
  };
  const audienceOptions = [["consumer", IconUser], ["business", IconBriefcase], ["law_firm", IconBuildingBank]];
  return <form className="case-intake" onSubmit={submit}>
    <p className="dialog-intro">{c.intro}</p>
    <fieldset disabled={saving} className="audience-picker"><legend>{c.audience}</legend>{audienceOptions.map(([id, Icon]) => <label key={id} className={audience === id ? "choice-card chosen" : "choice-card"}><input type="radio" name="audience" value={id} checked={audience === id} onChange={() => setAudience(id)} /><span><Icon size={20} /><strong>{c[id]}</strong><small>{c[`${id}Hint`]}</small></span></label>)}</fieldset>
    <fieldset disabled={saving} className="intake-section"><legend>{c.referenceHeading}</legend>
      <div className="reference-picker">{["generate", "existing"].map(mode => <label key={mode} className={referenceMode === mode ? "reference-choice chosen" : "reference-choice"}><input type="radio" name="reference_mode" value={mode} checked={referenceMode === mode} onChange={() => setReferenceMode(mode)} />{c[mode]}</label>)}</div>
      <p className="field-help">{c[`${referenceMode}Hint`]}</p>
      {referenceMode === "existing" && <label>{c.reference}<input name="reference" required maxLength={100} placeholder={c.referencePlaceholder} /></label>}
    </fieldset>
    <fieldset disabled={saving} className="intake-section"><legend>{c.partiesHeading}</legend><div className="intake-grid">
      <label>{audience === "law_firm" ? c.client : audience === "business" ? c.company : c.person}<input key={`${audience}-name`} name="client_name" required maxLength={160} autoComplete="off" defaultValue={ownAccount ? user.organisation || user.full_name : ""} /></label>
      <SelectField name="client_role" label={c.clientRole} options={c.roles} defaultValue="other" />
      <label>{c.clientEmail}<input key={`${audience}-email`} name="client_email" type="email" maxLength={254} autoComplete="off" defaultValue={ownAccount ? user.email : ""} /></label>
      <label>{c.opponent}<input name="opponent_name" maxLength={160} /></label>
      <label>{c.clientAddress}<textarea key={`${audience}-address`} name="client_address" maxLength={500} rows={2} defaultValue={ownAccount ? profileAddress : ""} /></label>
      <label>{c.opponentAddress}<textarea name="opponent_address" maxLength={500} rows={2} /></label>
      <label className="span-two">{c.opponentReference}<input name="opponent_reference" maxLength={100} /></label>
    </div></fieldset>
    <fieldset disabled={saving} className="intake-section"><legend>{c.matterHeading}</legend><div className="intake-grid">
      <label className="span-two">{c.title}<input name="title" required minLength={3} maxLength={120} placeholder={t.caseTitle} /></label>
      <SelectField name="legal_area" label={c.legalArea} options={c.areas} defaultValue="general" />
      <SelectField name="jurisdiction" label={c.jurisdiction} options={c.jurisdictions} defaultValue="DE" />
      <SelectField name="stage" label={c.stage} options={c.stages} defaultValue="initial" />
      <label className="span-two">{c.description}<textarea name="description" required minLength={10} maxLength={4000} rows={4} placeholder={c.descriptionHint} /></label>
      <label className="span-two">{c.objective}<textarea name="objective" maxLength={2000} rows={2} placeholder={c.objectiveHint} /></label>
    </div></fieldset>
    <fieldset disabled={saving} className="intake-section"><legend>{c.procedureHeading}</legend><div className="intake-grid">
      <label>{c.court}<input name="court" maxLength={160} /></label><label>{c.courtReference}<input name="court_reference" maxLength={100} /></label>
      <label>{c.receivedOn}<input name="received_on" type="date" /></label><label>{c.deadline}<input name="deadline" type="date" /></label>
      <label className="span-two">{c.deadlineNote}<input name="deadline_note" maxLength={300} /></label>
    </div><p className="field-help">{c.deadlineHint}</p></fieldset>
    <fieldset disabled={saving} className="intake-section"><legend>{c.costsHeading}</legend><div className="intake-grid">
      <label>{c.value}<input name="dispute_value" type="number" min="0" max="1000000000000" step="0.01" placeholder="0.00" /></label>
      <SelectField name="currency" label={c.currency} options={[["EUR", "EUR"], ["MXN", "MXN"], ["USD", "USD"]]} defaultValue="EUR" />
      <SelectField name="fee_basis" label={c.feeBasis} options={c.fees} defaultValue="unknown" />
      {audience === "law_firm" && <SelectField name="conflict_check" label={c.conflict} options={c.conflicts} defaultValue="pending" />}
    </div>{audience === "law_firm" && <p className="field-help">{c.conflictHint}</p>}</fieldset>
    <div className="intake-footer">{error && <p className="storage-error" role="alert">{error}</p>}<div className="dialog-actions"><button type="button" className="secondary-button" disabled={saving} onClick={onCancel}>{t.cancel}</button><button type="submit" className="primary-button" disabled={saving}>{saving ? "…" : t.create}<IconArrowRight size={18} /></button></div></div>
  </form>;
}

export function CaseFacts({ item, lang }) {
  const c = intakeCopy[lang];
  const d = item.details || {};
  const option = (options, value) => options.find(([id]) => id === value)?.[1];
  const dateText = value => value ? new Date(`${value}T12:00:00`).toLocaleDateString(lang === "de" ? "de-DE" : "en-GB") : null;
  const entries = [
    [c.audience, c[d.audience]], [d.audience === "law_firm" ? c.client : d.audience === "business" ? c.company : c.person, d.client_name],
    [c.clientRole, option(c.roles, d.client_role)], [c.clientEmail, d.client_email], [c.clientAddress, d.client_address],
    [c.opponent, d.opponent_name], [c.opponentAddress, d.opponent_address], [c.opponentReference, d.opponent_reference],
    [c.legalArea, option(c.areas, d.legal_area)], [c.jurisdiction, option(c.jurisdictions, d.jurisdiction)], [c.stage, option(c.stages, d.stage)],
    [c.description, item.description], [c.objective, d.objective], [c.court, d.court], [c.courtReference, d.court_reference],
    [c.receivedOn, dateText(d.received_on)], [c.deadline, dateText(d.deadline)], [c.deadlineNote, d.deadline_note],
    [c.value, d.dispute_value != null ? `${Number(d.dispute_value).toLocaleString(lang, { minimumFractionDigits: 2 })} ${d.currency || "EUR"}` : null],
    [c.feeBasis, option(c.fees, d.fee_basis)], ...(d.audience === "law_firm" ? [[c.conflict, option(c.conflicts, d.conflict_check)]] : []),
  ].filter(([, value]) => value);
  return <details className="panel case-facts"><summary>{c.facts}<span>+</span></summary><dl>{entries.map(([label, value]) => <div key={label}><dt>{label.replace(" *", "")}</dt><dd>{value}</dd></div>)}</dl>{d.deadline && <p className="field-help">{c.deadlineHint}</p>}</details>;
}
