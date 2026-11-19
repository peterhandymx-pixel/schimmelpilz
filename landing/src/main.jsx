import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./styles.css";
import "./workbench.css";
import "./research-chat.css";
import "./document-review.css";
import "./letterhead.css";
import "./legal-sources.css";

const start = Banner => createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {Banner && <Banner />}
    <App />
  </React.StrictMode>,
);

// The public demo build (VITE_DEMO=1) answers the API from recorded sample data; the normal app is unaffected.
if (import.meta.env.VITE_DEMO) {
  Promise.all([import("./demo/demoApi.js"), import("./demo/DemoBanner.jsx"), import("./demo/demo.css")])
    .then(([api, banner]) => { api.install(); start(banner.DemoBanner); });
} else {
  start(null);
}
