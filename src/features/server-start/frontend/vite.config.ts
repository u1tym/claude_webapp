import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/portal_server_start/",
  server: {
    port: 5176,
  },
});
