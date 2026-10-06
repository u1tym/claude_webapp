import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { expect, vi } from "vitest";
import { apiUrl } from "../src/api";
import RoomView from "../src/views/RoomView.vue";
import type { DeviceKey, DeviceState, Devices } from "../src/room";

export const ERROR: DeviceState = { status: "error", state: null };

export function devices(override: Partial<Devices> = {}): Devices {
  return {
    ceiling_light: { status: "ok", state: "off" },
    indirect_light: { status: "ok", state: "on" },
    indoor_speaker: { status: "ok", state: "off" },
    bedside_speaker: { status: "ok", state: "off" },
    front_door: { status: "ok", state: "locked", battery: 35 },
    ...override,
  };
}

/** GET /dimming-patterns の応答（固定の 4 種。値は requirements.md の用語表のとおり）。 */
export const PATTERNS_RESPONSE = {
  default: "full",
  patterns: [
    { id: "full", name: "全灯", brightness: 100, color_temperature: 6200 },
    { id: "reading", name: "読書", brightness: 80, color_temperature: 5000 },
    { id: "relax", name: "くつろぎ", brightness: 50, color_temperature: 3000 },
    { id: "night", name: "夜", brightness: 10, color_temperature: 2700 },
  ],
};

export type Call = { method: string; path: string; body: unknown };

export function res(body: unknown, status = 200): Partial<Response> {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

export type Handler = (call: Call) => Partial<Response> | Promise<Partial<Response>>;

/** fetch を差し替える。呼び出しを記録し、ハンドラが応答を返す。 */
export function mockApi(handler: Handler): { calls: Call[] } {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const call: Call = {
        method: init.method ?? "GET",
        path: url.replace(apiUrl(""), ""),
        body: init.body ? JSON.parse(init.body as string) : undefined,
      };
      calls.push(call);
      expect(init.credentials).toBe("include");
      return handler(call);
    }),
  );
  return { calls };
}

export const STATE_AT = "2026-10-01T10:15:30+09:00";
export const SWITCH_AT = "2026-10-01T10:16:45+09:00";

/** 既定: GET /state は devices、PUT は目標どおりに切り替えた結果を返す。 */
export function defaultHandler(initial: Devices = devices()): Handler {
  const current = { ...initial };
  return ({ method, path, body }) => {
    if (method === "GET" && path === "/state") {
      return res({ fetched_at: STATE_AT, devices: current });
    }
    if (method === "GET" && path === "/dimming-patterns") {
      return res(PATTERNS_RESPONSE);
    }
    const match = path.match(/^\/devices\/(\w+)\/state$/);
    if (method === "PUT" && match) {
      const key = match[1] as DeviceKey;
      const result = { ...current[key], state: (body as { state: string }).state } as DeviceState;
      current[key] = result;
      return res({ device: key, applied: true, fetched_at: SWITCH_AT, result });
    }
    return res({}, 404);
  };
}

export async function mountView(): Promise<VueWrapper> {
  const wrapper = mount(RoomView);
  await flushPromises();
  return wrapper;
}

export const part = (w: VueWrapper, key: DeviceKey) => w.get(`[data-device="${key}"]`);
export const fetchedAt = (w: VueWrapper) => w.get('[data-testid="fetched-at"]').text();
export const refreshButton = (w: VueWrapper) => w.get(".room-fetch button");
export const status = (w: VueWrapper) => w.get(".room-status");

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

