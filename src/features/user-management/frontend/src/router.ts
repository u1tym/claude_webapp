import { createRouter, createWebHistory } from "vue-router";
import AssignmentsView from "./views/AssignmentsView.vue";
import FeaturesView from "./views/FeaturesView.vue";
import UsersView from "./views/UsersView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", redirect: "/users" },
    { path: "/users", component: UsersView, meta: { title: "ユーザ" } },
    { path: "/features", component: FeaturesView, meta: { title: "機能" } },
    { path: "/assignments", component: AssignmentsView, meta: { title: "割当" } },
  ],
});
