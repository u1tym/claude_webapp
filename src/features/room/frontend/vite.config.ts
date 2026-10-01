import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue()],
  // 公開 URL（rules/17-nginx-deploy.md）
  base: "/portal_room/",
  server: {
    port: 5185,
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
  },
});
