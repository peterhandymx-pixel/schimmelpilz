import { useEffect, useState } from "react";

// Shown on every page of the public demo: what this is, and that nothing is saved.
export function DemoBanner() {
  const [notice, setNotice] = useState(false);
  useEffect(() => {
    let timer;
    const show = () => { setNotice(true); clearTimeout(timer); timer = setTimeout(() => setNotice(false), 4500); };
    window.addEventListener("schimmelpilz-demo-blocked", show);
    return () => { window.removeEventListener("schimmelpilz-demo-blocked", show); clearTimeout(timer); };
  }, []);
  return <>
    <div className="demo-banner" role="note">
      <strong>Demo</strong><span>Kanzlei Muster mit erfundenen Beispielakten · Fristen- und Kostenrechner rechnen echt · Speichern ist in der Demo nicht möglich</span>
      <a href="/">Zur Website</a>
    </div>
    {notice && <div className="demo-toast" role="status">Demo: Hier wird nichts gespeichert. In der eigenen Kanzlei-Version funktioniert diese Aktion.</div>}
  </>;
}
