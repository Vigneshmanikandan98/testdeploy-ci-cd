import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api calls are forwarded to FastAPI on port 8000.
// In production there is no proxy: FastAPI serves this build itself.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
  build: { outDir: "dist" },
});
