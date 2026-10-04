import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server mirrors the nginx routing in infra/nginx.conf, so the app code
// only ever knows two relative prefixes: /api and /tiles.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", ws: true },
      "/tiles": { target: "http://localhost:8080", rewrite: (p) => p.replace(/^\/tiles/, "") },
    },
  },
});
