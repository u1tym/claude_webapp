import { createRouter, createWebHistory } from "vue-router";
import KnowhowView from "./views/KnowhowView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [{ path: "/", component: KnowhowView }],
});
