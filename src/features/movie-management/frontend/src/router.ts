import { createRouter, createWebHistory } from "vue-router";

// nav: 現在地として強調するナビ項目（下位の画面は、その入口となる項目を現在地にする）
export type NavKey = "videos" | "playlists" | "history" | "series" | "genres";

declare module "vue-router" {
  interface RouteMeta {
    nav: NavKey;
  }
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", component: () => import("./views/VideoListView.vue"), meta: { nav: "videos" } },
    { path: "/register", component: () => import("./views/VideoRegisterView.vue"), meta: { nav: "videos" } },
    {
      path: "/videos/:id",
      component: () => import("./views/VideoPlayerView.vue"),
      props: true,
      meta: { nav: "videos" },
    },
    {
      path: "/videos/:id/edit",
      component: () => import("./views/VideoEditView.vue"),
      props: true,
      meta: { nav: "videos" },
    },
    { path: "/history", component: () => import("./views/HistoryView.vue"), meta: { nav: "history" } },
    { path: "/series", component: () => import("./views/SeriesListView.vue"), meta: { nav: "series" } },
    {
      path: "/series/:id",
      component: () => import("./views/SeriesDetailView.vue"),
      props: true,
      meta: { nav: "series" },
    },
    { path: "/genres", component: () => import("./views/GenreView.vue"), meta: { nav: "genres" } },
    { path: "/playlists", component: () => import("./views/PlaylistListView.vue"), meta: { nav: "playlists" } },
    {
      path: "/playlists/:id/edit",
      component: () => import("./views/PlaylistEditView.vue"),
      props: true,
      meta: { nav: "playlists" },
    },
    {
      path: "/playlists/:id/play",
      component: () => import("./views/PlaylistPlayerView.vue"),
      props: true,
      meta: { nav: "playlists" },
    },
  ],
});
