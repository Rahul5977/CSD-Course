import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

// Offline-first: cache tiles and the last good API responses (see public/sw.js).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
