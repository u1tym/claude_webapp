import { createRouter, createWebHistory } from "vue-router";

// nav: 現在地として強調するナビ項目（下位の画面は、その入口となる項目を現在地にする）
export type NavKey = "notes";

declare module "vue-router" {
  interface RouteMeta {
    nav: NavKey;
  }
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", component: () => import("./views/NoteListView.vue"), meta: { nav: "notes" } },
    {
      path: "/files/:id",
      component: () => import("./views/FileView.vue"),
      props: true,
      meta: { nav: "notes" },
    },
  ],
});
