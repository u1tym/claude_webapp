import { createRouter, createWebHistory } from "vue-router";
import ApiKeyListView from "./views/ApiKeyListView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", name: "api-keys", component: ApiKeyListView },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
