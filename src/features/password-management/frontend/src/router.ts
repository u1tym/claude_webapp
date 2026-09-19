import { createRouter, createWebHistory } from "vue-router";
import PasswordsView from "./views/PasswordsView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [{ path: "/", component: PasswordsView }],
});
