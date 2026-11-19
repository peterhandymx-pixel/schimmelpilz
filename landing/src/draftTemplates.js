export const draftCopy = {
  de: {
    title: "Schriftsatz vorbereiten", kind: "Dokumentart", recipient: "Empfänger / Anschrift", recipientPlaceholder: "Gericht, Behörde, Kanzlei, Unternehmen oder Privatperson", language: "Sprache des Entwurfs", insert: "Vorlage in den Editor einsetzen", replaceHint: "Setzt den Editor auf die gewählte Vorlage zurück. Den Entwurf anschließend ergänzen und speichern.",
    hint: "Vorlagen mit Ihren Falldaten. Platzhalter in [Klammern] vervollständigen. Rechtliche Begründung, Zuständigkeit, Fristen und Einreichungsform werden nicht automatisch geprüft. Es wird nichts versendet.",
    courtHint: "Klagevorlage: Zivilklage, bei Sozial- und Verwaltungssachen Klage gegen den Bescheid (Aufhebungs- und Verpflichtungsantrag). Für andere Verfahrensarten oder Länder anpassen; ein englischer Text ist keine Prüfung der zulässigen Gerichtssprache.",
    types: [["letter", "Allgemeines Anschreiben"], ["claim", "Klageentwurf (passt sich dem Gericht an)"], ["application", "Antrag"], ["objection", "Widerspruch"], ["response", "Stellungnahme / Erwiderung"]],
  },
  en: {
    title: "Prepare a document", kind: "Document type", recipient: "Recipient / address", recipientPlaceholder: "Court, authority, law firm, business or individual", language: "Draft language", insert: "Insert template into the editor", replaceHint: "Resets the editor to the selected template. Complete and save the draft afterwards.",
    hint: "Templates using your case data. Complete placeholders in [brackets]. Legal reasoning, jurisdiction, deadlines and filing requirements are not checked automatically. Nothing is sent.",
    courtHint: "Claim template: a general structure for German civil proceedings. Adapt for other proceedings or countries; an English text does not check the permitted court language.",
    types: [["letter", "General correspondence"], ["claim", "Claim draft (civil proceedings)"], ["application", "Application"], ["objection", "Objection"], ["response", "Written response / defence"]],
  },
};

// The subject line of a letter (the first line after the reference block) or the heading of a pleading, for lists.
export function draftSubject(body = "") {
  const lines = body.split("\n").map(line => line.trim());
  const ref = lines.findIndex(line => /^(Unser (Akten)?[Zz]eichen|Our reference)/.test(line));
  if (ref >= 0) {
    const gap = lines.indexOf("", ref);
    const subject = gap >= 0 ? lines.slice(gap).find(Boolean) : "";
    if (subject && !/^(Sehr geehrte|Dear)/.test(subject)) return subject.slice(0, 120);
  }
  return (lines.find(line => /^[A-ZÄÖÜ]{5,}$/.test(line)) || "").slice(0, 120);
}

// jurisdiction: the court suggestion from /cases/{id}/court-suggestion ({ok, court, basis} or {ok:false, message}).
export function documentTemplate(item, language = "de", kind = "letter", recipient = "", jurisdiction = null) {
  const d = item.details || {};
  const de = language === "de";
  const own = [d.client_name, d.client_address].filter(Boolean).join("\n") || (de ? "[Name und Anschrift der eigenen Partei]" : "[Own party’s name and address]");
  const opposite = [d.opponent_name, d.opponent_address].filter(Boolean).join("\n") || (de ? "[Name und Anschrift der Gegenseite]" : "[Opposing party’s name and address]");
  const missingCourt = kind === "claim" && jurisdiction && !jurisdiction.ok ? `[GERICHT FEHLT – ${jurisdiction.message}]` : "";
  const to = recipient.trim() || (kind === "claim" && d.court ? d.court.split(/,\s*/).join("\n") : "") || missingCourt || (de ? "[Empfänger und vollständige Anschrift]" : "[Recipient and full address]");
  const competence = jurisdiction?.ok && (!d.court || d.court.startsWith(jurisdiction.name))
    ? `Das angerufene Gericht ist zuständig. ${jurisdiction.basis}\n${jurisdiction.area === "zivil" ? "[Zuständigkeit im Einzelfall prüfen, etwa besondere Gerichtsstände (§§ 20 ff. ZPO) oder eine Gerichtsstandsvereinbarung.]" : "[Zuständigkeit im Einzelfall prüfen.]"}`
    : "[Sachliche und örtliche Zuständigkeit, Verfahrensart, Vertretung und Form prüfen und begründen.]";
  const date = de ? "[Ort, Datum]" : "[Place, date]";
  const ref = de ? `Unser Aktenzeichen: ${item.reference}` : `Our reference: ${item.reference}`;
  const publicLaw = ["social", "administrative", "tax"].includes(d.legal_area);
  const external = [[de ? "Az. des Gerichts" : "Court reference", d.court_reference], [de ? (publicLaw ? "Az. der Behörde" : "Zeichen der Gegenseite") : (publicLaw ? "Authority reference" : "Opposing party reference"), d.opponent_reference]].filter(([, value]) => value).map(([label, value]) => `${label}: ${value}`).join("\n");
  const header = `${own}\n\n${de ? (kind === "claim" ? "An das" : "An") : "To"}\n${to}\n\n${date}\n${ref}${external ? `\n${external}` : ""}`;
  const objective = d.objective || (de ? "[Gewünschtes Ergebnis / Auftrag ergänzen]" : "[Complete desired outcome / instructions]");
  const facts = item.description;
  const attachments = de ? "Anlagen:\n[Anlagen mit Bezeichnung und Nummer aufführen]" : "Attachments:\n[List attachments by name and number]";
  const closing = de ? "Mit freundlichen Grüßen\n[Name / Unterschrift]" : "Yours faithfully,\n[Name / signature]";
  if (kind === "claim" && de && publicLaw) {
    const social = d.legal_area === "social", tax = d.legal_area === "tax";
    const decision = `den Bescheid der Beklagten vom [Datum]${d.opponent_reference ? `, Az. ${d.opponent_reference},` : ""} in Gestalt ${tax ? "der Einspruchsentscheidung" : "des Widerspruchsbescheids"} vom [Datum]`;
    return `${header}\n\nKLAGE\n\n${own}\n– Kläger/in –\n\ngegen\n\n${opposite}\n[gesetzliche Vertretung der Behörde / des Leistungsträgers]\n– Beklagte/r –\n\nwegen: ${item.title}\n\n`
      + `Ich erhebe Klage und beantrage,\n\n1. ${decision} aufzuheben [und die Beklagte zu verpflichten, … / zu verurteilen, …],\n\n2. ${social ? "die Beklagte zu verpflichten, die außergerichtlichen Kosten der klagenden Partei zu erstatten." : "der Beklagten die Kosten des Verfahrens aufzuerlegen."}\n\n`
      + `Begründung:\n\nI. Sachverhalt\n${facts}\n\nII. Vorverfahren und Klagefrist\nGegen den Bescheid vom [Datum] wurde am [Datum] ${tax ? "Einspruch eingelegt. Die Einspruchsentscheidung" : "Widerspruch erhoben. Der Widerspruchsbescheid"} vom [Datum] ist am [Datum] zugegangen. `
      + `Die Klagefrist von einem Monat (${social ? "§ 87 Abs. 1, 2 SGG" : tax ? "§ 47 Abs. 1 FGO" : "§ 74 Abs. 1 VwGO"}) ist gewahrt.\n\nIII. Rechtliche Begründung\n[Warum der Bescheid rechtswidrig ist: Rechtsgrundlage, Voraussetzungen, Fehler der Behörde, Beweismittel.]\n\n`
      + `IV. Zuständigkeit\n${competence}\n\n`
      + (social ? "Hinweis: Das Verfahren ist für Versicherte, Leistungsempfänger und behinderte Menschen gerichtskostenfrei (§ 183 SGG). Eine anwaltliche Vertretung ist vor dem Sozialgericht nicht vorgeschrieben (§ 73 SGG).\n\n"
        : tax ? "Hinweis: Vor dem Finanzgericht ist eine Vertretung durch Steuerberater oder Anwalt nicht vorgeschrieben (§ 62 Abs. 1 FGO); es fallen Gerichtskosten nach dem GKG an.\n\n"
        : "Hinweis: Vor dem Verwaltungsgericht ist eine anwaltliche Vertretung nicht vorgeschrieben (§ 67 Abs. 1 VwGO); es fallen Gerichtskosten nach dem GKG an.\n\n")
      + `Anlagen:\n– Bescheid vom [Datum]\n– ${tax ? "Einspruch" : "Widerspruch"} vom [Datum]\n– ${tax ? "Einspruchsentscheidung" : "Widerspruchsbescheid"} vom [Datum]\n\n[Name / Unterschrift]`;
  }
  if (kind === "claim") {
    const claimant = d.client_role === "respondent" ? (de ? "[Klagende Partei – eigene Partei ist als Beklagte erfasst; Rollen prüfen]" : "[Claimant – own party recorded as respondent; verify roles]") : own;
    const value = d.dispute_value == null ? (de ? "[Wert ergänzen / klären]" : "[Complete / establish value]") : `${Number(d.dispute_value).toLocaleString(de ? "de-DE" : "en-GB", { minimumFractionDigits: 2 })} ${d.currency || "EUR"}`;
    return de
      ? `${header}\n\nKLAGEENTWURF\nwegen: ${item.title}\n\nKlagende Partei:\n${claimant}\n\nBeklagte Partei:\n${opposite}\n\nStreitwert: ${value}\n\nI. Anträge\n[Bestimmten Klageantrag mit beantragter Rechtsfolge formulieren. Streitwert ist nicht automatisch die Klageforderung.]\n[Etwaige weitere Anträge nach Prüfung ergänzen.]\n\nII. Sachverhalt\n${facts}\n\nIII. Beweismittel\n[Zu jeder streitigen Tatsache Beweismittel, Zeugen oder Anlage zuordnen.]\n\nIV. Rechtliche Begründung\n[Anspruchsgrundlage, Voraussetzungen, Einwendungen und geprüfte Fundstellen ergänzen.]\n\nV. Zuständigkeit und Verfahrensangaben\n${competence}\n[Vorherige Streitschlichtung / Mediation und weitere erforderliche Angaben ergänzen.]\n\nAuftragsziel aus der Akte:\n${objective}\n\n${attachments}\n\n[Name / Unterschrift]`
      : `${header}\n\nCLAIM DRAFT\nSubject: ${item.title}\n\nClaimant:\n${claimant}\n\nDefendant:\n${opposite}\n\nValue in dispute: ${value}\n\nI. Relief sought\n[State the specific relief sought. Matter value is not automatically the sum claimed.]\n[Add other requests after review.]\n\nII. Facts\n${facts}\n\nIII. Evidence\n[Identify evidence, witnesses or an attachment for each disputed fact.]\n\nIV. Legal grounds\n[Complete the legal basis, requirements, defences and verified references.]\n\nV. Jurisdiction and procedure\n[Verify and explain subject-matter and territorial jurisdiction, procedure, representation and form.]\n[Add prior conciliation / mediation and other required particulars.]\n\nInstructions from the case file:\n${objective}\n\n${attachments}\n\n[Name / signature]`;
  }
  const titles = de ? { letter: "Anschreiben", application: "Antrag", objection: "Widerspruch", response: "Stellungnahme / Erwiderung" } : { letter: "Correspondence", application: "Application", objection: "Objection", response: "Written response / defence" };
  const action = de
    ? { letter: "Bitte nehmen Sie zu dem unten beschriebenen Sachverhalt Stellung.\n[Konkretes Anliegen und gewünschte Reaktion ergänzen.]", application: "Ich beantrage:\n[Konkreten Antrag und beantragte Entscheidung formulieren.]", objection: "Hiermit lege ich Widerspruch gegen [genaue Bezeichnung der Entscheidung, Datum und Zustellung] ein.\n[Statthaftigkeit, zuständige Stelle, Frist und Form vor Verwendung prüfen.]", response: "Zu [Schreiben / Vortrag / gerichtlicher Verfügung vom Datum] nehme ich wie folgt Stellung:\n[Einzelne Punkte und eigene Anträge ergänzen.]" }[kind]
    : { letter: "Please respond to the facts described below.\n[Complete the specific request and desired response.]", application: "I apply for:\n[State the precise application and decision sought.]", objection: "I object to [identify the decision, date and service].\n[Verify the available remedy, authority, deadline and form before use.]", response: "In response to [letter / submissions / court direction and date]:\n[Complete the individual points and any requests.]" }[kind];
  return `${header}\n\n${titles[kind] || titles.letter}: ${item.title}\n\n${de ? "Sehr geehrte Damen und Herren," : "Dear Sir or Madam,"}\n\n${action}\n\n${de ? "Sachverhalt:" : "Facts:"}\n${facts}\n\n${de ? "Ziel / Auftrag:" : "Objective / instructions:"}\n${objective}\n\n${de ? "Begründung / Nachweise:" : "Reasons / evidence:"}\n${de ? "[Argumente, Belege und geprüfte Rechtsgrundlagen ergänzen.]" : "[Complete arguments, evidence and verified legal grounds.]"}\n\n${closing}\n\n${attachments}`;
}
