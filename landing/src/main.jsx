import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./styles.css";
import "./workbench.css";
import "./research-chat.css";
import "./document-review.css";
import "./letterhead.css";
import "./legal-sources.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
