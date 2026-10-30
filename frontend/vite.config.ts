import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Note: no manualChunks - splitting React Three Fiber away from React creates a circular
// chunk dependency that breaks React internals at runtime (verified in browser testing).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true },
  build: { chunkSizeWarningLimit: 1600 },
  test: { environment: "node" },
} as any);
