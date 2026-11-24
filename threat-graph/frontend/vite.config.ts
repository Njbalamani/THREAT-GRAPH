import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          cytoscape: ["cytoscape"],
          charts: ["chart.js", "react-chartjs-2"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
