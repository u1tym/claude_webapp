import { createRouter, createWebHistory } from "vue-router";
import CalendarView from "./views/CalendarView.vue";

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [{ path: "/", component: CalendarView, meta: { title: "Schedule" } }],
});
