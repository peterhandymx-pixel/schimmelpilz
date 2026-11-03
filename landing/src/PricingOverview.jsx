import { useEffect, useState } from 'react';
import { IconCheck, IconArrowRight } from '@tabler/icons-react';
import { API_BASE } from './useCaseStorage.js';
import './pricing.css';

const copy = {
  de: {
    kicker: 'PREISE & TESTZUGANG', title: 'Der passende Einstieg für Ihre Arbeit.',
    intro: 'Für eigene Anliegen, Ihr Unternehmen oder Ihre Kanzlei. Monatstarife mit 7 Tagen kostenlosem Testzugang.',
    trial: '7 Tage kostenlos testen', terms: 'Keine Kreditkarte · Keine automatische Abbuchung',
    monthly: 'pro Inhaber-Arbeitsbereich / Monat', cta: 'Testzugang anlegen',
    shared: 'In allen Tarifen: Deutsch & Englisch, Aktenzeichen, Dokumentablage, KI-Recherche mit verfügbaren Originalquellen, bearbeitbare Entwürfe und PDF-Export.',
    pilot: '7 Tage kostenlos testen ab der Registrierung. Danach bezahlen Sie ausdrücklich über einen Clip-Zahlungslink, jeweils einen Monat im Voraus – ohne automatische Verlängerung. Mit der Registrierung entsteht kein kostenpflichtiges Abonnement.',
    note: 'Monatliche Endpreise einschließlich anfallender Steuern. Jede Person hat ein eigenes Konto; Teamzugriff wird vom Inhaber ausdrücklich freigegeben. Die Assistenz ersetzt keine individuelle anwaltliche Beratung.',
    plans: [
      { id: 'consumer', name: 'Privat', price: 9.90, description: 'Eigene Rechte verstehen und den nächsten Schritt vorbereiten.', features: ['Strukturierte Akten für eigene Anliegen', 'Unterlagen und Belege zusammenhalten', 'Rechtsfragen im KI-Chat recherchieren', 'Anschreiben und Einwendungen vorbereiten'] },
      { id: 'business', name: 'Business', price: 29.90, description: 'Verträge, Forderungen und Geschäftspost im Blick behalten.', features: ['Passendes Unternehmensprofil', 'Verträge und Vorgänge in Akten organisieren', 'Korrespondenz mit eigenem Briefpapier', 'Entwürfe mit Prüfvermerken und Versionen'] },
      { id: 'law_firm', name: 'Kanzlei', price: 49.90, description: 'Mandatsakten, Recherche und Schriftsätze an einem Ort.', features: ['Passendes Kanzlei- und Berufsprofil', 'Deutsche Normen und Entscheidungen suchen', 'Textblöcke neben Originalpassagen prüfen', 'Schriftsatzversionen und eigene Freigaben'] },
    ],
  },
  en: {
    kicker: 'PRICING & TRIAL', title: 'A practical starting point for your work.',
    intro: 'For personal matters, your business or your law firm. Monthly plans with a 7-day free trial.',
    trial: 'Try free for 7 days', terms: 'No credit card · No automatic charge',
    monthly: 'per owner workspace / month', cta: 'Create trial account',
    shared: 'Every plan: German & English, case references, document storage, AI research with available original sources, editable drafts and PDF export.',
    pilot: '7 free trial days from registration. After that you pay explicitly through a Clip payment link, one month in advance, with no automatic renewal. Registering does not create a paid subscription.',
    note: 'Monthly final prices, including applicable taxes. Each person has their own login; owners explicitly grant team access. The assistant does not replace individual advice from a qualified lawyer.',
    plans: [
      { id: 'consumer', name: 'Personal', price: 9.90, description: 'Understand your rights and prepare your next step.', features: ['Structured files for personal matters', 'Keep documents and evidence together', 'Research legal questions in AI chat', 'Prepare letters and objections'] },
      { id: 'business', name: 'Business', price: 29.90, description: 'Keep track of contracts, receivables and correspondence.', features: ['Tailored business profile', 'Organise contracts and matters in files', 'Correspondence on your own letter paper', 'Drafts with review notes and versions'] },
      { id: 'law_firm', name: 'Law firm', price: 49.90, description: 'Client files, research and drafting in one place.', features: ['Tailored firm and professional profile', 'Search German statutes and decisions', 'Review text blocks beside original passages', 'Document versions and your own approvals'] },
    ],
  },
};

// Registration audiences map to billing plans; prices and currency come from the operator's configuration.
const PLAN_FOR = { consumer: 'personal', business: 'business', law_firm: 'firm' };

export function PricingOverview({ lang, onSelect }) {
  const c = copy[lang];
  const [pricing, setPricing] = useState(null);
  useEffect(() => {
    const abort = new AbortController();
    fetch(`${API_BASE}/api/public/pricing`, { signal: abort.signal }).then(response => response.ok ? response.json() : null).then(value => { if (value) setPricing(value); }).catch(() => { /* Keep the default prices. */ });
    return () => abort.abort();
  }, []);
  const format = new Intl.NumberFormat(lang === 'de' ? 'de-DE' : 'en-IE', { style: 'currency', currency: pricing?.currency || 'EUR', currencyDisplay: pricing?.currency && pricing.currency !== 'EUR' ? 'code' : 'symbol' });
  const price = plan => pricing?.plans?.[PLAN_FOR[plan.id]] != null ? pricing.plans[PLAN_FOR[plan.id]] / 100 : plan.price;
  return <section className="pricing-section" id="pricing" aria-labelledby="pricing-title">
    <header className="pricing-heading"><p className="section-kicker">{c.kicker}</p><h2 id="pricing-title">{c.title}</h2><p>{c.intro}</p></header>
    <div className="pricing-trial"><strong>{c.trial}</strong><span>{c.terms}</span></div>
    <div className="pricing-grid">{c.plans.map(plan => <article className="pricing-card" key={plan.id}>
      <h3>{plan.name}</h3><p className="pricing-description">{plan.description}</p>
      <p className="pricing-amount">{format.format(price(plan))}<small>{c.monthly}</small></p>
      <ul>{plan.features.map(feature => <li key={feature}><IconCheck size={17} aria-hidden="true" /><span>{feature}</span></li>)}</ul>
      <button className="pricing-cta" onClick={() => onSelect(plan.id)} aria-label={`${c.cta} · ${plan.name}`}>{c.cta}<IconArrowRight size={18} aria-hidden="true" /></button>
    </article>)}</div>
    <p className="pricing-shared">{c.shared}</p>
    <p className="pricing-pilot">{c.pilot}</p>
    <p className="pricing-note">{c.note}</p>
  </section>;
}
