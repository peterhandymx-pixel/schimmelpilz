import { IconFolders, IconUsers, IconFileText, IconEdit, IconCalendar, IconMessageChatbot, IconFileDescription, IconBuilding, IconPlus, IconListCheck, IconBook2, IconGavel, IconBuildingBank, IconReceipt, IconWorld, IconScale, IconBuildingCommunity, IconReportMoney, IconExternalLink, IconClipboardCheck } from '@tabler/icons-react';

const internal = [
  ['cases', 'Akten', 'Case files', IconFolders, '#b3984c'],
  ['parties', 'Adressen', 'Addresses', IconUsers, '#47879f'],
  ['documents', 'E-Akte', 'Electronic files', IconFileText, '#c7744d'],
  ['drafts', 'Schriftverkehr', 'Correspondence', IconEdit, '#526e95'],
  ['tasks', 'Termine / Fristen', 'Dates / deadlines', IconCalendar, '#7f8c5d'],
  ['research', 'KI-Recherche', 'AI research', IconMessageChatbot, '#087967'],
  ['account', 'Briefpapier & Profil', 'Letter paper & profile', IconFileDescription, '#9b7252'],
  ['activity', 'Aktuelle Akten', 'Recent files', IconListCheck, '#4583a0'],
  ['new', 'Neue Akte anlegen', 'Open a new case', IconPlus, '#438260'],
  ['drafts', 'Entwürfe & Freigaben', 'Drafts & approvals', IconClipboardCheck, '#658454'],
];
const external = [
  ['Gesetze im Internet', 'German federal statutes', IconBook2, '#388652', 'https://www.gesetze-im-internet.de/'],
  ['Urteile & Beschlüsse', 'Judgments & orders', IconGavel, '#9a5151', 'https://www.rechtsprechung-im-internet.de/'],
  ['Gerichtsverzeichnis', 'Court directory', IconBuildingBank, '#427e97', 'https://www.justiz.de/service/verzeichnisse/index.php'],
  ['RVG · Anwaltsgebühren', 'RVG · Lawyer fees', IconReceipt, '#b99142', 'https://www.gesetze-im-internet.de/rvg/'],
  ['GKG · Gerichtskosten', 'GKG · Court fees', IconReportMoney, '#658aaa', 'https://www.gesetze-im-internet.de/gkg_2004/'],
  ['FamGKG · Familienverfahren', 'FamGKG · Family proceedings', IconScale, '#ba8051', 'https://www.gesetze-im-internet.de/famgkg/'],
  ['EUR-Lex · EU-Recht', 'EUR-Lex · EU law', IconWorld, '#487699', 'https://eur-lex.europa.eu/'],
  ['CURIA · EU-Rechtsprechung', 'CURIA · EU case law', IconGavel, '#69659b', 'https://curia.europa.eu/'],
  ['Unternehmensregister', 'Company register', IconBuildingCommunity, '#438ca0', 'https://www.unternehmensregister.de/'],
  ['Justiz · Onlinedienste', 'Justice · Online services', IconBuilding, '#859a4a', 'https://www.justiz.de/onlinedienste/index.php'],
];

export function OfficeModules({ lang, services = false, onNavigate, onNewCase }) {
  const de = lang === 'de';
  return <section className="office-launcher" aria-label={de ? 'Kanzleimodule und Online Services' : 'Office modules and online services'}>
    <div className="office-module-grid">
      {internal.map(([target,german,english,Icon,color],index) => <button className="office-module" key={`local-${index}`} onClick={() => target === 'new' ? onNewCase() : onNavigate(target)}>
        <Icon size={62} stroke={1.55} color={color} aria-hidden="true" /><span>{de ? german : english}</span>
      </button>)}
      {external.map(([german,english,Icon,color,href]) => <a className="office-module office-external" key={href} href={href} target="_blank" rel="noreferrer" aria-label={`${de ? german : english} · ${de ? 'externe Website' : 'external website'}`}>
        <Icon size={62} stroke={1.55} color={color} aria-hidden="true" /><span>{de ? german : english}<IconExternalLink size={13} aria-hidden="true" /></span>
      </a>)}
    </div>
    <p className="office-services-note">{services ? (de ? 'Online Services: Module öffnen Ihren Arbeitsbereich; Links öffnen die jeweiligen Originalangebote in einem neuen Tab.' : 'Online services: modules open your workspace; links open the original providers in a new tab.') : (de ? 'Ihr Arbeitsplatz: Modul auswählen und direkt mit Ihren Akten arbeiten.' : 'Your workspace: choose a module to work with your case files.')} {de ? 'Externe Angebote sind separat verlinkt; Gebühren werden nicht automatisch berechnet. Es werden keine Aktenangaben übermittelt.' : 'External services are linked separately; fees are not calculated automatically. No case particulars are sent.'}</p>
  </section>;
}
