import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    "process.env": "{}",
  },
  plugins: [react()],
  build: {
    outDir: "dist",
    lib: {
      entry: resolve(__dirname, "src/embed.tsx"),
      name: "RagWidget",
      fileName: () => "widget.js",
      formats: ["iife"],
    },
    rollupOptions: {
      output: {
        banner:
          "var process=globalThis.process||(globalThis.process={env:{}});process.env=process.env||{};process.env.NODE_ENV=process.env.NODE_ENV||'production';",
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 4174,
  },
  preview: {
    host: "0.0.0.0",
    port: 4174,
  },
});
