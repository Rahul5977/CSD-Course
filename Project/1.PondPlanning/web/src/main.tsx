import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Landing from "./Landing";
import "./tokens.css";
import "./ui.css";
import "./styles.css";

// Offline-first: cache tiles and the last good API responses (see public/sw.js).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}

// Two routes, no router: `/` is the public landing page, `/app` the workspace.
const path = window.location.pathname.replace(/\/+$/, "");
const Page = path === "/app" ? App : Landing;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Page />
  </React.StrictMode>,
);
