import { createRouter, createWebHistory } from "vue-router";
import AccountsView from "./views/AccountsView.vue";
import CancellationView from "./views/CancellationView.vue";
import CategoriesView from "./views/CategoriesView.vue";
import ContractsView from "./views/ContractsView.vue";

// ui-design.md の画面一覧。本機能を開いたとき（公開パスの基点）は、アカウント一覧を表示する。
export const routes = [
  { path: "/", name: "accounts", component: AccountsView, meta: { title: "アカウント一覧" } },
  { path: "/contracts", name: "contracts", component: ContractsView, meta: { title: "契約一覧" } },
  { path: "/categories", name: "categories", component: CategoriesView, meta: { title: "区分" } },
  { path: "/cancellation", name: "cancellation", component: CancellationView, meta: { title: "解約順" } },
];

export function createAppRouter(history = createWebHistory(import.meta.env.BASE_URL)) {
  return createRouter({ history, routes });
}

export const router = createAppRouter();
