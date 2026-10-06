import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import RoomView from "../src/views/RoomView.vue";
import {
  ERROR,
  PATTERNS_RESPONSE,
  SWITCH_AT,
  defaultHandler,
  deferred,
  devices,
  mockApi,
  mountView,
  part,
  res,
  status,
  type Call,
  type Handler,
} from "./helpers";
import type { Devices } from "../src/room";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const dialog = (w: VueWrapper) => w.find("[role=dialog]");
const option = (w: VueWrapper, id: string) => w.get(`[data-pattern="${id}"]`);
const offButton = (w: VueWrapper) => w.find('[data-action="off"]');
const cancelButton = (w: VueWrapper) => w.get('[role=dialog] button[aria-label="キャンセル"]');
const puts = (calls: Call[]) => calls.filter((c) => c.method === "PUT");

const CEILING_ON = devices({ ceiling_light: { status: "ok", state: "on" } });

async function openDialog(w: VueWrapper): Promise<void> {
  await part(w, "ceiling_light").trigger("click");
  await flushPromises();
}

describe("電灯のパーツを押したとき", () => {
  it("調光パターンダイアログを開く。PUT はしない", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);

    expect(dialog(wrapper).exists()).toBe(true);
    expect(dialog(wrapper).attributes("aria-label")).toBe("調光パターンを選択");
    expect(dialog(wrapper).text()).toContain("調光パターンを選択");
    expect(puts(calls)).toHaveLength(0);
  });

  it("パターンは API から取得し、4 種を全灯・読書・くつろぎ・夜の順に、明るさと色温度の目安つきで並べる", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);

    expect(calls.filter((c) => c.path === "/dimming-patterns")).toEqual([
      { method: "GET", path: "/dimming-patterns", body: undefined },
    ]);
    const options = wrapper.findAll(".dimming-option");
    expect(options.map((o) => o.get(".dimming-name").text())).toEqual(["全灯", "読書", "くつろぎ", "夜"]);
    expect(options.map((o) => o.get(".dimming-caption").text())).toEqual([
      "明るさ 100・色温度 6200",
      "明るさ 80・色温度 5000",
      "明るさ 50・色温度 3000",
      "明るさ 10・色温度 2700",
    ]);
  });

  it("消灯中は「消灯」を出さない", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);
    expect(offButton(wrapper).exists()).toBe(false);
  });

  it("点灯中は「消灯」を出す", async () => {
    mockApi(defaultHandler(CEILING_ON));
    const wrapper = await mountView();
    await openDialog(wrapper);
    expect(offButton(wrapper).exists()).toBe(true);
    expect(offButton(wrapper).text()).toBe("消灯");
  });

  it("パターンの取得は 1 回だけ（2 回目以降は取り直さない）", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);
    await cancelButton(wrapper).trigger("click");
    await openDialog(wrapper);
    expect(dialog(wrapper).exists()).toBe(true);
    expect(calls.filter((c) => c.path === "/dimming-patterns")).toHaveLength(1);
  });

  it("パターンを取得できなければ、ダイアログを開かず、ステータスに一文を示す", async () => {
    mockApi((call) =>
      call.path === "/dimming-patterns" ? res({ detail: "x" }, 500) : defaultHandler()(call),
    );
    const wrapper = await mountView();
    await openDialog(wrapper);

    expect(dialog(wrapper).exists()).toBe(false);
    expect(status(wrapper).text()).toBe("調光パターンを取得できませんでした。");
    expect(status(wrapper).classes()).toContain("is-error");
  });

  it.each([401, 403] as const)("パターンの取得で %s なら親（殻）へ auth-error を伝える", async (code) => {
    mockApi((call) =>
      call.path === "/dimming-patterns" ? res({ detail: "x" }, code) : defaultHandler()(call),
    );
    const wrapper = await mountView();
    await openDialog(wrapper);

    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
    expect(dialog(wrapper).exists()).toBe(false);
  });

  it("取得できなかった電灯は、ダイアログを開かない", async () => {
    const { calls } = mockApi(defaultHandler(devices({ ceiling_light: ERROR })));
    const wrapper = await mountView();
    await openDialog(wrapper);
    expect(dialog(wrapper).exists()).toBe(false);
    expect(calls.filter((c) => c.path === "/dimming-patterns")).toHaveLength(0);
  });
});

describe("パターンの選択", () => {
  it.each(PATTERNS_RESPONSE.patterns)("「$name」を選ぶと、そのパターンで電灯を ON にする", async ({ id, name }) => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);

    await option(wrapper, id).trigger("click");
    await flushPromises();

    expect(puts(calls)).toEqual([
      { method: "PUT", path: "/devices/ceiling_light/state", body: { state: "on", pattern: id } },
    ]);
    expect(dialog(wrapper).exists()).toBe(false);
    expect(part(wrapper, "ceiling_light").text()).toContain("ON");
    expect(status(wrapper).text()).toBe(`電灯を ON（${name}）にしました。`);
    expect(status(wrapper).classes()).not.toContain("is-error");
  });

  it("点灯中に別のパターンを選ぶと、電灯は ON のまま、そのパターンで PUT する", async () => {
    const { calls } = mockApi(defaultHandler(CEILING_ON));
    const wrapper = await mountView();
    await openDialog(wrapper);

    await option(wrapper, "night").trigger("click");
    await flushPromises();

    expect(puts(calls)[0]!.body).toEqual({ state: "on", pattern: "night" });
    expect(part(wrapper, "ceiling_light").text()).toContain("ON");
    expect(status(wrapper).text()).toBe("電灯を ON（夜）にしました。");
  });

  it("実行中は、選択肢と「消灯」を無効にし、ダイアログは開いたまま。終わると閉じる", async () => {
    const pending = deferred<Partial<Response>>();
    const handler = defaultHandler(CEILING_ON);
    mockApi((call) => (call.method === "PUT" ? pending.promise : handler(call)));
    const wrapper = await mountView();
    await openDialog(wrapper);

    await option(wrapper, "reading").trigger("click");
    await flushPromises();

    expect(dialog(wrapper).exists()).toBe(true);
    for (const o of wrapper.findAll(".dimming-option")) {
      expect(o.attributes("disabled")).toBeDefined();
    }
    expect(offButton(wrapper).attributes("disabled")).toBeDefined();
    expect(cancelButton(wrapper).attributes("disabled")).toBeDefined();
    expect(part(wrapper, "ceiling_light").text()).toContain("切替中…");

    pending.resolve(
      res({
        device: "ceiling_light",
        applied: true,
        fetched_at: SWITCH_AT,
        result: { status: "ok", state: "on" },
      }),
    );
    await flushPromises();
    expect(dialog(wrapper).exists()).toBe(false);
  });

  it("実行中に押し直しても、PUT は 1 回だけ", async () => {
    const pending = deferred<Partial<Response>>();
    const handler = defaultHandler();
    const { calls } = mockApi((call) => (call.method === "PUT" ? pending.promise : handler(call)));
    const wrapper = await mountView();
    await openDialog(wrapper);

    await option(wrapper, "full").trigger("click");
    await option(wrapper, "reading").trigger("click"); // 無効なので何も起きない
    await flushPromises();
    expect(puts(calls)).toHaveLength(1);
  });

  it("切替に失敗したら、ダイアログを閉じ、ステータスに一文を示し、図は元の状態のまま", async () => {
    const handler = defaultHandler();
    const { calls } = mockApi((call) => (call.method === "PUT" ? res({ detail: "x" }, 502) : handler(call)));
    const wrapper = await mountView();
    await openDialog(wrapper);

    await option(wrapper, "reading").trigger("click");
    await flushPromises();

    expect(puts(calls)).toHaveLength(1);
    expect(dialog(wrapper).exists()).toBe(false);
    expect(status(wrapper).text()).toBe("機器を操作できませんでした。");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(part(wrapper, "ceiling_light").text()).toContain("OFF");
  });

  it("指示は通ったが、状態が目標になっていないときは、その旨を示す", async () => {
    const handler = defaultHandler();
    mockApi((call) =>
      call.method === "PUT"
        ? res({ device: "ceiling_light", applied: true, fetched_at: SWITCH_AT, result: { status: "ok", state: "off" } })
        : handler(call),
    );
    const wrapper = await mountView();
    await openDialog(wrapper);
    await option(wrapper, "full").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toContain("状態が変わっていません");
    expect(part(wrapper, "ceiling_light").text()).toContain("OFF");
  });
});

describe("消灯", () => {
  it("「消灯」を押すと、パターンを付けずに OFF にする", async () => {
    const { calls } = mockApi(defaultHandler(CEILING_ON));
    const wrapper = await mountView();
    await openDialog(wrapper);

    await offButton(wrapper).trigger("click");
    await flushPromises();

    expect(puts(calls)).toEqual([
      { method: "PUT", path: "/devices/ceiling_light/state", body: { state: "off" } },
    ]);
    expect(dialog(wrapper).exists()).toBe(false);
    expect(part(wrapper, "ceiling_light").text()).toContain("OFF");
    expect(status(wrapper).text()).toBe("電灯を OFF にしました。");
  });
});

describe("閉じる操作", () => {
  it("キャンセルで、何も実行せずに閉じる", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);

    await cancelButton(wrapper).trigger("click");
    await flushPromises();

    expect(dialog(wrapper).exists()).toBe(false);
    expect(puts(calls)).toHaveLength(0);
    expect(part(wrapper, "ceiling_light").text()).toContain("OFF");
  });

  it("Esc でも、何も実行せずに閉じる", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);

    await dialog(wrapper).trigger("keydown", { key: "Escape" });
    await flushPromises();

    expect(dialog(wrapper).exists()).toBe(false);
    expect(puts(calls)).toHaveLength(0);
  });

  it("背景（オーバーレイ）を押しても閉じない", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);

    await wrapper.get(".dialog-overlay").trigger("click");
    await flushPromises();

    expect(dialog(wrapper).exists()).toBe(true);
  });
});

describe("表示しないもの", () => {
  it("電灯の現在の明るさと色温度は、画面に出さない（ダイアログが閉じているとき）", async () => {
    mockApi(defaultHandler(CEILING_ON));
    const wrapper = await mountView();
    expect(wrapper.text()).not.toMatch(/明るさ|色温度/);
  });

  it("選んだパターン名は、切替後の図に残さない", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    await openDialog(wrapper);
    await option(wrapper, "reading").trigger("click");
    await flushPromises();
    expect(part(wrapper, "ceiling_light").text()).not.toContain("読書");
  });
});

// ---- 一括切替「電灯選択」 ----

const sceneButton = (w: VueWrapper, key: string) => w.get(`[data-scene="${key}"]`);
const posts = (calls: Call[]) => calls.filter((c) => c.method === "POST");

type SceneResult = { device: string; target: "on" | "off"; outcome: "success" | "failure" }[];

/** GET は既定、POST /scenes/ceiling_light は与えた応答を返す。 */
function withCeilingScene(
  outcome: "success" | "partial" | "failure",
  results: SceneResult,
  after: Devices,
  initial: Devices = devices(),
): Handler {
  const base = defaultHandler(initial);
  return (call) =>
    call.method === "POST" && call.path === "/scenes/ceiling_light"
      ? res({ scene: "ceiling_light", outcome, results, fetched_at: SWITCH_AT, devices: after })
      : base(call);
}

const AFTER_ON = devices({
  ceiling_light: { status: "ok", state: "on" },
  indirect_light: { status: "ok", state: "off" },
});
const BOTH_OK: SceneResult = [
  { device: "ceiling_light", target: "on", outcome: "success" },
  { device: "indirect_light", target: "off", outcome: "success" },
];

describe("一括切替「電灯選択」", () => {
  it("押すと、調光パターンダイアログを開く。POST はしない", async () => {
    const { calls } = mockApi(withCeilingScene("success", BOTH_OK, AFTER_ON));
    const wrapper = await mountView();

    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();

    expect(dialog(wrapper).exists()).toBe(true);
    expect(wrapper.findAll(".dimming-option").map((o) => o.get(".dimming-name").text())).toEqual([
      "全灯",
      "読書",
      "くつろぎ",
      "夜",
    ]);
    expect(posts(calls)).toHaveLength(0);
  });

  it("電灯が点灯中でも「消灯」は出さない（電灯のパーツから開いたときだけ）", async () => {
    mockApi(withCeilingScene("success", BOTH_OK, AFTER_ON, CEILING_ON));
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    expect(offButton(wrapper).exists()).toBe(false);
  });

  it.each(PATTERNS_RESPONSE.patterns)("「$name」を選ぶと、そのパターンで電灯選択を実行する", async ({ id, name }) => {
    const { calls } = mockApi(withCeilingScene("success", BOTH_OK, AFTER_ON));
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();

    await option(wrapper, id).trigger("click");
    await flushPromises();

    expect(posts(calls)).toEqual([
      { method: "POST", path: "/scenes/ceiling_light", body: { pattern: id } },
    ]);
    expect(dialog(wrapper).exists()).toBe(false);
    expect(part(wrapper, "ceiling_light").text()).toContain("ON");
    expect(part(wrapper, "indirect_light").text()).toContain("OFF");
    expect(status(wrapper).text()).toBe(`電灯選択（${name}）を実行しました。`);
    expect(status(wrapper).classes()).not.toContain("is-error");
  });

  it("キャンセルすると、何も実行せずに閉じる", async () => {
    const { calls } = mockApi(withCeilingScene("success", BOTH_OK, AFTER_ON));
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();

    await cancelButton(wrapper).trigger("click");
    await flushPromises();

    expect(dialog(wrapper).exists()).toBe(false);
    expect(posts(calls)).toHaveLength(0);
  });

  it("実行中は、ダイアログを開いたまま、選択肢を無効にし、終わると閉じる", async () => {
    const pending = deferred<Partial<Response>>();
    const base = withCeilingScene("success", BOTH_OK, AFTER_ON);
    mockApi((call) => (call.method === "POST" ? pending.promise : base(call)));
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();

    await option(wrapper, "reading").trigger("click");
    await flushPromises();
    expect(dialog(wrapper).exists()).toBe(true);
    for (const o of wrapper.findAll(".dimming-option")) {
      expect(o.attributes("disabled")).toBeDefined();
    }

    pending.resolve(
      res({ scene: "ceiling_light", outcome: "success", results: BOTH_OK, fetched_at: SWITCH_AT, devices: AFTER_ON }),
    );
    await flushPromises();
    expect(dialog(wrapper).exists()).toBe(false);
  });

  it("電灯が失敗し、間接照明が成功したら、一部失敗として機器の名称を示す", async () => {
    mockApi(
      withCeilingScene(
        "partial",
        [
          { device: "ceiling_light", target: "on", outcome: "failure" },
          { device: "indirect_light", target: "off", outcome: "success" },
        ],
        devices({ indirect_light: { status: "ok", state: "off" } }),
      ),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    await option(wrapper, "night").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("一部の機器の切り替えに失敗しました。成功: 間接照明／失敗: 電灯");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(part(wrapper, "ceiling_light").text()).toContain("OFF");
    expect(dialog(wrapper).exists()).toBe(false);
  });

  it("実行が HTTP エラーなら、ダイアログを閉じ、一文だけを示す", async () => {
    const base = defaultHandler();
    mockApi((call) => (call.method === "POST" ? res({ detail: "内部の理由" }, 500) : base(call)));
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    await option(wrapper, "full").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(dialog(wrapper).exists()).toBe(false);
  });

  it("パターンを取得できなければ、ダイアログを開かず、ステータスに一文を示す", async () => {
    mockApi((call) =>
      call.path === "/dimming-patterns" ? res({ detail: "x" }, 500) : defaultHandler()(call),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    expect(dialog(wrapper).exists()).toBe(false);
    expect(status(wrapper).text()).toBe("調光パターンを取得できませんでした。");
  });

  it("電灯選択以外の一括切替は、ダイアログを開かない", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    for (const scene of ["indoor_speaker", "bedside_speaker", "indirect_light", "out"]) {
      await sceneButton(wrapper, scene).trigger("click");
      await flushPromises();
      expect(dialog(wrapper).exists()).toBe(false);
    }
    expect(calls.filter((c) => c.path === "/dimming-patterns")).toHaveLength(0);
  });

  it("電灯のパーツと電灯選択は、同じダイアログを共有し、取得は 1 回だけ", async () => {
    const { calls } = mockApi(withCeilingScene("success", BOTH_OK, AFTER_ON));
    const wrapper = await mountView();
    await openDialog(wrapper);
    await cancelButton(wrapper).trigger("click");
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    expect(dialog(wrapper).exists()).toBe(true);
    expect(calls.filter((c) => c.path === "/dimming-patterns")).toHaveLength(1);
  });

  it("状態を取得できていない間は、電灯選択を押してもダイアログを開かない", async () => {
    mockApi(() => res({ detail: "x" }, 500));
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    expect(dialog(wrapper).exists()).toBe(false);
  });
});

it("ダイアログを持つ ROOM ページは、マウントしても余計な API を呼ばない（パターンは開くときに取得する）", async () => {
  const { calls } = mockApi(defaultHandler());
  const wrapper = mount(RoomView);
  await flushPromises();
  expect(calls.map((c) => c.path)).toEqual(["/state"]);
  wrapper.unmount();
});
