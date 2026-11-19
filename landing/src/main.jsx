import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./styles.css";
import "./workbench.css";
import "./research-chat.css";
import "./document-review.css";
import "./letterhead.css";
import "./legal-sources.css";

const root = createRoot(document.getElementById("root"));
const start = Banner => root.render(
  <React.StrictMode>
    {Banner && <Banner />}
    <App />
  </React.StrictMode>,
);

// The public demo build (VITE_DEMO=1) asks for the beta-test code, then answers the API from recorded sample data.
// The normal app is unaffected.
if (import.meta.env.VITE_DEMO) {
  Promise.all([import("./demo/demoApi.js"), import("./demo/DemoBanner.jsx"), import("./demo/BetaGate.jsx"), import("./demo/demo.css")])
    .then(([api, banner, gate]) => {
      const enter = () => { api.install(); start(banner.DemoBanner); };
      if (gate.hasAccess()) enter();
      else root.render(<gate.BetaGate onEnter={enter} />);
    });
} else {
  start(null);
}
