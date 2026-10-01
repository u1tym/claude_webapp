import { createRouter, createWebHistory } from "vue-router";
import RoomView from "./views/RoomView.vue";
import SchedulesView from "./views/SchedulesView.vue";

export const routes = [
  { path: "/", component: RoomView, meta: { title: "ROOM" } },
  { path: "/schedules", component: SchedulesView, meta: { title: "定期実行" } },
];

export function createAppRouter(history = createWebHistory(import.meta.env.BASE_URL)) {
  return createRouter({ history, routes });
}

export const router = createAppRouter();
