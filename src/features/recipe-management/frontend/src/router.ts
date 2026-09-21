import { createRouter, createWebHistory } from "vue-router";

// nav: 現在地として強調するナビ項目（下位の画面は、その入口となる項目を現在地にする）
export type NavKey = "recipes";

declare module "vue-router" {
  interface RouteMeta {
    nav: NavKey;
  }
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", component: () => import("./views/RecipeListView.vue"), meta: { nav: "recipes" } },
    // `/recipes/new` は `/recipes/:id` より先に定義する
    { path: "/recipes/new", component: () => import("./views/RecipeRegisterView.vue"), meta: { nav: "recipes" } },
    {
      path: "/recipes/:id",
      component: () => import("./views/RecipeDetailView.vue"),
      props: true,
      meta: { nav: "recipes" },
    },
    {
      path: "/recipes/:id/edit",
      component: () => import("./views/RecipeEditView.vue"),
      props: true,
      meta: { nav: "recipes" },
    },
  ],
});
