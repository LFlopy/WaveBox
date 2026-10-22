import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    proxy: {
      "/api/auth": {
        target: "http://auth:8000",
        changeOrigin: true,
      },

      "/api/tracks": {
        target: "http://api:8080",
        changeOrigin: true,
      },
      "/audio": {
        target: "http://api:8080",
        changeOrigin: true,
      },
      "/covers": {
        target: "http://api:8080",
        changeOrigin: true,
      },
    },
  },
});
