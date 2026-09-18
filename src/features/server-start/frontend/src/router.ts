import { createRouter, createWebHistory } from "vue-router";
import PowerView from "./views/PowerView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [{ path: "/", component: PowerView }],
});
