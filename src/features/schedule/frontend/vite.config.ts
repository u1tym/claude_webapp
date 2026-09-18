import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/portal_schedule/",
  server: {
    port: 5175,
  },
});
