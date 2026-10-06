import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import type { ScheduleItem } from "../src/room";
import SchedulesView from "../src/views/SchedulesView.vue";
import { mockApi, res, type Handler } from "./helpers";

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

/** 一覧・登録（採番は 100 から）・変更に成功するサーバの代わり。 */
function serverHandler(initial: ScheduleItem[]): Handler {
  let current = [...initial];
  let nextId = 100;
  return ({ method, path, body }) => {
    const input = body as Omit<ScheduleItem, "id" | "last_run">;
    if (method === "GET" && path === "/schedules") {
      // Web アプリと同じ並び: 表示順の昇順（無いものは末尾）、同じ値の中は時刻、id の順
      const sorted = [...current].sort(
        (a, b) =>
          (a.display_order ?? Number.POSITIVE_INFINITY) - (b.display_order ?? Number.POSITIVE_INFINITY) ||
          a.run_time.localeCompare(b.run_time) ||
          a.id - b.id,
      );
      return res({ schedules: sorted });
    }
    if (method === "POST" && path === "/schedules") {
      const created: ScheduleItem = { id: nextId++, ...input, last_run: null };
      current = [...current, created];
      return res(created, 201);
    }
    const put = path.match(/^\/schedules\/(\d+)$/);
    if (method === "PUT" && put) {
      const id = Number(put[1]);
      const old = current.find((s) => s.id === id)!;
      const updated: ScheduleItem = { ...old, ...input, id };
      current = current.map((s) => (s.id === id ? updated : s));
      return res(updated);
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
const dialog = (w: VueWrapper) => w.get("[role=dialog]");

async function fillAndSave(
  wrapper: VueWrapper,
  values: { condition: string; time: string; scene: string },
): Promise<void> {
  await wrapper.get(`input[name="condition"][value="${values.condition}"]`).setValue(true);
  await wrapper.get("#schedule-time").setValue(values.time);
  await wrapper.get('input[name="action-type"][value="scene"]').setValue(true);
  await wrapper.get("#schedule-scene").setValue(values.scene);
  await wrapper.get("form").trigger("submit");
  await flushPromises();
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("新規登録", () => {
  it("新規を押すと、登録の入力モーダルが開く", async () => {
    mockApi(serverHandler([item()]));
    const wrapper = await mountSchedules();
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);

    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");

    expect(dialog(wrapper).attributes("aria-label")).toBe("定期実行の登録");
  });

  it("保存すると POST し、モーダルを閉じ、一覧に（時刻順で）加え、「登録しました。」を示す", async () => {
    const { calls } = mockApi(serverHandler([item({ id: 1, run_time: "07:00" }), item({ id: 2, run_time: "22:00" })]));
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");

    await fillAndSave(wrapper, { condition: "daily", time: "12:30", scene: "out" });

    expect(calls.filter((c) => c.method !== "GET").at(-1)).toEqual({
      method: "POST",
      path: "/schedules",
      body: { condition: "daily", weekdays: [], run_time: "12:30", scene: "out", title: null, display_order: null, is_enabled: true },
    });
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(rows(wrapper).map((r) => r.get(".sch-time").text())).toEqual(["07:00", "12:30", "22:00"]);
    expect(row(wrapper, 100).get(".sch-condition").text()).toBe("毎日");
    expect(row(wrapper, 100).get(".sch-scene").text()).toBe("お出かけ");
    expect(row(wrapper, 100).get(".sch-last").text()).toBe("未実行");
    expect(status(wrapper).text()).toBe("登録しました。");
    expect(status(wrapper).classes()).not.toContain("is-error");
  });

  it("曜日の指定で登録すると、一覧に「月・水」のように表示される", async () => {
    mockApi(serverHandler([item()]));
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await wrapper.get('input[value="weekdays"]').setValue(true);
    await wrapper.get('[aria-label="水曜日"]').trigger("click");
    await wrapper.get('[aria-label="月曜日"]').trigger("click");
    await wrapper.get("#schedule-time").setValue("06:00");
    await wrapper.get('input[name="action-type"][value="scene"]').setValue(true);
    await wrapper.get("#schedule-scene").setValue("indirect_light");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(row(wrapper, 100).get(".sch-condition").text()).toBe("月・水");
  });

  it("祝日を除く・の前の日の個別切替を登録すると、一覧に条件と実行内容が表示される", async () => {
    mockApi(serverHandler([item()]));
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await wrapper.get('input[value="weekdays"]').setValue(true);
    for (const label of ["月", "火", "水", "木", "金"]) {
      await wrapper.get(`[aria-label="${label}曜日"]`).trigger("click");
    }
    await wrapper.get('input[name="holiday-mode"][value="exclude"]').setValue(true);
    await wrapper.get('input[name="day-shift"][value="before"]').setValue(true);
    await wrapper.get("#schedule-time").setValue("21:30");
    await wrapper.get('input[name="action-type"][value="device"]').setValue(true);
    await wrapper.get("#schedule-device").setValue("indirect_light");
    await wrapper.get('input[name="state"][value="on"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(row(wrapper, 100).get(".sch-condition").text()).toBe("月・火・水・木・金（祝日を除く）の前の日");
    expect(row(wrapper, 100).get(".sch-scene").text()).toBe("間接照明を ON");
  });

  it("空の一覧からも登録でき、表が現れる", async () => {
    mockApi(serverHandler([]));
    const wrapper = await mountSchedules();
    expect(wrapper.text()).toContain("データがありません");

    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await fillAndSave(wrapper, { condition: "daily", time: "07:00", scene: "out" });

    expect(wrapper.text()).not.toContain("データがありません");
    expect(rows(wrapper)).toHaveLength(1);
  });

  it("一覧を取得できていなかったときは、登録のあとに取得し直す", async () => {
    let listFails = true;
    const base = serverHandler([item({ id: 1 })]);
    const { calls } = mockApi((call) =>
      call.method === "GET" && listFails ? res({}, 500) : base(call),
    );
    const wrapper = await mountSchedules();
    expect(wrapper.get("[role=alert]").text()).toBe("定期実行を取得できませんでした。");

    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    listFails = false;
    await fillAndSave(wrapper, { condition: "daily", time: "08:00", scene: "out" });

    // 登録した 1 件だけでなく、既存の分も含めて、取得し直した一覧が出る
    expect(calls.filter((c) => c.method === "GET")).toHaveLength(2);
    expect(rows(wrapper)).toHaveLength(2);
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
  });

  it("登録の成功の一文は数秒で消える", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    mockApi(serverHandler([item()]));
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await fillAndSave(wrapper, { condition: "daily", time: "08:00", scene: "out" });
    expect(status(wrapper).text()).toBe("登録しました。");

    vi.advanceTimersByTime(4000);
    await flushPromises();
    expect(status(wrapper).text()).toBe("");
  });
});

describe("変更", () => {
  it("編集を押すと、現在の値が入った変更の入力モーダルが開く", async () => {
    mockApi(
      serverHandler([item({ id: 5, condition: "weekdays", weekdays: [2, 4], run_time: "21:15", scene: "bedside_speaker", is_enabled: false })]),
    );
    const wrapper = await mountSchedules();

    await row(wrapper, 5).get('[aria-label="編集"]').trigger("click");

    expect(dialog(wrapper).attributes("aria-label")).toBe("定期実行の変更");
    expect((wrapper.get("#schedule-time").element as HTMLInputElement).value).toBe("21:15");
    expect((wrapper.get("#schedule-scene").element as HTMLSelectElement).value).toBe("bedside_speaker");
    expect(wrapper.get('[aria-label="火曜日"]').attributes("aria-checked")).toBe("true");
    expect(wrapper.get('[aria-label="木曜日"]').attributes("aria-checked")).toBe("true");
    expect(wrapper.get('[role="switch"]').attributes("aria-checked")).toBe("false");
  });

  it("保存すると PUT し、一覧のその行が更新され、並びも更新される。「変更しました。」を示す", async () => {
    const last = { at: "2026-10-01T07:00:02+09:00", result: "success" as const, failed_devices: [] };
    const { calls } = mockApi(
      serverHandler([item({ id: 1, run_time: "07:00", last_run: last }), item({ id: 2, run_time: "12:00" })]),
    );
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="編集"]').trigger("click");

    await wrapper.get("#schedule-time").setValue("20:00");
    await wrapper.get("#schedule-scene").setValue("out");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(calls.filter((c) => c.method !== "GET").at(-1)).toEqual({
      method: "PUT",
      path: "/schedules/1",
      body: { condition: "daily", weekdays: [], run_time: "20:00", scene: "out", title: null, display_order: null, is_enabled: true },
    });
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    // 時刻が変わったので、並びも変わる
    expect(rows(wrapper).map((r) => r.attributes("data-schedule-id"))).toEqual(["2", "1"]);
    expect(row(wrapper, 1).get(".sch-time").text()).toBe("20:00");
    expect(row(wrapper, 1).get(".sch-scene").text()).toBe("お出かけ");
    // 最終実行は変わらない
    expect(row(wrapper, 1).get(".sch-result").text()).toBe("✓ 成功");
    expect(status(wrapper).text()).toBe("変更しました。");
  });

  it("変更で有効／無効も変えられる", async () => {
    mockApi(serverHandler([item({ id: 1, is_enabled: true })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="編集"]').trigger("click");
    await wrapper.get('[role="switch"][aria-labelledby="schedule-enabled-label"]').trigger("click");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(row(wrapper, 1).get('[role="switch"]').attributes("aria-checked")).toBe("false");
    expect(row(wrapper, 1).classes()).toContain("is-disabled");
  });
});

describe("キャンセル・失敗", () => {
  it("キャンセルすると、何も送らず、一覧も変えずに閉じる", async () => {
    const { calls } = mockApi(serverHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="編集"]').trigger("click");
    await wrapper.get("#schedule-time").setValue("23:00");

    await wrapper.get('[aria-label="キャンセル"]').trigger("click");

    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(calls.filter((c) => c.method !== "GET")).toHaveLength(0);
    expect(row(wrapper, 1).get(".sch-time").text()).toBe("07:00");
    expect(status(wrapper).text()).toBe("");
  });

  it("背景を押しても閉じない。Esc では閉じる", async () => {
    mockApi(serverHandler([item({ id: 1 })]));
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");

    await wrapper.get(".dialog-overlay").trigger("click");
    expect(wrapper.find("[role=dialog]").exists()).toBe(true);

    await dialog(wrapper).trigger("keydown", { key: "Escape" });
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
  });

  it("保存に失敗したら、モーダルは開いたまま、モーダルの先頭にエラーを示し、一覧は変わらない", async () => {
    const base = serverHandler([item({ id: 1, run_time: "07:00" })]);
    mockApi((call) => (call.method === "PUT" ? res({ detail: "x" }, 400) : base(call)));
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[aria-label="編集"]').trigger("click");
    await wrapper.get("#schedule-time").setValue("09:00");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(wrapper.find("[role=dialog]").exists()).toBe(true);
    expect(dialog(wrapper).get("[role=alert]").text()).toBe(
      "保存できませんでした。入力内容を確認してください。",
    );
    expect((wrapper.get("#schedule-time").element as HTMLInputElement).value).toBe("09:00");
    expect(row(wrapper, 1).get(".sch-time").text()).toBe("07:00");
    expect(status(wrapper).text()).toBe("");
  });

  it.each([401, 403] as const)("保存で %s なら、モーダルを閉じ、親（殻）へ auth-error を伝える", async (code) => {
    const base = serverHandler([item()]);
    mockApi((call) => (call.method === "POST" ? res({ detail: "x" }, code) : base(call)));
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await fillAndSave(wrapper, { condition: "daily", time: "08:00", scene: "out" });

    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    const emitted = wrapper.emitted("auth-error")!;
    expect(emitted).toHaveLength(1);
    expect(emitted[0]![0]).toBeInstanceOf(AuthError);
    expect((emitted[0]![0] as AuthError).status).toBe(code);
  });
});


describe("保存のあとの並び（Web アプリが決める並びのまま）", () => {
  it("保存のあとに、一覧を取り直し、表示順の小さいものが先に並ぶ", async () => {
    const { calls } = mockApi(
      serverHandler([item({ id: 1, run_time: "07:00" }), item({ id: 2, run_time: "09:00", display_order: 5 })]),
    );
    const wrapper = await mountSchedules();
    // 表示順のあるもの（2）が先、表示順なし（1）が末尾
    expect(rows(wrapper).map((r) => r.attributes("data-schedule-id"))).toEqual(["2", "1"]);

    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await wrapper.get('input[value="daily"]').setValue(true);
    await wrapper.get("#schedule-time").setValue("23:00");
    await wrapper.get('input[name="action-type"][value="scene"]').setValue(true);
    await wrapper.get("#schedule-scene").setValue("out");
    await wrapper.get("#schedule-title").setValue("先頭にしたい");
    await wrapper.get("#schedule-display-order").setValue("0");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    // 保存のあとに、一覧を取り直している（GET は、開いたときと、保存のあとの 2 回）
    expect(calls.filter((c) => c.method === "GET" && c.path === "/schedules")).toHaveLength(2);
    expect(rows(wrapper).map((r) => r.attributes("data-schedule-id"))).toEqual(["100", "2", "1"]);
    expect(row(wrapper, 100).get(".sch-title").text()).toBe("先頭にしたい");
    expect(status(wrapper).text()).toBe("登録しました。");
  });

  it("変更で表示順を付けると、並びが変わる。外すと戻る", async () => {
    mockApi(serverHandler([item({ id: 1, run_time: "07:00" }), item({ id: 2, run_time: "09:00" })]));
    const wrapper = await mountSchedules();
    expect(rows(wrapper).map((r) => r.attributes("data-schedule-id"))).toEqual(["1", "2"]);

    await row(wrapper, 2).get('[aria-label="編集"]').trigger("click");
    await wrapper.get("#schedule-display-order").setValue("0");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(rows(wrapper).map((r) => r.attributes("data-schedule-id"))).toEqual(["2", "1"]);

    await row(wrapper, 2).get('[aria-label="編集"]').trigger("click");
    await wrapper.get("#schedule-display-order").setValue("");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(rows(wrapper).map((r) => r.attributes("data-schedule-id"))).toEqual(["1", "2"]);
  });

  it("取り直しに失敗しても、保存した 1 件は一覧に反映し、「登録しました。」を示す", async () => {
    let getCount = 0;
    const base = serverHandler([item({ id: 1 })]);
    mockApi((call) => {
      if (call.method === "GET" && call.path === "/schedules") {
        getCount += 1;
        if (getCount >= 2) {
          return res({}, 500); // 保存のあとの取り直しだけ失敗する
        }
      }
      return base(call);
    });
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await fillAndSave(wrapper, { condition: "daily", time: "08:00", scene: "out" });

    expect(rows(wrapper)).toHaveLength(2);
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(status(wrapper).text()).toBe("登録しました。");
  });

  it.each([401, 403] as const)("保存のあとの取り直しで %s なら、親（殻）へ auth-error を伝える", async (code) => {
    let getCount = 0;
    const base = serverHandler([item({ id: 1 })]);
    mockApi((call) => {
      if (call.method === "GET" && call.path === "/schedules") {
        getCount += 1;
        if (getCount >= 2) {
          return res({}, code);
        }
      }
      return base(call);
    });
    const wrapper = await mountSchedules();
    await wrapper.get('.schedules-top [aria-label="新規"]').trigger("click");
    await fillAndSave(wrapper, { condition: "daily", time: "08:00", scene: "out" });
    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
  });

  it("有効／無効の切替と削除では、一覧を取り直さない（並びは変わらない）", async () => {
    const { calls } = mockApi(
      (() => {
        const base = serverHandler([item({ id: 1 }), item({ id: 2, run_time: "09:00" })]);
        return (call: Parameters<typeof base>[0]) =>
          call.method === "PUT" && call.path.endsWith("/enabled")
            ? res({ ...item({ id: 1 }), is_enabled: false })
            : call.method === "DELETE"
              ? res({}, 204)
              : base(call);
      })(),
    );
    const wrapper = await mountSchedules();
    await row(wrapper, 1).get('[role="switch"]').trigger("click");
    await flushPromises();
    expect(calls.filter((c) => c.method === "GET")).toHaveLength(1);
  });
});
