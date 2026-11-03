import logoUrl from "./assets/schimmelpilz-logo.webp";
import markUrl from "./assets/schimmelpilz-mark.webp";

const LABEL = "Rechtsassistentin Schimmelpilz – Entwickelt von einem ausgebildeten Rechtsanwaltsfachangestellten";

// CI logo: full lockup (artwork, name and claim) by default; `compact` shows only the artwork for tight spots.
// Wide places size it with CSS width; the office header swaps to the mark on narrow screens.
export function BrandLogo({ className = "brand-logo", compact = false }) {
  return <span className={`brand-lockup ${compact ? "compact" : ""} ${className}`}>
    <img className="brand-full" src={logoUrl} alt={LABEL} width="1000" height="388" />
    <img className="brand-mark" src={markUrl} alt={LABEL} width="320" height="259" />
  </span>;
}
