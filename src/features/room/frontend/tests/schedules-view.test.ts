import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import {
  actionText,
  conditionText,
  formatLastRunAt,
  sortSchedules,
  type ScheduleItem,
} from "../src/room";
import SchedulesView from "../src/views/SchedulesView.vue";
import { deferred, mockApi, res, type Handler } from "./helpers";

function item(override: Partial<ScheduleItem> = {}): ScheduleItem {
  return {
    id: 1,
    condition: "daily",
    weekdays: [],
    holiday_mode: "none",
    day_shift: "same",
    run_time: "07:00",
    scene: "indoor_speaker",
    device: null,
    state: null,
    is_enabled: true,
    last_run: null,
    ...override,
  };
}

/** GET /schedules は与えた一覧、PUT .../enabled と DELETE は既定で成功させる。 */
function scheduleHandler(initial: ScheduleItem[]): Handler {
  let current = [...initial];
  return ({ method, path, body }) => {
    if (method === "GET" && path === "/schedules") {
      return res({ schedules: current });
    }
    const enabled = path.match(/^\/schedules\/(\d+)\/enabled$/);
    if (method === "PUT" && enabled) {
      const id = Number(enabled[1]);
      current = current.map((s) =>
        s.id === id ? { ...s, is_enabled: (body as { is_enabled: boolean }).is_enabled } : s,
      );
      return res(current.find((s) => s.id === id));
    }
    const del = path.match(/^\/schedules\/(\d+)$/);
    if (method === "DELETE" && del) {
      current = current.filter((s) => s.id !== Number(del[1]));
      return res(null, 204);
    }
    return res({}, 404);
  };
}

async function mountSchedules(): Promise<VueWrapper> {
  const wrapper = mount(SchedulesView);
  await flushPromises();
  return wrapper;
}

const rows = (w: VueWrapper) => w.findAll(".sch-body .sch-row");
const row = (w: VueWrapper, id: number) => w.get(`[data-schedule-id="${id}"]`);
const status = (w: VueWrapper) => w.get(".status-line");
const createButton = (w: VueWrapper) => w.get('.schedules-top [aria-label="新規"]');

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("表示", () => {
  it("GET /schedules を呼び、一覧を表示する", async () => {
    const { calls } = mockApi(
      scheduleHandler([
        item({ id: 1, condition: "daily", run_time: "07:00", scene: "indoor_speaker" }),
        item({ id: 2, condition: "weekdays", weekdays: [5, 1, 3], run_time: "22:30", scene: "out" }),
        item({
          id: 3,
          condition: "weekdays",
          weekdays: [1, 2, 3, 4, 5],
          holiday_mode: "exclude",
          day_shift: "before",
          run_time: "09:15",
          scene: null,
          device: "indirect_light",
          state: "off",
        }),
      ]),
    );
    const wrapper = await mountSchedules();

    expect(calls).toEqual([{ method: "GET", path: "/schedules", body: undefined }]);
    expect(rows(wrapper)).toHaveLength(3);
    expect(wrapper.get(".schedules-title").text()).toBe("定期実行");

    const first = row(wrapper, 1);
    expect(first.get(".sch-condition").text()).toBe("毎日");
    expect(first.get(".sch-time").text()).toBe("07:00");
    expect(first.get(".sch-scene").text()).toBe("屋内スピーカー選択");
    expect(row(wrapper, 2).get(".sch-condition").text()).toBe("月・水・金");
    expect(row(wrapper, 2).get(".sch-scene").text()).toBe("お出かけ");
    expect(row(wrapper, 3).get(".sch-condition").text()).toBe("月・火・水・木・金（祝日を除く）の前の日");
    expect(row(wrapper, 3).get(".sch-scene").text()).toBe("間接照明を OFF");
  });

  it("時刻の昇順に並べる", async () => {
    mockApi(
      scheduleHandler([
        item({ id: 1, run_time: "23:10" }),
        item({ id: 2, run_time: "06:05" }),
        item({ id: 3, run_time: "12:00" }),
      ]),
    );
    const wrapper = await mountSchedules();
    expect(rows(wrapper).map((r) => r.get(".sch-time").text())).toEqual(["06:05", "12:00", "23:10"]);
  });

  it("同じ時刻なら実行内容の名称順に並べる", () => {
    const list = [
      item({ id: 1, scene: "out" }),
      item({ id: 2, scene: "indirect_light" }),
      item({ id: 3, scene: "bedside_speaker" }),
      item({ id: 4, scene: "ceiling_light" }),
      item({ id: 5, scene: "indoor_speaker" }),
    ];
    const expected = [...list]
      .map((s) => actionText(s))
      .sort((a, b) => a.localeCompare(b, "ja"));
    expect(sortSchedules(list).map((s) => actionText(s))).toEqual(expected);
  });

  it("同じ時刻・同じ一括切替なら登録の順（id）に並べる", () => {
    const list = [item({ id: 9 }), item({ id: 2 }), item({ id: 5 })];
    expect(sortSchedules(list).map((s) => s.id)).toEqual([2, 5, 9]);
  });

  it("並べ替えで元の配列を変えない", () => {
    const list = [item({ id: 1, run_time: "23:00" }), item({ id: 2, run_time: "01:00" })];
    sortSchedules(list);
    expect(list.map((s) => s.id)).toEqual([1, 2]);
  });

  it("列の見出しがあり、一覧に名前がある", async () => {
    mockApi(scheduleHandler([item()]));
    const wrapper = await mountSchedules();
    expect(wrapper.get('[role="table"]').attributes("aria-label")).toBe("定期実行の一覧");
    expect(wrapper.findAll('[role="columnheader"]').map((h) => h.text())).toEqual([
      "有効",
      "実行条件",
      "時刻",
      "実行内容",
      "最終実行",
      "操作",
    ]);
  });
});

describe("個別切替の一覧と最終実行", () => {
  it("個別切替の実行内容と、成功・失敗が示される", async () => {
    mockApi(
      scheduleHandler([
        item({
          id: 1,
          scene: null,
          device: "indoor_speaker",
          state: "off",
          last_run: { at: "2026-10-01T07:00:02+09:00", result: "success", failed_devices: [] },
        }),
        item({
          id: 2,
          scene: null,
          device: "bedside_speaker",
          state: "on",
          last_run: {
            at: "2026-10-01T07:00:03+09:00",
            result: "failure",
            failed_devices: ["bedside_speaker"],
          },
        }),
      ]),
    );
    const wrapper = await mountSchedules();
    expect(row(wrapper, 1).get(".sch-scene").text()).toBe("屋内スピーカーを OFF");
    expect(row(wrapper, 1).get(".sch-result").text()).toBe("✓ 成功");
    expect(row(wrapper, 2).get(".sch-scene").text()).toBe("枕元スピーカーを ON");
    expect(row(wrapper, 2).get(".sch-result").text()).toBe("✕ 失敗");
    expect(row(wrapper, 2).get(".sch-failed").text()).toContain("枕元スピーカー");
  });

  it("列の見出しは「実行内容」で、有効／無効のスイッチの名称も実行内容を使う", async () => {
    mockApi(
      scheduleHandler([item({ id: 1, scene: null, device: "indirect_light", state: "on", run_time: "06:30" })]),
    );
    const wrapper = await mountSchedules();
    expect(wrapper.text()).toContain("実行内容");
    expect(wrapper.text()).not.toContain("一括切替");
    expect(row(wrapper, 1).get('[role="switch"]').attributes("aria-label")).toBe(
      "間接照明を ON 06:30 の定期実行",
    );
  });
});

describe("最終実行", () => {
  it("未実行は「未実行」", async () => {
    mockApi(scheduleHandler([item({ last_run: null })]));
    const wrapper = await mountSchedules();
    expect(row(wrapper, 1).get(".sch-last").text()).toBe("未実行");
  });

  it("成功は日時と結果を示し、失敗した機器は出さない", async () => {
    mockApi(
      scheduleHandler([
        item({ last_run: { at: "2026-10-01T07:00:02+09:00", result: "success", failed_devices: [] } }),
      ]),
    );
    const wrapper = await mountSchedules();
    const last = row(wrapper, 1).get(".sch-last");
    expect(last.text()).toContain("2026-10-01 07:00");
    expect(last.get(".sch-result").text()).toBe("✓ 成功");
    expect(last.find(".sch-failed").exists()).toBe(false);
  });

  it("一部失敗は、記号と文言と、失敗した機器の名称を示す", async () => {
    mockApi(
      scheduleHandler([
        item({
          last_run: {
            at: "2026-10-01T07:00:02+09:00",
            result: "partial",
            failed_devices: ["bedside_speaker", "indirect_light"],
          },
        }),
      ]),
    );
    const wrapper = await mountSchedules();
    const last = row(wrapper, 1).get(".sch-last");
    expect(last.get(".sch-result").text()).toBe("△ 一部失敗");
    expect(last.get(".sch-result").attributes("data-result")).toBe("partial");
    expect(last.get(".sch-failed").text()).toBe("失敗: 枕元スピーカー、間接照明");
  });

  it("失敗は、✕ と文言で示す（結果ごとに記号が違う）", async () => {
    mockApi(
      scheduleHandler([
        item({
          last_run: {
            at: "2026-10-01T07:00:02+09:00",
            result: "failure",
            failed_devices: ["indoor_speaker"],
          },
        }),
      ]),
    );
    const wrapper = await mountSchedules();
    expect(row(wrapper, 1).get(".sch-result").text()).toBe("✕ 失敗");
    expect(row(wrapper, 1).get(".sch-failed").text()).toBe("失敗: 屋内スピーカー");
  });
});

describe("文言の補助関数", () => {
  it("実行条件の表示", () => {
    expect(conditionText({ condition: "daily", weekdays: [] })).toBe("毎日");
    expect(conditionText({ condition: "weekdays", weekdays: [7, 1] })).toBe("月・日");
    expect(conditionText({ condition: "weekdays", weekdays: [6, 2, 4] })).toBe("火・木・土");
    expect(conditionText({ condition: "weekdays", weekdays: [1, 2, 3, 4, 5, 6, 7] })).toBe(
      "月・火・水・木・金・土・日",
    );
  });

  it.each([
    ["none", "same", "月・水"],
    ["include", "same", "月・水・祝日"],
    ["exclude", "same", "月・水（祝日を除く）"],
    ["none", "before", "月・水の前の日"],
    ["none", "after", "月・水の次の日"],
    ["include", "before", "月・水・祝日の前の日"],
    ["include", "after", "月・水・祝日の次の日"],
    ["exclude", "before", "月・水（祝日を除く）の前の日"],
    ["exclude", "after", "月・水（祝日を除く）の次の日"],
  ] as const)("曜日の指定の表示: 祝日の扱い %s、実行日の取り方 %s", (mode, shift, expected) => {
    expect(
      conditionText({ condition: "weekdays", weekdays: [3, 1], holiday_mode: mode, day_shift: shift }),
    ).toBe(expected);
  });

  it("毎日は、祝日の扱いと実行日の取り方に関わらず「毎日」", () => {
    expect(
      conditionText({ condition: "daily", weekdays: [], holiday_mode: "none", day_shift: "same" }),
    ).toBe("毎日");
  });

  it("実行内容の表示: 一括切替は名称、個別切替は機器と状態（電灯は未実装を添える）", () => {
    expect(actionText({ scene: "out", device: null, state: null })).toBe("お出かけ");
    expect(actionText({ scene: "ceiling_light", device: null, state: null })).toBe("電灯選択");
    expect(actionText({ scene: null, device: "indirect_light", state: "on" })).toBe("間接照明を ON");
    expect(actionText({ scene: null, device: "indoor_speaker", state: "off" })).toBe("屋内スピーカーを OFF");
    expect(actionText({ scene: null, device: "bedside_speaker", state: "on" })).toBe("枕元スピーカーを ON");
    expect(actionText({ scene: null, device: "ceiling_light", state: "on" })).toBe("電灯を ON（未実装）");
    expect(actionText({ scene: null, device: "ceiling_light", state: "off" })).toBe("電灯を OFF（未実装）");
  });

  it("最終実行の日時は年月日 時分", () => {
    expect(formatLastRunAt("2026-10-01T07:00:02+09:00")).toBe("2026-10-01 07:00");
  });
});

describe("読込中・空・エラー", () => {
  it("読込中は「読み込み中…」を示し、新規は押せない", async () => {
    const pending = deferred<Partial<Response>>();
    mockApi(() => pending.promise);
    const wrapper = mount(SchedulesView);
    await flushPromises();
    expect(wrapper.text()).toContain("読み込み中…");
    expect(createButton(wrapper).attributes("disabled")).toBeDefined();
    expect(wrapper.find('[role="table"]').exists()).toBe(false);

    pending.resolve(res({ schedules: [item()] }));
    await flushPromises();
    expect(wrapper.text()).not.toContain("読み込み中…");
    expect(createButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("空は「データがありません」を示し、新規は押せる", async () => {
    mockApi(scheduleHandler([]));
    const wrapper = await mountSchedules();
    expect(wrapper.text()).toContain("データがありません");
    expect(createButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("取得に失敗したら、先頭に一文を示し、新規は押せる（内部理由は出さない）", async () => {
    mockApi(() => res({ detail: "内部の理由" }, 500));
    const wrapper = await mountSchedules();
    expect(wrapper.get("[role=alert]").text()).toBe("定期実行を取得できませんでした。");
    expect(wrapper.text()).not.toContain("内部の理由");
    expect(createButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("通信できないときも同じ表示にする", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const wrapper = await mountSchedules();
    expect(wrapper.get("[role=alert]").text()).toBe("定期実行を取得できませんでした。");
    expect(wrapper.text()).not.toContain("Failed to fetch");
  });

  it.each([401, 403] as const)("%s は親（殻）へ auth-error を伝え、内容は見せない", async (code) => {
    mockApi(() => res({ detail: "x" }, code));
    const wrapper = await mountSchedules();
    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect(emitted![0]![0]).toBeInstanceOf(AuthError);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
    expect(wrapper.find('[role="table"]').exists()).toBe(false);
  });
});

describe("有効／無効の切替", () => {
  it("スイッチは状態を aria-checked と文言（有効／無効）で示す", async () => {
    mockApi(scheduleHandler([item({ id: 1, is_enabled: true }), item({ id: 2, is_enabled: false })]));
    const wrapper = await mountSchedules();
    const on = row(wrapper, 1).get('[role="switch"]');
    const off = row(wrapper, 2).get('[role="switch"]');
    expect(on.attributes("aria-checked")).toBe("true");
    expect(on.text()).toBe("有効");
    expect(off.attributes("aria-checked")).toBe("false");
    expect(off.text()).toBe("無効");
    expect(row(wrapper, 2).classes()).toContain("is-disabled");
    expect(row(wrapper, 1).classes()).not.toContain("is-disabled");
  });

  it("スイッチの aria-label は、どの定期実行かが分かる", async () => {
    mockApi(scheduleHandler([item({ id: 1, run_time: "07:00", scene: "out" })]));
    const wrapper = await mountSchedules();
    expect(row(wrapper, 1).get('[role="switch"]').attributes("aria-label")).toBe(
      "お出かけ 07:00 の定期実行",
    );
  });

  it("押すと、反対の値を PUT し、その場で切り替わる。他の行は変わらない", async () => {
    const { calls } = mockApi(
      scheduleHandler([item({ id: 1, is_enabled: true }), item({ id: 2, run_time: "08:00", is_enabled: true })]),
    );
    const wrapper = await mountSchedules();

    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();

    expect(calls.at(-1)).toEqual({
      method: "PUT",
      path: "/schedules/1/enabled",
      body: { is_enabled: false },
    });
    expect(row(wrapper, 1).get('[role="switch"]').attributes("aria-checked")).toBe("false");
    expect(row(wrapper, 1).get('[role="switch"]').text()).toBe("無効");
    expect(row(wrapper, 1).classes()).toContain("is-disabled");
    expect(row(wrapper, 2).get('[role="switch"]').attributes("aria-checked")).toBe("true");

    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();
    expect(calls.at(-1)?.body).toEqual({ is_enabled: true });
    expect(row(wrapper, 1).get('[role="switch"]').text()).toBe("有効");
  });

  it("切替中は、その行の操作（スイッチ・編集・削除）を重ねて押せない", async () => {
    const pending = deferred<Partial<Response>>();
    const base = scheduleHandler([item({ id: 1 }), item({ id: 2, run_time: "08:00" })]);
    const { calls } = mockApi((call) =>
      call.method === "PUT" ? pending.promise : base(call),
    );
    const wrapper = await mountSchedules();

    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();
    expect(row(wrapper, 1).get('[role="switch"]').attributes("disabled")).toBeDefined();
    expect(row(wrapper, 1).get('[aria-label="編集"]').attributes("disabled")).toBeDefined();
    expect(row(wrapper, 1).get('[aria-label="削除"]').attributes("disabled")).toBeDefined();
    // 他の行は操作できる
    expect(row(wrapper, 2).get('[role="switch"]').attributes("disabled")).toBeUndefined();

    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1);

    pending.resolve(res(item({ id: 1, is_enabled: false })));
    await flushPromises();
    expect(row(wrapper, 1).get('[role="switch"]').attributes("disabled")).toBeUndefined();
  });

  it.each([404, 500])("失敗（%s）は一文を示し、状態は元のまま。失敗は残る", async (code) => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const base = scheduleHandler([item({ id: 1, is_enabled: true })]);
    mockApi((call) => (call.method === "PUT" ? res({ detail: "内部の理由" }, code) : base(call)));
    const wrapper = await mountSchedules();

    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(wrapper.text()).not.toContain("内部の理由");
    expect(row(wrapper, 1).get('[role="switch"]').attributes("aria-checked")).toBe("true");
    vi.advanceTimersByTime(60000);
    await flushPromises();
    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(row(wrapper, 1).get('[role="switch"]').attributes("disabled")).toBeUndefined();
  });

  it("通信できないときも「操作に失敗しました。」", async () => {
    const base = scheduleHandler([item()]);
    mockApi((call) => {
      if (call.method === "PUT") {
        throw new TypeError("Failed to fetch");
      }
      return base(call);
    });
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toBe("操作に失敗しました。");
  });

  it.each([401, 403] as const)("切替で %s なら親（殻）へ auth-error を伝える", async (code) => {
    const base = scheduleHandler([item()]);
    mockApi((call) => (call.method === "PUT" ? res({ detail: "x" }, code) : base(call)));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();
    expect((wrapper.emitted("auth-error")![0]![0] as AuthError).status).toBe(code);
    expect(status(wrapper).text()).toBe("");
  });
});

describe("削除", () => {
  it("削除を押すと確認を出す。承認するまで DELETE しない", async () => {
    const { calls } = mockApi(scheduleHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();

    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");

    const dialog = wrapper.get("[role=dialog]");
    expect(dialog.attributes("aria-modal")).toBe("true");
    expect(dialog.text()).toContain("この定期実行を削除します。よろしいですか?");
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(0);
  });

  it("確定すると DELETE して、一覧から消す", async () => {
    const { calls } = mockApi(scheduleHandler([item({ id: 1 }), item({ id: 2, run_time: "08:00" })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");

    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();

    expect(calls.at(-1)).toEqual({ method: "DELETE", path: "/schedules/1", body: undefined });
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(rows(wrapper)).toHaveLength(1);
    expect(wrapper.find('[data-schedule-id="1"]').exists()).toBe(false);
    expect(status(wrapper).text()).toBe("削除しました。");
    expect(status(wrapper).classes()).not.toContain("is-error");
  });

  it("最後の 1 件を削除すると「データがありません」になる", async () => {
    mockApi(scheduleHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("データがありません");
    expect(createButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("キャンセルすると、何も削除せずに閉じる", async () => {
    const { calls } = mockApi(scheduleHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");

    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    await flushPromises();

    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(0);
    expect(rows(wrapper)).toHaveLength(1);
  });

  it("背景を押しても閉じない。Esc ではキャンセルと同じく閉じる", async () => {
    const { calls } = mockApi(scheduleHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");

    await wrapper.get(".dialog-overlay").trigger("click");
    expect(wrapper.find("[role=dialog]").exists()).toBe(true);

    await wrapper.get("[role=dialog]").trigger("keydown", { key: "Escape" });
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(0);
  });

  it("削除に失敗したら一文を示し、行は残る", async () => {
    const base = scheduleHandler([item({ id: 1 })]);
    mockApi((call) => (call.method === "DELETE" ? res({ detail: "x" }, 404) : base(call)));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();

    expect(status(wrapper).text()).toBe("操作に失敗しました。");
    expect(status(wrapper).classes()).toContain("is-error");
    expect(rows(wrapper)).toHaveLength(1);
  });

  it("成功の一文は数秒で消える", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    mockApi(scheduleHandler([item({ id: 1 }), item({ id: 2, run_time: "08:00" })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(status(wrapper).text()).toBe("削除しました。");

    vi.advanceTimersByTime(4000);
    await flushPromises();
    expect(status(wrapper).text()).toBe("");
  });

  it.each([401, 403] as const)("削除で %s なら親（殻）へ auth-error を伝える", async (code) => {
    const base = scheduleHandler([item({ id: 1 })]);
    mockApi((call) => (call.method === "DELETE" ? res({ detail: "x" }, code) : base(call)));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="削除"]').trigger("click");
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect((wrapper.emitted("auth-error")![0]![0] as AuthError).status).toBe(code);
    expect(rows(wrapper)).toHaveLength(1);
  });
});

describe("ボタン", () => {
  it("新規・編集・削除はアイコンのみで、aria-label を持つ", async () => {
    mockApi(scheduleHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    for (const button of [
      createButton(wrapper),
      row(wrapper, 1).get('[aria-label="編集"]'),
      row(wrapper, 1).get('[aria-label="削除"]'),
    ]) {
      expect(button.text()).toBe("");
      expect(button.find("svg").exists()).toBe(true);
      expect(button.attributes("title")).toBe(button.attributes("aria-label"));
    }
  });

  it("操作の列の右端が削除（編集 → 削除の順）", async () => {
    mockApi(scheduleHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    const labels = row(wrapper, 1)
      .findAll(".sch-actions button")
      .map((b) => b.attributes("aria-label"));
    expect(labels).toEqual(["編集", "削除"]);
  });
});
