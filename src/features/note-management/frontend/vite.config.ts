import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/portal_note_management/",
  server: {
    port: 5183,
  },
});
