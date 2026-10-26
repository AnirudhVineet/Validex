import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// /api is proxied to the backend so the browser only talks to one origin.
// In docker, API_TARGET is set to the backend service URL.
// Ports 8010 / 5180 avoid clashing with other local projects on 8000 / 5173.
const apiTarget = process.env.API_TARGET || "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5180,
    strictPort: true,
    proxy: { "/api": apiTarget },
  },
});
