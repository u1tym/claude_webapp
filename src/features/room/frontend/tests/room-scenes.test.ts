import { flushPromises, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import type { DeviceKey, Devices, SceneKey } from "../src/room";
import {
  ERROR,
  STATE_AT,
  defaultHandler,
  deferred,
  devices,
  fetchedAt,
  mockApi,
  mountView,
  part,
  refreshButton,
  res,
  status,
  type Handler,
} from "./helpers";

const SCENE_AT = "2026-10-01T10:20:00+09:00";

const LABELS: Record<SceneKey, string> = {
  indoor_speaker: "屋内スピーカー選択",
  bedside_speaker: "枕元スピーカー選択",
  ceiling_light: "電灯選択",
  indirect_light: "間接照明選択",
  out: "お出かけ",
};

const sceneButton = (w: VueWrapper, key: SceneKey) => w.get(`[data-scene="${key}"]`);
const allSceneButtons = (w: VueWrapper) => w.findAll("[data-scene]");

type SceneBody = {
  scene: SceneKey;
  outcome: "success" | "partial" | "failure";
  results: { device: DeviceKey; target: "on" | "off"; outcome: "success" | "failure" | "skipped" }[];
  devices: Devices;
};

/** GET /state は既定、POST /scenes/{scene} は与えた応答を返す。 */
function withScene(body: SceneBody | ((scene: SceneKey) => SceneBody), initial = devices()): Handler {
  const base = defaultHandler(initial);
  return (call) => {
    const match = call.path.match(/^\/scenes\/(\w+)$/);
    if (call.method === "POST" && match) {
      const scene = match[1] as SceneKey;
      const payload = typeof body === "function" ? body(scene) : body;
      return res({ ...payload, fetched_at: SCENE_AT });
    }
    return base(call);
  };
}

const allOff = devices({
  indirect_light: { status: "ok", state: "off" },
  indoor_speaker: { status: "ok", state: "off" },
  bedside_speaker: { status: "ok", state: "off" },
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("一括切替ボタン", () => {
  it("5 つのボタンを、文字ラベルつきで、定義の順に表示する", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    const buttons = allSceneButtons(wrapper);
    expect(buttons.map((b) => b.text())).toEqual([
      "屋内スピーカー選択",
      "枕元スピーカー選択",
      "電灯選択",
      "間接照明選択",
      "お出かけ",
    ]);
    expect(buttons.map((b) => b.attributes("data-scene"))).toEqual([
      "indoor_speaker",
      "bedside_speaker",
      "ceiling_light",
      "indirect_light",
      "out",
    ]);
    expect(wrapper.get(".room-scenes").text()).toContain("一括切替");
    expect(buttons.every((b) => b.attributes("disabled") === undefined)).toBe(true);
  });

  it("「お出かけ」は専用のクラスを持つ（スマートフォンで幅いっぱいにする）", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    expect(sceneButton(wrapper, "out").classes()).toContain("is-out");
    expect(sceneButton(wrapper, "indoor_speaker").classes()).not.toContain("is-out");
  });

  it("PC とスマートフォンで同じボタンを 1 組だけ描画する（配置は CSS で切り替える）", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    expect(allSceneButtons(wrapper)).toHaveLength(5);
  });
});

describe("実行", () => {
  it.each(Object.keys(LABELS) as SceneKey[])(
    "%s を押すと POST /scenes/%s を呼び、確認は挟まない",
    async (scene) => {
      const { calls } = mockApi(
        withScene({ scene, outcome: "success", results: [], devices: allOff }),
      );
      const wrapper = await mountView();

      await sceneButton(wrapper, scene).trigger("click");
      await flushPromises();

      expect(calls.at(-1)).toEqual({ method: "POST", path: `/scenes/${scene}`, body: undefined });
      expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    },
  );

  it("成功したら、応答の状態で図と取得日時を更新し、成功の一文を示す", async () => {
    const after = devices({
      indoor_speaker: { status: "ok", state: "on" },
      bedside_speaker: { status: "ok", state: "off" },
    });
    mockApi(
      withScene({
        scene: "indoor_speaker",
        outcome: "success",
        results: [
          { device: "indoor_speaker", target: "on", outcome: "success" },
          { device: "bedside_speaker", target: "off", outcome: "success" },
        ],
        devices: after,
      }),
    );
    const wrapper = await mountView();

    await sceneButton(wrapper, "indoor_speaker").trigger("click");
    await flushPromises();

    expect(part(wrapper, "indoor_speaker").text()).toContain("ON");
    expect(part(wrapper, "bedside_speaker").text()).toContain("OFF");
    expect(fetchedAt(wrapper)).toBe("2026-10-01 10:20:00");
    expect(status(wrapper).text()).toBe("屋内スピーカー選択を実行しました。");
    expect(status(wrapper).classes()).not.toContain("is-error");
  });

  it("お出かけは、4 機器を OFF にした状態を示し、玄関ドアは変わらない", async () => {
    mockApi(
      withScene({
        scene: "out",
        outcome: "success",
        results: [
          { device: "ceiling_light", target: "off", outcome: "skipped" },
          { device: "indirect_light", target: "off", outcome: "success" },
          { device: "indoor_speaker", target: "off", outcome: "success" },
          { device: "bedside_speaker", target: "off", outcome: "success" },
        ],
        devices: allOff,
      }, devices({ bedside_speaker: { status: "ok", state: "on" } })),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();

    for (const key of ["indirect_light", "indoor_speaker", "bedside_speaker"] as const) {
      expect(part(wrapper, key).text()).toContain("OFF");
    }
    expect(part(wrapper, "front_door").text()).toContain("施錠中");
    expect(status(wrapper).text()).toBe("お出かけを実行しました。");
  });

  it("電灯選択は、電灯が未実装のため変更していないことを添える", async () => {
    mockApi(
      withScene({
        scene: "ceiling_light",
        outcome: "success",
        results: [
          { device: "ceiling_light", target: "on", outcome: "skipped" },
          { device: "indirect_light", target: "off", outcome: "success" },
        ],
        devices: allOff,
      }),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "ceiling_light").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("電灯選択を実行しました。（電灯は未実装のため変更していません）");
    expect(part(wrapper, "ceiling_light").text()).toContain("OFF");
    expect(part(wrapper, "indirect_light").text()).toContain("OFF");
  });

  it("成功の一文は数秒で消える", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    mockApi(withScene({ scene: "out", outcome: "success", results: [], devices: allOff }));
    const wrapper = await mountView();
    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).not.toBe("");

    vi.advanceTimersByTime(4000);
    await flushPromises();
    expect(status(wrapper).text()).toBe("");
  });
});

describe("実行中", () => {
  it("すべてのボタン・パーツ・更新を操作できず、「実行中…」を示す。重ねて実行しない", async () => {
    const pending = deferred<Partial<Response>>();
    const { calls } = mockApi(({ method, path }) =>
      method === "POST" && path.startsWith("/scenes/")
        ? pending.promise
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();

    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("実行中…");
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") !== undefined)).toBe(true);
    expect(sceneButton(wrapper, "out").attributes("aria-busy")).toBe("true");
    expect(refreshButton(wrapper).attributes("disabled")).toBeDefined();
    expect(part(wrapper, "indirect_light").attributes("aria-disabled")).toBe("true");

    await sceneButton(wrapper, "indoor_speaker").trigger("click"); // 無効なので何も起きない
    await part(wrapper, "indirect_light").trigger("click");
    await part(wrapper, "front_door").trigger("click");
    expect(calls.filter((c) => c.method !== "GET")).toHaveLength(1);
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);

    pending.resolve(
      res({
        scene: "out",
        outcome: "success",
        results: [],
        fetched_at: SCENE_AT,
        devices: allOff,
      }),
    );
    await flushPromises();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") === undefined)).toBe(true);
    expect(refreshButton(wrapper).attributes("disabled")).toBeUndefined();
    expect(status(wrapper).text()).toBe("お出かけを実行しました。");
  });

  it("個別切替の間も、一括切替は押せない", async () => {
    const pending = deferred<Partial<Response>>();
    mockApi(({ method, path }) =>
      method === "PUT" && path.startsWith("/devices/")
        ? pending.promise
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") !== undefined)).toBe(true);
  });
});

describe("一部失敗・失敗", () => {
  it("一部の機器が失敗したら、成功した機器と失敗した機器の名称を示し、失敗は残る", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const after = devices({
      indoor_speaker: { status: "ok", state: "on" },
      bedside_speaker: { status: "ok", state: "on" }, // 失敗したので ON のまま
    });
    mockApi(
      withScene({
        scene: "indoor_speaker",
        outcome: "partial",
        results: [
          { device: "indoor_speaker", target: "on", outcome: "success" },
          { device: "bedside_speaker", target: "off", outcome: "failure" },
        ],
        devices: after,
      }),
    );
    const wrapper = await mountView();

    await sceneButton(wrapper, "indoor_speaker").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe(
      "一部の機器の切り替えに失敗しました。成功: 屋内スピーカー／失敗: 枕元スピーカー",
    );
    expect(status(wrapper).classes()).toContain("is-error");
    // 成功した機器は元に戻らず、応答の状態が図に反映される
    expect(part(wrapper, "indoor_speaker").text()).toContain("ON");
    expect(part(wrapper, "bedside_speaker").text()).toContain("ON");
    vi.advanceTimersByTime(60000);
    await flushPromises();
    expect(status(wrapper).text()).toContain("失敗: 枕元スピーカー"); // 次の操作まで残る
    // ボタンは再び押せる
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") === undefined)).toBe(true);
  });

  it("すべて失敗したら、失敗した機器の名称を示す（skipped は含めない）", async () => {
    mockApi(
      withScene({
        scene: "out",
        outcome: "failure",
        results: [
          { device: "ceiling_light", target: "off", outcome: "skipped" },
          { device: "indirect_light", target: "off", outcome: "failure" },
          { device: "indoor_speaker", target: "off", outcome: "failure" },
          { device: "bedside_speaker", target: "off", outcome: "failure" },
        ],
        devices: devices(),
      }),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe(
      "切り替えに失敗しました。失敗: 間接照明、屋内スピーカー、枕元スピーカー",
    );
    expect(status(wrapper).text()).not.toContain("電灯");
    expect(status(wrapper).classes()).toContain("is-error");
  });

  it.each([404, 500, 502])("HTTP %s は一文だけを示し、図は元のまま", async (code) => {
    mockApi(({ method, path }) =>
      method === "POST" && path.startsWith("/scenes/")
        ? res({ detail: "内部の理由 TESTID" }, code)
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(wrapper.text()).not.toContain("内部の理由");
    expect(part(wrapper, "indirect_light").text()).toContain("ON");
    expect(fetchedAt(wrapper)).toBe("2026-10-01 10:15:30");
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") === undefined)).toBe(true);
  });

  it("通信できないときも「操作に失敗しました。」", async () => {
    mockApi(({ method }) => {
      if (method === "POST") {
        throw new TypeError("Failed to fetch");
      }
      return res({ fetched_at: STATE_AT, devices: devices() });
    });
    const wrapper = await mountView();
    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(wrapper.text()).not.toContain("Failed to fetch");
  });

  it.each([401, 403] as const)("%s は親（殻）へ auth-error を伝える", async (code) => {
    mockApi(({ method, path }) =>
      method === "POST" && path.startsWith("/scenes/")
        ? res({ detail: "x" }, code)
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await sceneButton(wrapper, "out").trigger("click");
    await flushPromises();
    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect(emitted![0]![0]).toBeInstanceOf(AuthError);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
  });
});

describe("押せない間", () => {
  it("読み込み中は押せない", async () => {
    const pending = deferred<Partial<Response>>();
    mockApi(() => pending.promise);
    const { mount } = await import("@vue/test-utils");
    const RoomView = (await import("../src/views/RoomView.vue")).default;
    const wrapper = mount(RoomView);
    await flushPromises();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") !== undefined)).toBe(true);
  });

  it("全機器の取得に失敗したときは押せない（操作は更新だけ有効）", async () => {
    mockApi(() =>
      res({
        fetched_at: STATE_AT,
        devices: devices({
          indirect_light: ERROR,
          indoor_speaker: ERROR,
          bedside_speaker: ERROR,
          front_door: { ...ERROR, battery: null },
        }),
      }),
    );
    const wrapper = await mountView();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") !== undefined)).toBe(true);
    expect(refreshButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("通信に失敗したときも押せない", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const wrapper = await mountView();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") !== undefined)).toBe(true);
  });

  it("一部の機器だけ取得に失敗したときは押せる", async () => {
    mockApi(() => res({ fetched_at: STATE_AT, devices: devices({ indoor_speaker: ERROR }) }));
    const wrapper = await mountView();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") === undefined)).toBe(true);
  });

  it("取得し直しに失敗したら押せなくなり、成功すれば押せる", async () => {
    let n = 0;
    mockApi(() =>
      n++ === 1 ? res({}, 500) : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await refreshButton(wrapper).trigger("click");
    await flushPromises();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") !== undefined)).toBe(true);

    await refreshButton(wrapper).trigger("click");
    await flushPromises();
    expect(allSceneButtons(wrapper).every((b) => b.attributes("disabled") === undefined)).toBe(true);
  });
});
