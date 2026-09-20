import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/portal_goods_management/",
  server: {
    port: 5180,
  },
});
