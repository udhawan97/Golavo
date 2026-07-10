import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server binds to loopback; the desktop shell proxies to the sidecar.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173 },
});
