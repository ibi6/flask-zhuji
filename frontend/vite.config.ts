import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const dirname = path.dirname(fileURLToPath(import.meta.url));

const isGitHubPages = process.env.GITHUB_PAGES === "true";

// https://vite.dev/config/
export default defineConfig({
  base: isGitHubPages ? "/flask-zhuji/" : "/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(dirname, "src"),
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  server: {
    port: 5180,
    strictPort: true,
    host: "127.0.0.1",
    proxy: {
      // 开发模式下把 API 请求转发到 Flask 后端
      "/api": {
        target: process.env.HOSTGUARD_API_TARGET || "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.HOSTGUARD_API_TARGET || "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    env: {
      VITE_USE_MOCK: "true",
    },
  },
});
