import { createRouter, createWebHistory } from "vue-router";
import GoodsListView from "./views/GoodsListView.vue";
import GoodsFormView from "./views/GoodsFormView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", component: GoodsListView },
    { path: "/goods/new", component: GoodsFormView },
    { path: "/goods/:id/edit", component: GoodsFormView, props: true },
  ],
});
