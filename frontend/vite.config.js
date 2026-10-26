import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// /api is proxied to the backend so the browser only talks to one origin.
// In docker, API_TARGET is set to the backend service URL.
// Backend on 8000, frontend on 5173 (strictPort: fail instead of silently moving ports).
const apiTarget = process.env.API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: { "/api": apiTarget },
  },
});
