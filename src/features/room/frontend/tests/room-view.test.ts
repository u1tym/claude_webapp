import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import RoomView from "../src/views/RoomView.vue";
import {
  ERROR,
  SWITCH_AT,
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
} from "./helpers";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("画面を開いたとき", () => {
  it("状態を取得し、図と取得日時を表示する", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();

    expect(calls).toEqual([{ method: "GET", path: "/state", body: undefined }]);
    expect(fetchedAt(wrapper)).toBe("2026-10-01 10:15:30");
    expect(part(wrapper, "indirect_light").text()).toContain("ON");
    expect(part(wrapper, "front_door").text()).toContain("施錠中");
    expect(wrapper.findAll("[data-device]")).toHaveLength(5);
  });

  it("取得が終わるまで「読み込み中…」を示し、更新は押せない", async () => {
    const pending = deferred<Partial<Response>>();
    mockApi(() => pending.promise);
    const wrapper = mount(RoomView);
    await flushPromises();

    expect(wrapper.text()).toContain("読み込み中…");
    expect(wrapper.find("[data-device]").exists()).toBe(false);
    expect(refreshButton(wrapper).attributes("disabled")).toBeDefined();

    pending.resolve(res({ fetched_at: STATE_AT, devices: devices() }));
    await flushPromises();
    expect(wrapper.text()).not.toContain("読み込み中…");
    expect(refreshButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("全機器の取得に失敗したら、先頭にエラーを示し、図は機器ごとの失敗を示す", async () => {
    mockApi(() =>
      res({
        fetched_at: STATE_AT,
        devices: devices({
          ceiling_light: ERROR,
          indirect_light: ERROR,
          indoor_speaker: ERROR,
          bedside_speaker: ERROR,
          front_door: { ...ERROR, battery: null },
        }),
      }),
    );
    const wrapper = await mountView();

    expect(wrapper.get("[role=alert]").text()).toBe("状態を取得できませんでした。");
    expect(part(wrapper, "indirect_light").text()).toContain("取得できません");
    // 操作できるのは更新だけ
    expect(refreshButton(wrapper).attributes("disabled")).toBeUndefined();
    expect(part(wrapper, "indirect_light").attributes("aria-disabled")).toBe("true");
  });

  it("一部の機器だけ失敗したときは、エラーを出さず、その機器のパーツに示す", async () => {
    mockApi(() => res({ fetched_at: STATE_AT, devices: devices({ indoor_speaker: ERROR }) }));
    const wrapper = await mountView();

    expect(wrapper.find("[role=alert]").exists()).toBe(false);
    expect(part(wrapper, "indoor_speaker").text()).toContain("取得できません");
    expect(part(wrapper, "indirect_light").text()).toContain("ON");
  });

  it("通信に失敗したら「状態を取得できませんでした。」だけを示す", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const wrapper = await mountView();
    expect(wrapper.get("[role=alert]").text()).toBe("状態を取得できませんでした。");
    expect(wrapper.text()).not.toContain("Failed to fetch");
    expect(wrapper.find("[data-device]").exists()).toBe(false);
  });

  it("サーバのエラー（500）でも同じ表示にする", async () => {
    mockApi(() => res({ detail: "サーバエラーです" }, 500));
    const wrapper = await mountView();
    expect(wrapper.get("[role=alert]").text()).toBe("状態を取得できませんでした。");
    expect(wrapper.text()).not.toContain("サーバエラーです");
  });

  it.each([401, 403] as const)("%s は親（殻）へ auth-error を伝える", async (code) => {
    mockApi(() => res({ detail: "x" }, code));
    const wrapper = await mountView();
    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect(emitted![0]![0]).toBeInstanceOf(AuthError);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
    // 内容は見せない
    expect(wrapper.find("[data-device]").exists()).toBe(false);
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
  });
});

describe("更新", () => {
  it("押すと状態と取得日時を取り直す。取得中は重ねて押せない", async () => {
    const first = res({ fetched_at: STATE_AT, devices: devices() });
    const second = deferred<Partial<Response>>();
    let n = 0;
    const { calls } = mockApi(() => (n++ === 0 ? first : second.promise));
    const wrapper = await mountView();

    await refreshButton(wrapper).trigger("click");
    await flushPromises();
    expect(refreshButton(wrapper).attributes("disabled")).toBeDefined();
    await refreshButton(wrapper).trigger("click"); // 無効なので何も起きない
    expect(calls).toHaveLength(2);
    // 取得中も、直前の図は残るが、パーツは操作できない
    expect(part(wrapper, "indirect_light").attributes("aria-disabled")).toBe("true");

    second.resolve(
      res({
        fetched_at: "2026-10-01T11:00:00+09:00",
        devices: devices({ indirect_light: { status: "ok", state: "off" } }),
      }),
    );
    await flushPromises();
    expect(fetchedAt(wrapper)).toBe("2026-10-01 11:00:00");
    expect(part(wrapper, "indirect_light").text()).toContain("OFF");
    expect(refreshButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("更新に失敗してもエラーを示し、更新は再び押せる", async () => {
    let n = 0;
    mockApi(() => (n++ === 0 ? res({ fetched_at: STATE_AT, devices: devices() }) : res({}, 500)));
    const wrapper = await mountView();
    await refreshButton(wrapper).trigger("click");
    await flushPromises();
    expect(wrapper.get("[role=alert]").text()).toBe("状態を取得できませんでした。");
    expect(refreshButton(wrapper).attributes("disabled")).toBeUndefined();
  });
});

describe("個別切替（間接照明・スピーカー）", () => {
  it.each([
    ["indirect_light", "off", "OFF", "間接照明を OFF にしました。"],
    ["indoor_speaker", "on", "ON", "屋内スピーカーを ON にしました。"],
    ["bedside_speaker", "on", "ON", "枕元スピーカーを ON にしました。"],
  ] as const)("%s をクリックすると、目標の状態 %s を PUT し、図とステータスを更新する", async (key, target, text, message) => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();

    await part(wrapper, key).trigger("click");
    await flushPromises();

    expect(calls.at(-1)).toEqual({
      method: "PUT",
      path: `/devices/${key}/state`,
      body: { state: target }, // 「反転」ではなく目標の状態を明示する
    });
    expect(part(wrapper, key).text()).toContain(text);
    expect(status(wrapper).text()).toBe(message);
    expect(status(wrapper).classes()).not.toContain("is-error");
    // 取得日時は、機器から最後に取得した日時になる
    expect(fetchedAt(wrapper)).toBe("2026-10-01 10:16:45");
  });

  it("切替中は「切替中…」を示し、すべてのパーツと更新を操作できない", async () => {
    const pending = deferred<Partial<Response>>();
    const { calls } = mockApi(({ method }) =>
      method === "PUT" ? pending.promise : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();

    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(part(wrapper, "indirect_light").text()).toContain("切替中…");
    expect(refreshButton(wrapper).attributes("disabled")).toBeDefined();
    await part(wrapper, "indoor_speaker").trigger("click"); // 重ねて切り替えない
    await part(wrapper, "front_door").trigger("click");
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1);
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);

    pending.resolve(
      res({
        device: "indirect_light",
        applied: true,
        fetched_at: SWITCH_AT,
        result: { status: "ok", state: "off" },
      }),
    );
    await flushPromises();
    expect(part(wrapper, "indirect_light").text()).not.toContain("切替中…");
  });

  it("他の機器は変えない（切り替えた機器だけが変わる）", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(part(wrapper, "indoor_speaker").text()).toContain("OFF");
    expect(part(wrapper, "bedside_speaker").text()).toContain("OFF");
    expect(part(wrapper, "front_door").text()).toContain("施錠中");
  });

  it("成功のステータスは数秒で消える", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).not.toBe("");

    vi.advanceTimersByTime(4000);
    await flushPromises();
    expect(status(wrapper).text()).toBe("");
  });

  it.each([
    [502, "機器を操作できませんでした。"],
    [500, "操作に失敗しました。"],
    [400, "操作に失敗しました。"],
  ])("切替の失敗（%s）は一文を示し、図は元の状態のまま。失敗は消えず、再び操作できる", async (code, message) => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    mockApi(({ method }) =>
      method === "PUT"
        ? res({ detail: "内部の理由 TESTID" }, code)
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();

    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe(message);
    expect(status(wrapper).classes()).toContain("is-error");
    expect(wrapper.text()).not.toContain("内部の理由");
    expect(part(wrapper, "indirect_light").text()).toContain("ON"); // 元のまま
    expect(fetchedAt(wrapper)).toBe("2026-10-01 10:15:30"); // 取得日時も変わらない
    vi.advanceTimersByTime(60000);
    await flushPromises();
    expect(status(wrapper).text()).toBe(message); // 失敗は次の操作まで残る
    expect(part(wrapper, "indirect_light").attributes("aria-disabled")).toBe("false");
  });

  it("通信できないときも「操作に失敗しました。」で、図は元のまま", async () => {
    mockApi(({ method }) => {
      if (method === "PUT") {
        throw new TypeError("Failed to fetch");
      }
      return res({ fetched_at: STATE_AT, devices: devices() });
    });
    const wrapper = await mountView();
    await part(wrapper, "bedside_speaker").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(part(wrapper, "bedside_speaker").text()).toContain("OFF");
  });

  it("指示は成功したが取得し直しに失敗したときは、更新を促す", async () => {
    mockApi(({ method }) =>
      method === "PUT"
        ? res({ device: "indirect_light", applied: true, fetched_at: SWITCH_AT, result: ERROR })
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toBe("指示は送りましたが、状態を確認できませんでした。更新してください。");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(part(wrapper, "indirect_light").text()).toContain("取得できません");
  });

  it("指示は成功したが状態が目標と違うときは、そのことを示す", async () => {
    mockApi(({ method }) =>
      method === "PUT"
        ? res({
            device: "indirect_light",
            applied: true,
            fetched_at: SWITCH_AT,
            result: { status: "ok", state: "on" }, // OFF にしたいのに ON のまま
          })
        : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toContain("状態が変わっていません");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(part(wrapper, "indirect_light").text()).toContain("ON");
  });

  it("取得できなかった機器は切り替えられない（PUT しない）", async () => {
    const { calls } = mockApi(() =>
      res({ fetched_at: STATE_AT, devices: devices({ indoor_speaker: ERROR }) }),
    );
    const wrapper = await mountView();
    await part(wrapper, "indoor_speaker").trigger("click");
    await flushPromises();
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
  });

  it("電灯を押しただけでは切り替えない（調光パターンを選ぶまで PUT しない）", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "ceiling_light").trigger("click");
    await flushPromises();
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
    expect(wrapper.find("[role=dialog]").exists()).toBe(true);
    expect(part(wrapper, "ceiling_light").text()).not.toContain("未実装");
  });

  it.each([401, 403] as const)("切替で %s なら親（殻）へ auth-error を伝える", async (code) => {
    mockApi(({ method }) =>
      method === "PUT" ? res({ detail: "x" }, code) : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
    expect(status(wrapper).text()).toBe("");
  });
});

describe("玄関ドア（確認ダイアログ）", () => {
  it("施錠中のドアを押すと、開錠の確認を出す。承認するまで PUT しない", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();

    await part(wrapper, "front_door").trigger("click");

    const dialog = wrapper.get("[role=dialog]");
    expect(dialog.attributes("aria-modal")).toBe("true");
    expect(dialog.text()).toContain("玄関ドアを開錠します。よろしいですか?");
    expect(dialog.text()).toContain("開錠すると、玄関のドアが開けられる状態になります。");
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
  });

  it("確定すると、開錠（unlocked）を PUT して切り替える", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "front_door").trigger("click");

    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();

    expect(calls.at(-1)).toEqual({
      method: "PUT",
      path: "/devices/front_door/state",
      body: { state: "unlocked" },
    });
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(part(wrapper, "front_door").text()).toContain("開錠中");
    expect(status(wrapper).text()).toBe("玄関ドアを開錠しました。");
  });

  it("キャンセルすると、状態を変えずに閉じる", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "front_door").trigger("click");

    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    await flushPromises();

    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
    expect(part(wrapper, "front_door").text()).toContain("施錠中");
  });

  it("背景（オーバーレイ）を押しても閉じない", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "front_door").trigger("click");

    await wrapper.get(".dialog-overlay").trigger("click");

    expect(wrapper.find("[role=dialog]").exists()).toBe(true);
  });

  it("Esc では、キャンセルと同じく状態を変えずに閉じる", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await part(wrapper, "front_door").trigger("click");

    await wrapper.get("[role=dialog]").trigger("keydown", { key: "Escape" });

    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
  });

  it("開錠中のドアを押すと、施錠の確認を出し、開錠の注意文は添えない", async () => {
    const { calls } = mockApi(
      defaultHandler(devices({ front_door: { status: "ok", state: "unlocked", battery: 35 } })),
    );
    const wrapper = await mountView();
    await part(wrapper, "front_door").trigger("click");

    const dialog = wrapper.get("[role=dialog]");
    expect(dialog.text()).toContain("玄関ドアを施錠します。よろしいですか?");
    expect(dialog.text()).not.toContain("開けられる状態");

    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(calls.at(-1)?.body).toEqual({ state: "locked" });
    expect(status(wrapper).text()).toBe("玄関ドアを施錠しました。");
  });

  it("確認のボタンはアイコンのみで、aria-label を持つ。最初のフォーカスはキャンセル", async () => {
    mockApi(defaultHandler());
    const wrapper = mount(RoomView, { attachTo: document.body });
    await flushPromises();
    await part(wrapper, "front_door").trigger("click");
    await flushPromises();

    const confirm = wrapper.get('[aria-label="確定"]');
    const cancel = wrapper.get('[aria-label="キャンセル"]');
    expect(confirm.text()).toBe("");
    expect(cancel.text()).toBe("");
    expect(document.activeElement).toBe(cancel.element);
    wrapper.unmount();
  });

  it("切替の失敗では、玄関ドアの状態は元のまま", async () => {
    mockApi(({ method }) =>
      method === "PUT" ? res({ detail: "x" }, 502) : res({ fetched_at: STATE_AT, devices: devices() }),
    );
    const wrapper = await mountView();
    await part(wrapper, "front_door").trigger("click");
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toBe("機器を操作できませんでした。");
    expect(part(wrapper, "front_door").text()).toContain("施錠中");
  });

  it("電池残量は操作しても何も起きない", async () => {
    const { calls } = mockApi(defaultHandler());
    const wrapper = await mountView();
    await wrapper.get('[data-part="battery"]').trigger("click");
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
  });
});

describe("ステータス", () => {
  it("操作前は空だが、1 行分の領域は確保される", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    expect(wrapper.find(".room-status").exists()).toBe(true);
    expect(status(wrapper).text()).toBe("");
  });

  it("失敗は role=alert、成功は role=status で読み上げられる", async () => {
    mockApi(defaultHandler());
    const wrapper = await mountView();
    expect(status(wrapper).attributes("role")).toBe("status");
    await part(wrapper, "indirect_light").trigger("click");
    await flushPromises();
    expect(status(wrapper).attributes("role")).toBe("status");
  });
});
