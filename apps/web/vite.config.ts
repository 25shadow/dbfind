import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const devServerPort = Number(process.env.VITE_DEV_SERVER_PORT ?? 5173);
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: devServerPort,
    proxy: {
      "/api": apiProxyTarget
    }
  }
});
