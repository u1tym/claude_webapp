import { createRouter, createWebHistory } from "vue-router";
import BudgetsView from "./views/BudgetsView.vue";
import ExpensesView from "./views/ExpensesView.vue";
import PaymentMethodsView from "./views/PaymentMethodsView.vue";
import ReportsView from "./views/ReportsView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", component: ExpensesView, meta: { title: "支出記録" } },
    { path: "/budgets", component: BudgetsView, meta: { title: "予算管理" } },
    { path: "/payment-methods", component: PaymentMethodsView, meta: { title: "支出方法管理" } },
    { path: "/reports", component: ReportsView, meta: { title: "集計" } },
  ],
});
