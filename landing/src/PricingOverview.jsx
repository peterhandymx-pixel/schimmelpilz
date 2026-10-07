import { IconCheck, IconArrowRight } from '@tabler/icons-react';
import './pricing.css';

const copy = {
  de: {
    kicker: 'PREISE & TESTZUGANG', title: 'Der passende Einstieg für Ihre Arbeit.',
    intro: 'Für eigene Anliegen, Ihr Unternehmen oder Ihre Kanzlei. Geplante Monatstarife zum Produktstart – mit 7 Tagen kostenlosem Testzugang.',
    trial: '7 Tage kostenlos testen', terms: 'Keine Kreditkarte · Keine automatische Abbuchung',
    monthly: 'pro Einzelkonto / Monat', cta: 'Testzugang anlegen',
    shared: 'In allen Tarifen: Deutsch & Englisch, Aktenzeichen, Dokumentablage, KI-Recherche mit verfügbaren Originalquellen, bearbeitbare Entwürfe und PDF-Export.',
    pilot: 'Aktuell kostenlose Pilotphase. Die kostenpflichtigen Tarife und die siebentägige Testphase zum Produktstart sind noch nicht aktiviert. Mit der Registrierung entsteht kein kostenpflichtiges Abonnement.',
    note: 'Geplante Endpreise in Euro einschließlich anfallender Steuern. Ein Zugang für eine Person; gemeinsame Teamkonten sind noch nicht verfügbar. Die Assistenz ersetzt keine individuelle anwaltliche Beratung.',
    plans: [
      { id: 'consumer', name: 'Privat', price: 9.90, description: 'Eigene Rechte verstehen und den nächsten Schritt vorbereiten.', features: ['Strukturierte Akten für eigene Anliegen', 'Unterlagen und Belege zusammenhalten', 'Rechtsfragen im KI-Chat recherchieren', 'Anschreiben und Einwendungen vorbereiten'] },
      { id: 'business', name: 'Business', price: 29.90, description: 'Verträge, Forderungen und Geschäftspost im Blick behalten.', features: ['Passendes Unternehmensprofil', 'Verträge und Vorgänge in Akten organisieren', 'Korrespondenz mit eigenem Briefpapier', 'Entwürfe mit Prüfvermerken und Versionen'] },
      { id: 'law_firm', name: 'Kanzlei', price: 49.90, description: 'Mandatsakten, Recherche und Schriftsätze an einem Ort.', features: ['Passendes Kanzlei- und Berufsprofil', 'Deutsche Normen und Entscheidungen suchen', 'Textblöcke neben Originalpassagen prüfen', 'Schriftsatzversionen und eigene Freigaben'] },
    ],
  },
  en: {
    kicker: 'PRICING & TRIAL', title: 'A practical starting point for your work.',
    intro: 'For personal matters, your business or your law firm. Planned monthly launch prices – with a 7-day free trial.',
    trial: 'Try free for 7 days', terms: 'No credit card · No automatic charge',
    monthly: 'per individual account / month', cta: 'Create trial account',
    shared: 'Every plan: German & English, case references, document storage, AI research with available original sources, editable drafts and PDF export.',
    pilot: 'Currently a free pilot. Paid plans and the seven-day launch trial are not active yet. Registering does not create a paid subscription.',
    note: 'Planned final prices in euros, including applicable taxes. One person per account; shared team accounts are not available yet. The assistant does not replace individual advice from a qualified lawyer.',
    plans: [
      { id: 'consumer', name: 'Personal', price: 9.90, description: 'Understand your rights and prepare your next step.', features: ['Structured files for personal matters', 'Keep documents and evidence together', 'Research legal questions in AI chat', 'Prepare letters and objections'] },
      { id: 'business', name: 'Business', price: 29.90, description: 'Keep track of contracts, receivables and correspondence.', features: ['Tailored business profile', 'Organise contracts and matters in files', 'Correspondence on your own letter paper', 'Drafts with review notes and versions'] },
      { id: 'law_firm', name: 'Law firm', price: 49.90, description: 'Client files, research and drafting in one place.', features: ['Tailored firm and professional profile', 'Search German statutes and decisions', 'Review text blocks beside original passages', 'Document versions and your own approvals'] },
    ],
  },
};

export function PricingOverview({ lang, onSelect }) {
  const c = copy[lang];
  const format = new Intl.NumberFormat(lang === 'de' ? 'de-DE' : 'en-IE', { style: 'currency', currency: 'EUR' });
  return <section className="pricing-section" id="pricing" aria-labelledby="pricing-title">
    <header className="pricing-heading"><p className="section-kicker">{c.kicker}</p><h2 id="pricing-title">{c.title}</h2><p>{c.intro}</p></header>
    <div className="pricing-trial"><strong>{c.trial}</strong><span>{c.terms}</span></div>
    <div className="pricing-grid">{c.plans.map(plan => <article className="pricing-card" key={plan.id}>
      <h3>{plan.name}</h3><p className="pricing-description">{plan.description}</p>
      <p className="pricing-amount">{format.format(plan.price)}<small>{c.monthly}</small></p>
      <ul>{plan.features.map(feature => <li key={feature}><IconCheck size={17} aria-hidden="true" /><span>{feature}</span></li>)}</ul>
      <button className="pricing-cta" onClick={() => onSelect(plan.id)} aria-label={`${c.cta} · ${plan.name}`}>{c.cta}<IconArrowRight size={18} aria-hidden="true" /></button>
    </article>)}</div>
    <p className="pricing-shared">{c.shared}</p>
    <p className="pricing-pilot">{c.pilot}</p>
    <p className="pricing-note">{c.note}</p>
  </section>;
}
