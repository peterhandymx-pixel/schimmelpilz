import logoUrl from "./assets/schimmelpilz-logo.png?inline";

// Bundle the supplied logo with the app so it needs no separate asset request.
export function BrandLogo({ className = "brand-logo" }) {
  return <img className={className} src={logoUrl} alt="Virtuelle Rechtsassistenz Schimmelpilz" width="2172" height="724" />;
}
