import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import ScheduleEditor from "../src/components/ScheduleEditor.vue";
import {
  formFromItem,
  toScheduleBody,
  validateScheduleForm,
  validateTitleAndOrder,
  type ScheduleForm,
  type ScheduleItem,
} from "../src/room";
import { deferred, mockApi, res, type Handler } from "./helpers";

function item(override: Partial<ScheduleItem> = {}): ScheduleItem {
  return {
    id: 7,
    condition: "weekdays",
    weekdays: [1, 3],
    holiday_mode: "none",
    day_shift: "same",
    run_time: "22:30",
    scene: "out",
    device: null,
    state: null,
    is_enabled: false,
    last_run: null,
    ...override,
  };
}

function mountEditor(target: ScheduleItem | null = null, attach = false): VueWrapper {
  return mount(ScheduleEditor, {
    props: { item: target },
    ...(attach ? { attachTo: document.body } : {}),
  });
}

/** 登録（201）と変更（200）に成功する。応答は、受けた本文に識別子と最終実行を足したもの。 */
const okHandler: Handler = ({ method, path, body }) => {
  const input = body as Omit<ScheduleItem, "id" | "last_run">;
  if (method === "POST" && path === "/schedules") {
    return res({ id: 99, ...input, last_run: null }, 201);
  }
  if (method === "PUT" && /^\/schedules\/\d+$/.test(path)) {
    return res({ id: Number(path.split("/")[2]), ...input, last_run: null });
  }
  return res({}, 404);
};

async function fill(
  wrapper: VueWrapper,
  values: { condition?: string; time?: string; scene?: string },
): Promise<void> {
  if (values.condition !== undefined) {
    await wrapper.get(`input[name="condition"][value="${values.condition}"]`).setValue(true);
  }
  if (values.time !== undefined) {
    await wrapper.get("#schedule-time").setValue(values.time);
  }
  if (values.scene !== undefined) {
    await wrapper.get('input[name="action-type"][value="scene"]').setValue(true);
    await wrapper.get("#schedule-scene").setValue(values.scene);
  }
}

const submit = (w: VueWrapper) => w.get("form").trigger("submit");
const errorText = (w: VueWrapper) => w.find("[role=alert]").text();
const chip = (w: VueWrapper, label: string) => w.get(`[aria-label="${label}曜日"]`);

afterEach(() => {
  vi.unstubAllGlobals();
});

const emptyForm: ScheduleForm = {
  condition: "",
  weekdays: [],
  holidayMode: "none",
  dayShift: "same",
  time: "",
  actionType: "",
  scene: "",
  device: "",
  state: "",
  pattern: "full",
  title: "",
  displayOrder: "",
  enabled: true,
};

describe("入力フォームの補助関数", () => {
  const valid: ScheduleForm = {
    ...emptyForm,
    condition: "daily",
    time: "07:00",
    actionType: "scene",
    scene: "out",
  };

  it("正しい入力は null（問題なし）", () => {
    expect(validateScheduleForm(valid)).toBeNull();
    expect(validateScheduleForm({ ...valid, condition: "weekdays", weekdays: [3] })).toBeNull();
    expect(validateScheduleForm({ ...valid, time: "00:00" })).toBeNull();
    expect(validateScheduleForm({ ...valid, time: "23:59" })).toBeNull();
  });

  it("実行条件が未選択", () => {
    expect(validateScheduleForm({ ...valid, condition: "" })).toBe("実行条件を選択してください。");
  });

  it("曜日の指定で曜日が 0 件", () => {
    expect(validateScheduleForm({ ...valid, condition: "weekdays", weekdays: [] })).toBe(
      "曜日を 1 つ以上選択してください。",
    );
  });

  it("曜日の指定でないときは、曜日が空でもよい（選んだ曜日が残っていてもよい）", () => {
    expect(validateScheduleForm({ ...valid, condition: "daily", weekdays: [] })).toBeNull();
    expect(validateScheduleForm({ ...valid, condition: "daily", weekdays: [1, 2] })).toBeNull();
  });

  it.each(["", "7:00", "24:00", "12:60", "07:00:30", "abc", "0700", "07-00"])(
    "時刻 %j は形式の誤り",
    (time) => {
      expect(validateScheduleForm({ ...valid, time })).toBe(
        "時刻を HH:MM の形式で入力してください。",
      );
    },
  );

  it("実行内容の種類が未選択", () => {
    expect(validateScheduleForm({ ...valid, actionType: "", scene: "" })).toBe(
      "実行内容を選択してください。",
    );
  });

  it("一括切替が未選択", () => {
    expect(validateScheduleForm({ ...valid, scene: "" })).toBe("一括切替を選択してください。");
  });

  it("機器の個別切替: 機器が未選択、状態が未選択", () => {
    const device = { ...valid, actionType: "device" as const, scene: "" as const };
    expect(validateScheduleForm(device)).toBe("機器を選択してください。");
    expect(validateScheduleForm({ ...device, device: "indirect_light" })).toBe(
      "状態（ON / OFF）を選択してください。",
    );
    expect(validateScheduleForm({ ...device, state: "on" })).toBe("機器を選択してください。");
    expect(validateScheduleForm({ ...device, device: "indirect_light", state: "off" })).toBeNull();
  });

  it("個別切替では、一括切替が残っていても検証に影響しない", () => {
    expect(
      validateScheduleForm({ ...valid, actionType: "device", scene: "out", device: "indoor_speaker", state: "on" }),
    ).toBeNull();
  });

  it("問題が複数あるときは、最初の 1 件だけを返す（実行条件 → 曜日 → 時刻 → 実行内容の順）", () => {
    expect(validateScheduleForm(emptyForm)).toBe("実行条件を選択してください。");
    expect(validateScheduleForm({ ...emptyForm, condition: "weekdays" })).toBe(
      "曜日を 1 つ以上選択してください。",
    );
    expect(validateScheduleForm({ ...emptyForm, condition: "daily" })).toBe(
      "時刻を HH:MM の形式で入力してください。",
    );
    expect(validateScheduleForm({ ...emptyForm, condition: "daily", time: "07:00" })).toBe(
      "実行内容を選択してください。",
    );
  });

  it("本文（毎日・一括切替）: 曜日・祝日の扱い・実行日の取り方・機器・状態を付けない", () => {
    expect(toScheduleBody({ ...valid, weekdays: [1, 2], holidayMode: "exclude", dayShift: "before" })).toEqual({
      condition: "daily",
      weekdays: [],
      run_time: "07:00",
      scene: "out",
      title: null,
      display_order: null,
      is_enabled: true,
    });
  });

  it("本文（曜日の指定）: 曜日を昇順で、祝日の扱いと実行日の取り方を付ける", () => {
    expect(
      toScheduleBody({
        ...valid,
        condition: "weekdays",
        weekdays: [5, 1, 3],
        holidayMode: "exclude",
        dayShift: "after",
      }),
    ).toEqual({
      condition: "weekdays",
      weekdays: [1, 3, 5],
      holiday_mode: "exclude",
      day_shift: "after",
      run_time: "07:00",
      scene: "out",
      title: null,
      display_order: null,
      is_enabled: true,
    });
  });

  it("本文（個別切替）: device と state だけを付け、scene を付けない", () => {
    expect(
      toScheduleBody({
        ...valid,
        actionType: "device",
        scene: "out",
        device: "bedside_speaker",
        state: "off",
      }),
    ).toEqual({
      condition: "daily",
      weekdays: [],
      run_time: "07:00",
      device: "bedside_speaker",
      state: "off",
      title: null,
      display_order: null,
      is_enabled: true,
    });
  });

  it("初期値: 新規は空で有効、変更は現在の値（元の配列を共有しない）", () => {
    expect(formFromItem(null)).toEqual(emptyForm);
    const source = item();
    const form = formFromItem(source);
    expect(form).toEqual({
      ...emptyForm,
      condition: "weekdays",
      weekdays: [1, 3],
      time: "22:30",
      actionType: "scene",
      scene: "out",
      enabled: false,
    });
    form.weekdays.push(7);
    expect(source.weekdays).toEqual([1, 3]);
  });

  it("初期値: 祝日の扱い・実行日の取り方・個別切替の内容が入る", () => {
    expect(
      formFromItem(
        item({
          holiday_mode: "include",
          day_shift: "before",
          scene: null,
          device: "indirect_light",
          state: "off",
        }),
      ),
    ).toMatchObject({
      holidayMode: "include",
      dayShift: "before",
      actionType: "device",
      scene: "",
      device: "indirect_light",
      state: "off",
    });
  });
});

describe("表示", () => {
  it("新規: 見出しは「定期実行の登録」。実行条件は未選択、有効は ON、曜日は出さない", () => {
    const wrapper = mountEditor();
    expect(wrapper.get("[role=dialog]").attributes("aria-label")).toBe("定期実行の登録");
    expect(wrapper.get(".editor-title").text()).toBe("定期実行の登録");
    expect(wrapper.get("[role=dialog]").attributes("aria-modal")).toBe("true");
    const radios = wrapper.findAll('input[name="condition"]');
    expect(radios.map((r) => (r.element as HTMLInputElement).value)).toEqual([
      "daily",
      "weekdays",
    ]);
    expect(radios.every((r) => !(r.element as HTMLInputElement).checked)).toBe(true);
    expect(wrapper.get('[role="switch"]').attributes("aria-checked")).toBe("true");
    expect(wrapper.find(".chips").exists()).toBe(false);
    expect((wrapper.get("#schedule-time").element as HTMLInputElement).value).toBe("");
    expect(wrapper.find("#schedule-scene").exists()).toBe(false);
    expect(wrapper.find("#schedule-device").exists()).toBe(false);
  });

  it("実行条件の選択肢は「毎日」「曜日の指定」の 2 つだけ", () => {
    const wrapper = mountEditor();
    const labels = wrapper
      .findAll('input[name="condition"]')
      .map((r) => r.element.parentElement?.textContent?.trim());
    expect(labels).toEqual([
      "毎日",
      "曜日の指定",
    ]);
  });

  it("一括切替の選択肢は 5 種だけで、玄関ドアの施錠・開錠を含めない", async () => {
    const wrapper = mountEditor();
    await wrapper.get('input[name="action-type"][value="scene"]').setValue(true);
    const options = wrapper.findAll("#schedule-scene option").map((o) => o.text());
    expect(options).toEqual([
      "選択してください",
      "屋内スピーカー選択",
      "枕元スピーカー選択",
      "電灯選択",
      "間接照明選択",
      "お出かけ",
    ]);
    expect(options.join("")).not.toMatch(/玄関|施錠|開錠/);
  });

  it("「曜日の指定」を選ぶと、月〜日の 7 つのチップが出る。選択は ✓ の記号でも示す", async () => {
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "weekdays" });

    const chips = wrapper.findAll(".chip");
    expect(chips).toHaveLength(7);
    expect(chips.map((c) => c.text())).toEqual(["月", "火", "水", "木", "金", "土", "日"]);
    expect(chips.every((c) => c.attributes("aria-checked") === "false")).toBe(true);

    await chip(wrapper, "水").trigger("click");
    expect(chip(wrapper, "水").attributes("aria-checked")).toBe("true");
    expect(chip(wrapper, "水").text()).toBe("✓ 水");
    expect(chip(wrapper, "水").classes()).toContain("is-selected");
    await chip(wrapper, "水").trigger("click"); // もう一度押すと外れる
    expect(chip(wrapper, "水").attributes("aria-checked")).toBe("false");
    expect(chip(wrapper, "水").text()).toBe("水");
  });

  it("「曜日の指定」以外に切り替えると、チップが消える", async () => {
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "weekdays" });
    expect(wrapper.find(".chips").exists()).toBe(true);
    await fill(wrapper, { condition: "daily" });
    expect(wrapper.find(".chips").exists()).toBe(false);
  });

  it("変更: 見出しは「定期実行の変更」。現在の値が入っている", () => {
    const wrapper = mountEditor(item());
    expect(wrapper.get(".editor-title").text()).toBe("定期実行の変更");
    expect((wrapper.get('input[value="weekdays"]').element as HTMLInputElement).checked).toBe(true);
    expect(chip(wrapper, "月").attributes("aria-checked")).toBe("true");
    expect(chip(wrapper, "火").attributes("aria-checked")).toBe("false");
    expect(chip(wrapper, "水").attributes("aria-checked")).toBe("true");
    expect((wrapper.get("#schedule-time").element as HTMLInputElement).value).toBe("22:30");
    expect((wrapper.get("#schedule-scene").element as HTMLSelectElement).value).toBe("out");
    expect(wrapper.get('[role="switch"]').attributes("aria-checked")).toBe("false");
    expect(wrapper.get('[role="switch"]').text()).toBe("無効");
  });

  it("有効のスイッチは、押すと有効／無効が切り替わり、文言でも示す", async () => {
    const wrapper = mountEditor();
    const toggle = wrapper.get('[role="switch"]');
    expect(toggle.text()).toBe("有効");
    await toggle.trigger("click");
    expect(toggle.attributes("aria-checked")).toBe("false");
    expect(toggle.text()).toBe("無効");
    await toggle.trigger("click");
    expect(toggle.text()).toBe("有効");
  });

  it("保存とキャンセルはアイコンのみで、aria-label を持つ", () => {
    const wrapper = mountEditor();
    const save = wrapper.get('[aria-label="保存"]');
    const cancel = wrapper.get('[aria-label="キャンセル"]');
    expect(save.text()).toBe("");
    expect(cancel.text()).toBe("");
    expect(save.find("svg").exists()).toBe(true);
    expect(cancel.find("svg").exists()).toBe(true);
    expect(save.attributes("type")).toBe("submit");
  });

  it("開いたとき、最初の入力欄にフォーカスがある", async () => {
    const wrapper = mountEditor(null, true);
    await flushPromises();
    expect(document.activeElement).toBe(wrapper.get('input[value="daily"]').element);
    wrapper.unmount();
  });
});

describe("送信前の検証", () => {
  it.each([
    [{}, "実行条件を選択してください。"],
    [{ condition: "weekdays", time: "07:00", scene: "out" }, "曜日を 1 つ以上選択してください。"],
    [{ condition: "daily", scene: "out" }, "時刻を HH:MM の形式で入力してください。"],
    [{ condition: "daily", time: "07:00" }, "実行内容を選択してください。"],
  ])("入力 %j は送信せず、先頭に「%s」を示し、モーダルは開いたまま", async (values, message) => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, values);

    await submit(wrapper);
    await flushPromises();

    expect(errorText(wrapper)).toBe(message);
    expect(calls).toHaveLength(0);
    expect(wrapper.emitted("saved")).toBeUndefined();
    expect(wrapper.emitted("cancel")).toBeUndefined();
  });

  it("エラーはモーダルの先頭（見出しの直後）に出る", async () => {
    mockApi(okHandler);
    const wrapper = mountEditor();
    await submit(wrapper);
    const children = Array.from(wrapper.get("form").element.children);
    expect(children[0]!.className).toBe("editor-title");
    expect(children[1]!.getAttribute("role")).toBe("alert");
  });

  it("直して再び送信すると、エラーが消えて保存される", async () => {
    mockApi(okHandler);
    const wrapper = mountEditor();
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("実行条件を選択してください。");

    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });
    await submit(wrapper);
    await flushPromises();
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
    expect(wrapper.emitted("saved")).toHaveLength(1);
  });
});

describe("登録", () => {
  it.each([
    ["毎日", { condition: "daily", time: "07:00", scene: "indoor_speaker" }, [], "daily"],
    ["毎日（電灯選択）", { condition: "daily", time: "09:15", scene: "ceiling_light" }, [], "daily"],
  ])("%s の定期実行を POST /schedules で登録する", async (_name, values, weekdays, condition) => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, values);

    await submit(wrapper);
    await flushPromises();

    expect(calls).toEqual([
      {
        method: "POST",
        path: "/schedules",
        body: {
          condition,
          weekdays,
          run_time: values.time,
          scene: values.scene,
          title: null,
          display_order: null,
          is_enabled: true,
        },
      },
    ]);
  });

  it("曜日の指定は、選んだ曜日を昇順で送る", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "weekdays", time: "22:30", scene: "out" });
    for (const label of ["金", "月", "水"]) {
      await chip(wrapper, label).trigger("click");
    }

    await submit(wrapper);
    await flushPromises();

    expect(calls[0]!.body).toEqual({
      condition: "weekdays",
      weekdays: [1, 3, 5],
      holiday_mode: "none",
      day_shift: "same",
      run_time: "22:30",
      scene: "out",
      title: null,
      display_order: null,
      is_enabled: true,
    });
  });

  it("曜日を選んだあとで「毎日」に変えたら、曜日は送らない", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "weekdays", time: "07:00", scene: "out" });
    await chip(wrapper, "月").trigger("click");
    await fill(wrapper, { condition: "daily" });

    await submit(wrapper);
    await flushPromises();

    expect((calls[0]!.body as { weekdays: number[] }).weekdays).toEqual([]);
  });

  it("無効にして登録できる", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });
    await wrapper.get('[role="switch"]').trigger("click");

    await submit(wrapper);
    await flushPromises();

    expect((calls[0]!.body as { is_enabled: boolean }).is_enabled).toBe(false);
  });

  it("保存ボタンを押しても送信される", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(null, true);
    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(calls).toHaveLength(1);
    wrapper.unmount();
  });

  it("成功したら、登録した定期実行と created を伝える", async () => {
    mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });

    await submit(wrapper);
    await flushPromises();

    const emitted = wrapper.emitted("saved")!;
    expect(emitted).toHaveLength(1);
    const [saved, mode] = emitted[0] as [ScheduleItem, string];
    expect(mode).toBe("created");
    expect(saved).toMatchObject({ id: 99, condition: "daily", run_time: "07:00", scene: "out" });
  });
});

describe("変更", () => {
  it("PUT /schedules/{id} で全項目を送り、updated を伝える", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(item());
    await fill(wrapper, { time: "06:45", scene: "bedside_speaker" });
    await chip(wrapper, "金").trigger("click");
    await wrapper.get('[role="switch"]').trigger("click"); // 無効 → 有効

    await submit(wrapper);
    await flushPromises();

    expect(calls).toEqual([
      {
        method: "PUT",
        path: "/schedules/7",
        body: {
          condition: "weekdays",
          weekdays: [1, 3, 5],
          holiday_mode: "none",
          day_shift: "same",
          run_time: "06:45",
          scene: "bedside_speaker",
          title: null,
          display_order: null,
          is_enabled: true,
        },
      },
    ]);
    const [saved, mode] = wrapper.emitted("saved")![0] as [ScheduleItem, string];
    expect(mode).toBe("updated");
    expect(saved.id).toBe(7);
  });

  it("実行条件を変えると、曜日を外して送る", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(item());
    await fill(wrapper, { condition: "daily" });
    await submit(wrapper);
    await flushPromises();
    expect(calls[0]!.body).toMatchObject({ condition: "daily", weekdays: [] });
  });

  it("変更でも、曜日の指定で曜日を外して 0 件にすると送信しない", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(item());
    await chip(wrapper, "月").trigger("click");
    await chip(wrapper, "水").trigger("click");
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("曜日を 1 つ以上選択してください。");
    expect(calls).toHaveLength(0);
  });
});

describe("保存の失敗", () => {
  async function filled(handler: Handler): Promise<VueWrapper> {
    mockApi(handler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });
    return wrapper;
  }

  it("400 は入力の見直しを促し、モーダルは開いたまま、入力は残る", async () => {
    const wrapper = await filled(() => res({ detail: "入力が不正です" }, 400));
    await submit(wrapper);
    await flushPromises();

    expect(errorText(wrapper)).toBe("保存できませんでした。入力内容を確認してください。");
    expect(wrapper.emitted("saved")).toBeUndefined();
    expect(wrapper.emitted("cancel")).toBeUndefined();
    expect((wrapper.get("#schedule-time").element as HTMLInputElement).value).toBe("07:00");
    expect((wrapper.get("#schedule-scene").element as HTMLSelectElement).value).toBe("out");
    expect(wrapper.get('[aria-label="保存"]').attributes("disabled")).toBeUndefined();
  });

  it.each([404, 500, 502])("%s は「操作に失敗しました。」（内部理由は出さない）", async (code) => {
    const wrapper = await filled(() => res({ detail: "内部の理由 TESTID" }, code));
    await submit(wrapper);
    await flushPromises();
    expect(errorText(wrapper)).toBe("操作に失敗しました。");
    expect(wrapper.text()).not.toContain("内部の理由");
    expect(wrapper.emitted("saved")).toBeUndefined();
  });

  it("通信できないときも「操作に失敗しました。」", async () => {
    const wrapper = await filled(() => {
      throw new TypeError("Failed to fetch");
    });
    await submit(wrapper);
    await flushPromises();
    expect(errorText(wrapper)).toBe("操作に失敗しました。");
    expect(wrapper.text()).not.toContain("Failed to fetch");
  });

  it("失敗のあと、直さずにもう一度保存できる", async () => {
    let n = 0;
    const wrapper = await filled((call) => (n++ === 0 ? res({}, 500) : okHandler(call)));
    await submit(wrapper);
    await flushPromises();
    expect(errorText(wrapper)).toBe("操作に失敗しました。");

    await submit(wrapper);
    await flushPromises();
    expect(wrapper.emitted("saved")).toHaveLength(1);
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
  });

  it.each([401, 403] as const)("%s は親へ auth-error を伝える（エラーの一文は出さない）", async (code) => {
    const wrapper = await filled(() => res({ detail: "x" }, code));
    await submit(wrapper);
    await flushPromises();
    const emitted = wrapper.emitted("auth-error")!;
    expect(emitted).toHaveLength(1);
    expect(emitted[0]![0]).toBeInstanceOf(AuthError);
    expect((emitted[0]![0] as AuthError).status).toBe(code);
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
    expect(wrapper.emitted("saved")).toBeUndefined();
  });
});

describe("保存中", () => {
  it("ボタンを押せず、重ねて送信しない", async () => {
    const pending = deferred<Partial<Response>>();
    const { calls } = mockApi(() => pending.promise);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });

    await submit(wrapper);
    await flushPromises();
    expect(wrapper.get('[aria-label="保存"]').attributes("disabled")).toBeDefined();
    expect(wrapper.get('[aria-label="キャンセル"]').attributes("disabled")).toBeDefined();

    await submit(wrapper);
    expect(calls).toHaveLength(1);

    pending.resolve(
      res({ id: 1, condition: "daily", weekdays: [], run_time: "07:00", scene: "out", is_enabled: true, last_run: null }, 201),
    );
    await flushPromises();
    expect(wrapper.emitted("saved")).toHaveLength(1);
  });
});

describe("閉じる操作", () => {
  it("キャンセルは、何も送らず cancel を伝える", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "07:00", scene: "out" });
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.emitted("cancel")).toHaveLength(1);
    expect(calls).toHaveLength(0);
  });

  it("Esc もキャンセルと同じ", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await wrapper.get("[role=dialog]").trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("cancel")).toHaveLength(1);
    expect(calls).toHaveLength(0);
  });

  it("背景（オーバーレイ）を押しても閉じない", async () => {
    mockApi(okHandler);
    const wrapper = mountEditor();
    await wrapper.get(".dialog-overlay").trigger("click");
    expect(wrapper.emitted("cancel")).toBeUndefined();
  });
});


// ---- 祝日の扱い・実行日の取り方・実行内容（T-025） ----

const radioValues = (w: VueWrapper, name: string) =>
  w.findAll(`input[name="${name}"]`).map((r) => (r.element as HTMLInputElement).value);
const radioLabels = (w: VueWrapper, name: string) =>
  w.findAll(`input[name="${name}"]`).map((r) => r.element.parentElement?.textContent?.trim());
const checked = (w: VueWrapper, name: string) =>
  w
    .findAll(`input[name="${name}"]`)
    .filter((r) => (r.element as HTMLInputElement).checked)
    .map((r) => (r.element as HTMLInputElement).value);
const pick = (w: VueWrapper, name: string, value: string) =>
  w.get(`input[name="${name}"][value="${value}"]`).setValue(true);

describe("祝日の扱いと実行日の取り方", () => {
  it("実行条件が「曜日の指定」のときだけ出る", async () => {
    const wrapper = mountEditor();
    expect(wrapper.find('input[name="holiday-mode"]').exists()).toBe(false);
    expect(wrapper.find('input[name="day-shift"]').exists()).toBe(false);

    await pick(wrapper, "condition", "weekdays");
    expect(radioValues(wrapper, "holiday-mode")).toEqual(["none", "include", "exclude"]);
    expect(radioLabels(wrapper, "holiday-mode")).toEqual([
      "指定した曜日のみ",
      "祝日も実行",
      "祝日は実行しない",
    ]);
    expect(radioValues(wrapper, "day-shift")).toEqual(["same", "before", "after"]);
    expect(radioLabels(wrapper, "day-shift")).toEqual(["当日", "の前の日", "の次の日"]);

    await pick(wrapper, "condition", "daily");
    expect(wrapper.find('input[name="holiday-mode"]').exists()).toBe(false);
    expect(wrapper.find('input[name="day-shift"]').exists()).toBe(false);
  });

  it("既定は「指定した曜日のみ」と「当日」。説明が添えられる", async () => {
    const wrapper = mountEditor();
    await pick(wrapper, "condition", "weekdays");
    expect(checked(wrapper, "holiday-mode")).toEqual(["none"]);
    expect(checked(wrapper, "day-shift")).toEqual(["same"]);
    expect(wrapper.text()).toContain(
      "祝日も実行は、指定した曜日に加えて祝日にも実行します。祝日は実行しないは、指定した曜日のうち祝日を除きます。",
    );
    expect(wrapper.text()).toContain(
      "上で決まる日に対して、実行する日を選びます。の前の日は前日、の次の日は翌日に実行します。",
    );
  });

  it.each([
    ["include", "before"],
    ["exclude", "after"],
    ["none", "before"],
  ] as const)("祝日の扱い %s・実行日の取り方 %s を送る", async (mode, shift) => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "weekdays", time: "21:00", scene: "out" });
    await chip(wrapper, "月").trigger("click");
    await pick(wrapper, "holiday-mode", mode);
    await pick(wrapper, "day-shift", shift);

    await submit(wrapper);
    await flushPromises();

    expect(calls[0]!.body).toEqual({
      condition: "weekdays",
      weekdays: [1],
      holiday_mode: mode,
      day_shift: shift,
      run_time: "21:00",
      scene: "out",
      title: null,
      display_order: null,
      is_enabled: true,
    });
  });

  it("曜日の指定で選んだあと「毎日」に変えたら、祝日の扱いと実行日の取り方は送らない", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "weekdays", time: "21:00", scene: "out" });
    await chip(wrapper, "火").trigger("click");
    await pick(wrapper, "holiday-mode", "exclude");
    await pick(wrapper, "day-shift", "before");
    await pick(wrapper, "condition", "daily");

    await submit(wrapper);
    await flushPromises();

    expect(calls[0]!.body).toEqual({
      condition: "daily",
      weekdays: [],
      run_time: "21:00",
      scene: "out",
      title: null,
      display_order: null,
      is_enabled: true,
    });
  });

  it("変更: 現在の祝日の扱いと実行日の取り方が初期値に入る", () => {
    const wrapper = mountEditor(item({ holiday_mode: "exclude", day_shift: "after" }));
    expect(checked(wrapper, "holiday-mode")).toEqual(["exclude"]);
    expect(checked(wrapper, "day-shift")).toEqual(["after"]);
  });
});

describe("実行内容", () => {
  it("新規は、種類（一括切替／機器の個別切替）が未選択で、続きの入力は出ない", () => {
    const wrapper = mountEditor();
    expect(radioLabels(wrapper, "action-type")).toEqual(["一括切替", "機器の個別切替"]);
    expect(checked(wrapper, "action-type")).toEqual([]);
    expect(wrapper.find("#schedule-scene").exists()).toBe(false);
    expect(wrapper.find("#schedule-device").exists()).toBe(false);
    expect(wrapper.find('input[name="state"]').exists()).toBe(false);
  });

  it("「機器の個別切替」を選ぶと、機器（4 つ）と状態（ON/OFF）が出て、一括切替は消える", async () => {
    const wrapper = mountEditor();
    await pick(wrapper, "action-type", "device");

    expect(wrapper.find("#schedule-scene").exists()).toBe(false);
    const options = wrapper.findAll("#schedule-device option").map((o) => o.text());
    expect(options).toEqual([
      "選択してください",
      "電灯",
      "間接照明",
      "屋内スピーカー",
      "枕元スピーカー",
    ]);
    expect(radioLabels(wrapper, "state")).toEqual(["ON", "OFF"]);
    expect(checked(wrapper, "state")).toEqual([]);
  });

  it("玄関ドアは、機器の選択肢にも一括切替の選択肢にも無い", async () => {
    const wrapper = mountEditor();
    await pick(wrapper, "action-type", "device");
    const deviceValues = wrapper.findAll("#schedule-device option").map((o) => o.attributes("value"));
    expect(deviceValues).not.toContain("front_door");
    expect(wrapper.html()).not.toContain("玄関");
  });

  it("種類を切り替えると、続きの入力が入れ替わる", async () => {
    const wrapper = mountEditor();
    await pick(wrapper, "action-type", "device");
    await pick(wrapper, "action-type", "scene");
    expect(wrapper.find("#schedule-scene").exists()).toBe(true);
    expect(wrapper.find("#schedule-device").exists()).toBe(false);
  });

  it.each([
    ["ceiling_light", "on"],
    ["indirect_light", "off"],
    ["indoor_speaker", "on"],
    ["bedside_speaker", "off"],
  ])("個別切替（%s を %s）を POST し、device と state だけを送る", async (device, state) => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30" });
    await pick(wrapper, "action-type", "device");
    await wrapper.get("#schedule-device").setValue(device);
    await pick(wrapper, "state", state);

    await submit(wrapper);
    await flushPromises();

    // 電灯を ON にするときだけ、調光パターン（既定の全灯）も送る
    const pattern = device === "ceiling_light" && state === "on" ? { pattern: "full" } : {};
    expect(calls.filter((c) => c.path !== "/dimming-patterns")).toEqual([
      {
        method: "POST",
        path: "/schedules",
        body: { condition: "daily", weekdays: [], run_time: "06:30", device, state, ...pattern, title: null, display_order: null, is_enabled: true },
      },
    ]);
    const body = calls.find((c) => c.method === "POST")!.body as Record<string, unknown>;
    expect("scene" in body).toBe(false);
  });

  it("個別切替の検証: 機器 → 状態の順に、最初の 1 件を示し、送信しない", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30" });
    await pick(wrapper, "action-type", "device");

    await submit(wrapper);
    expect(errorText(wrapper)).toBe("機器を選択してください。");

    await wrapper.get("#schedule-device").setValue("indirect_light");
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("状態（ON / OFF）を選択してください。");

    expect(calls).toHaveLength(0);
  });

  it("一括切替を選んだあと個別切替に変えたら、scene は送らない", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await pick(wrapper, "action-type", "device");
    await wrapper.get("#schedule-device").setValue("indoor_speaker");
    await pick(wrapper, "state", "off");

    await submit(wrapper);
    await flushPromises();

    const body = calls[0]!.body as Record<string, unknown>;
    expect(body).toMatchObject({ device: "indoor_speaker", state: "off" });
    expect("scene" in body).toBe(false);
  });

  it("変更: 個別切替の定期実行は、種類・機器・状態が初期値に入り、PUT できる", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(
      item({ condition: "daily", weekdays: [], scene: null, device: "bedside_speaker", state: "on" }),
    );
    expect(checked(wrapper, "action-type")).toEqual(["device"]);
    expect((wrapper.get("#schedule-device").element as HTMLSelectElement).value).toBe("bedside_speaker");
    expect(checked(wrapper, "state")).toEqual(["on"]);
    expect(wrapper.find("#schedule-scene").exists()).toBe(false);

    await pick(wrapper, "state", "off");
    await submit(wrapper);
    await flushPromises();

    expect(calls).toEqual([
      {
        method: "PUT",
        path: "/schedules/7",
        body: {
          condition: "daily",
          weekdays: [],
          run_time: "22:30",
          device: "bedside_speaker",
          state: "off",
          title: null,
          display_order: null,
          is_enabled: false,
        },
      },
    ]);
  });

  it("変更: 一括切替から個別切替へ変えられる（逆も）", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(item({ condition: "daily", weekdays: [] }));
    expect(checked(wrapper, "action-type")).toEqual(["scene"]);
    await pick(wrapper, "action-type", "device");
    await wrapper.get("#schedule-device").setValue("indirect_light");
    await pick(wrapper, "state", "on");
    await submit(wrapper);
    await flushPromises();
    expect(calls[0]!.body).toMatchObject({ device: "indirect_light", state: "on" });
  });
});


// ---- 調光パターン ----

const PATTERNS_BODY = {
  default: "full",
  patterns: [
    { id: "full", name: "全灯", brightness: 100, color_temperature: 6200 },
    { id: "reading", name: "読書", brightness: 80, color_temperature: 5000 },
    { id: "relax", name: "くつろぎ", brightness: 50, color_temperature: 3000 },
    { id: "night", name: "夜", brightness: 10, color_temperature: 2700 },
  ],
};

/** 登録・変更に成功し、GET /dimming-patterns は固定の 4 種を返す。 */
const withPatterns: Handler = (call) =>
  call.method === "GET" && call.path === "/dimming-patterns" ? res(PATTERNS_BODY) : okHandler(call);

async function chooseCeilingOn(wrapper: VueWrapper): Promise<void> {
  await pick(wrapper, "action-type", "device");
  await wrapper.get("#schedule-device").setValue("ceiling_light");
  await pick(wrapper, "state", "on");
  await flushPromises();
}

const patternField = (w: VueWrapper) => w.find('[data-field="pattern"]');
const patternBodies = (calls: { method: string; body: unknown }[]) =>
  calls.filter((c) => c.method === "POST" || c.method === "PUT").map((c) => c.body as Record<string, unknown>);

describe("調光パターン", () => {
  it("機器が電灯で、状態が ON のときだけ出る", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor();
    expect(patternField(wrapper).exists()).toBe(false);

    await pick(wrapper, "action-type", "device");
    expect(patternField(wrapper).exists()).toBe(false);

    await wrapper.get("#schedule-device").setValue("ceiling_light");
    expect(patternField(wrapper).exists()).toBe(false); // 状態が未選択

    await pick(wrapper, "state", "on");
    expect(patternField(wrapper).exists()).toBe(true);

    await pick(wrapper, "state", "off");
    expect(patternField(wrapper).exists()).toBe(false);

    await pick(wrapper, "state", "on");
    await wrapper.get("#schedule-device").setValue("indirect_light");
    expect(patternField(wrapper).exists()).toBe(false);
  });

  it("一括切替（電灯選択を含む）では出ない", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "ceiling_light" });
    expect(patternField(wrapper).exists()).toBe(false);
  });

  it("4 択（全灯・読書・くつろぎ・夜）で、既定は全灯。明るさと色温度の目安を添える", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor();
    await chooseCeilingOn(wrapper);

    expect(radioLabels(wrapper, "pattern")).toEqual([
      "全灯（明るさ 100・色温度 6200）",
      "読書（明るさ 80・色温度 5000）",
      "くつろぎ（明るさ 50・色温度 3000）",
      "夜（明るさ 10・色温度 2700）",
    ]);
    expect(checked(wrapper, "pattern")).toEqual(["full"]);
  });

  it("目安を取得できなくても、4 択は選べる。その旨を示す", async () => {
    mockApi(okHandler); // GET /dimming-patterns は 404
    const wrapper = mountEditor();
    await chooseCeilingOn(wrapper);

    expect(radioLabels(wrapper, "pattern")).toEqual(["全灯", "読書", "くつろぎ", "夜"]);
    expect(patternField(wrapper).text()).toContain("明るさと色温度の目安を取得できませんでした。");
  });

  it.each([401, 403] as const)("目安の取得で %s なら親（殻）へ auth-error を伝える", async (code) => {
    mockApi((call) =>
      call.path === "/dimming-patterns" ? res({ detail: "x" }, code) : okHandler(call),
    );
    const wrapper = mountEditor();
    await chooseCeilingOn(wrapper);
    const emitted = wrapper.emitted("auth-error");
    expect(emitted).toHaveLength(1);
    expect((emitted![0]![0] as AuthError).status).toBe(code);
  });

  it("目安は、初めて出すときに 1 回だけ取得する", async () => {
    const { calls } = mockApi(withPatterns);
    const wrapper = mountEditor();
    await chooseCeilingOn(wrapper);
    await pick(wrapper, "state", "off");
    await pick(wrapper, "state", "on");
    expect(calls.filter((c) => c.path === "/dimming-patterns")).toHaveLength(1);
  });

  it("選んだパターンを、電灯を ON にする個別切替として POST する", async () => {
    const { calls } = mockApi(withPatterns);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30" });
    await chooseCeilingOn(wrapper);
    await pick(wrapper, "pattern", "reading");

    await submit(wrapper);
    await flushPromises();

    expect(patternBodies(calls)).toEqual([
      {
        condition: "daily",
        weekdays: [],
        run_time: "06:30",
        device: "ceiling_light",
        state: "on",
        pattern: "reading",
        title: null,
        display_order: null,
        is_enabled: true,
      },
    ]);
  });

  it("電灯の OFF や、電灯以外の機器、一括切替では、pattern を送らない", async () => {
    const { calls } = mockApi(withPatterns);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30" });
    await chooseCeilingOn(wrapper);
    await pick(wrapper, "pattern", "night");
    await pick(wrapper, "state", "off");

    await submit(wrapper);
    await flushPromises();
    expect("pattern" in patternBodies(calls)[0]!).toBe(false);
  });

  it("条件に合わなくなったら、選択を破棄する（次に出すときは、既定の全灯）", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor();
    await chooseCeilingOn(wrapper);
    await pick(wrapper, "pattern", "night");
    expect(checked(wrapper, "pattern")).toEqual(["night"]);

    await pick(wrapper, "state", "off");
    await pick(wrapper, "state", "on");
    expect(checked(wrapper, "pattern")).toEqual(["full"]);
  });

  it("変更では、現在のパターンが初期値に入る", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor(
      item({ condition: "daily", weekdays: [], scene: null, device: "ceiling_light", state: "on", pattern: "night" }),
    );
    await flushPromises();
    expect(patternField(wrapper).exists()).toBe(true);
    expect(checked(wrapper, "pattern")).toEqual(["night"]);
  });

  it("変更で別のパターンを選ぶと、PUT で送る", async () => {
    const { calls } = mockApi(withPatterns);
    const wrapper = mountEditor(
      item({ condition: "daily", weekdays: [], scene: null, device: "ceiling_light", state: "on", pattern: "night" }),
    );
    await flushPromises();
    await pick(wrapper, "pattern", "relax");

    await submit(wrapper);
    await flushPromises();

    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.path).toBe("/schedules/7");
    expect((put.body as Record<string, unknown>).pattern).toBe("relax");
  });

  it("電灯の ON の既存の定期実行で pattern が null でも、既定の全灯として扱う", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor(
      item({ condition: "daily", weekdays: [], scene: null, device: "ceiling_light", state: "on", pattern: null }),
    );
    await flushPromises();
    expect(checked(wrapper, "pattern")).toEqual(["full"]);
  });

  it("一括切替の既存の定期実行を変更するとき、調光パターンは出ない", async () => {
    mockApi(withPatterns);
    const wrapper = mountEditor(item({ scene: "ceiling_light" }));
    await flushPromises();
    expect(patternField(wrapper).exists()).toBe(false);
  });
});


// ---- タイトルと表示順 ----

const titleInput = (w: VueWrapper) => w.get("#schedule-title");
const orderInput = (w: VueWrapper) => w.get("#schedule-display-order");

describe("タイトルと表示順の入力", () => {
  it("新規は、どちらも空。説明（Caption）がある", () => {
    const wrapper = mountEditor();
    expect((titleInput(wrapper).element as HTMLInputElement).value).toBe("");
    expect((orderInput(wrapper).element as HTMLInputElement).value).toBe("");
    expect(wrapper.text()).toContain("一覧で見分けるための名前です。付けなくてもかまいません。");
    expect(wrapper.text()).toContain("一覧での並びです。小さい数が先に並びます。空にすると末尾に並びます。");
    expect(wrapper.get('label[for="schedule-title"]').text()).toBe("タイトル");
    expect(wrapper.get('label[for="schedule-display-order"]').text()).toBe("表示順");
  });

  it("タイトルは 50 文字を超えて入力できない（入力欄の上限）", () => {
    expect(titleInput(mountEditor()).attributes("maxlength")).toBe("50");
  });

  it("どちらも空で保存でき、title と display_order は null で送る（項目を省かない）", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await submit(wrapper);
    await flushPromises();
    const body = calls[0]!.body as Record<string, unknown>;
    expect("title" in body && "display_order" in body).toBe(true);
    expect(body.title).toBeNull();
    expect(body.display_order).toBeNull();
  });

  it("付けた値を送る。タイトルの前後の空白は取り除き、表示順は数にする", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await titleInput(wrapper).setValue("  朝の読書灯　");
    await orderInput(wrapper).setValue("12");
    await submit(wrapper);
    await flushPromises();
    const body = calls[0]!.body as Record<string, unknown>;
    expect(body.title).toBe("朝の読書灯");
    expect(body.display_order).toBe(12);
  });

  it("空白だけのタイトルは、null で送る", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await titleInput(wrapper).setValue("   ");
    await submit(wrapper);
    await flushPromises();
    expect((calls[0]!.body as Record<string, unknown>).title).toBeNull();
  });

  it.each([
    ["0", 0],
    ["9999", 9999],
    ["007", 7],
    [" 5 ", 5],
  ])("表示順 %s は、%d として送る", async (input, expected) => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await orderInput(wrapper).setValue(input);
    await submit(wrapper);
    await flushPromises();
    expect((calls[0]!.body as Record<string, unknown>).display_order).toBe(expected);
  });

  it("50 文字ちょうどのタイトルは送れる", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await titleInput(wrapper).setValue("あ".repeat(50));
    await submit(wrapper);
    await flushPromises();
    expect((calls[0]!.body as Record<string, unknown>).title).toBe("あ".repeat(50));
  });

  it("51 文字のタイトルは、理由を示し、送信しない", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
    await titleInput(wrapper).setValue("あ".repeat(51));
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("タイトルは 50 文字以内で入力してください。");
    expect(calls).toHaveLength(0);
  });

  it.each(["-1", "10000", "1.5", "abc", "１２", "1e3", "+5", "0x10", "12345"])(
    "表示順 %s は、理由を示し、送信しない",
    async (input) => {
      const { calls } = mockApi(okHandler);
      const wrapper = mountEditor();
      await fill(wrapper, { condition: "daily", time: "06:30", scene: "out" });
      await orderInput(wrapper).setValue(input);
      await submit(wrapper);
      expect(errorText(wrapper)).toBe("表示順は 0 以上 9999 以下の整数で入力してください。");
      expect(calls).toHaveLength(0);
    },
  );

  it("検証の順は、実行内容 → タイトル → 表示順。最初の 1 件だけを示す", async () => {
    mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30" });
    await titleInput(wrapper).setValue("あ".repeat(51));
    await orderInput(wrapper).setValue("-1");
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("実行内容を選択してください。"); // 実行内容が先

    await fill(wrapper, { scene: "out" });
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("タイトルは 50 文字以内で入力してください。"); // タイトルが先

    await titleInput(wrapper).setValue("朝");
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("表示順は 0 以上 9999 以下の整数で入力してください。");
  });

  it("個別切替でも、タイトルと表示順を検証する", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor();
    await fill(wrapper, { condition: "daily", time: "06:30" });
    await pick(wrapper, "action-type", "device");
    await wrapper.get("#schedule-device").setValue("indirect_light");
    await pick(wrapper, "state", "on");
    await orderInput(wrapper).setValue("10000");
    await submit(wrapper);
    expect(errorText(wrapper)).toBe("表示順は 0 以上 9999 以下の整数で入力してください。");
    expect(calls).toHaveLength(0);
  });

  it("変更では、付いているタイトルと表示順が入る", () => {
    const wrapper = mountEditor(item({ title: "朝の読書灯", display_order: 3 }));
    expect((titleInput(wrapper).element as HTMLInputElement).value).toBe("朝の読書灯");
    expect((orderInput(wrapper).element as HTMLInputElement).value).toBe("3");
  });

  it("変更で、表示順 0 は「付いている」ので、0 と入る（空にならない）", () => {
    const wrapper = mountEditor(item({ title: null, display_order: 0 }));
    expect((orderInput(wrapper).element as HTMLInputElement).value).toBe("0");
    expect((titleInput(wrapper).element as HTMLInputElement).value).toBe("");
  });

  it("変更で、付いていない定期実行（項目が無い応答を含む）は、どちらも空", () => {
    for (const target of [item({ title: null, display_order: null }), item()]) {
      const wrapper = mountEditor(target);
      expect((titleInput(wrapper).element as HTMLInputElement).value).toBe("");
      expect((orderInput(wrapper).element as HTMLInputElement).value).toBe("");
    }
  });

  it("変更で、空にして保存すると null を送る（外す）。値を変えると、その値を送る", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(item({ title: "朝", display_order: 3 }));
    await titleInput(wrapper).setValue("");
    await orderInput(wrapper).setValue("");
    await submit(wrapper);
    await flushPromises();
    const cleared = calls[0]!.body as Record<string, unknown>;
    expect(cleared.title).toBeNull();
    expect(cleared.display_order).toBeNull();

    const second = mountEditor(item({ title: "朝", display_order: 3 }));
    await titleInput(second).setValue("夜");
    await orderInput(second).setValue("8");
    await submit(second);
    await flushPromises();
    const changed = calls[1]!.body as Record<string, unknown>;
    expect(changed.title).toBe("夜");
    expect(changed.display_order).toBe(8);
  });

  it("変更で、タイトルと表示順に触れずに保存しても、付いている値をそのまま送る（消さない）", async () => {
    const { calls } = mockApi(okHandler);
    const wrapper = mountEditor(item({ title: "朝", display_order: 3 }));
    await submit(wrapper);
    await flushPromises();
    const body = calls[0]!.body as Record<string, unknown>;
    expect(body.title).toBe("朝");
    expect(body.display_order).toBe(3);
  });
});

describe("タイトルと表示順の補助関数", () => {
  const base = { title: "", displayOrder: "" };

  it("validateTitleAndOrder: 空、1〜50 文字、0〜9999 は問題なし", () => {
    expect(validateTitleAndOrder(base)).toBeNull();
    expect(validateTitleAndOrder({ title: "あ", displayOrder: "0" })).toBeNull();
    expect(validateTitleAndOrder({ title: "x".repeat(50), displayOrder: "9999" })).toBeNull();
    expect(validateTitleAndOrder({ title: "  " + "x".repeat(50) + "  ", displayOrder: "" })).toBeNull(); // 取り除いた長さで見る
  });

  it("validateTitleAndOrder: タイトルが先、表示順が後", () => {
    expect(validateTitleAndOrder({ title: "x".repeat(51), displayOrder: "-1" })).toBe(
      "タイトルは 50 文字以内で入力してください。",
    );
    expect(validateTitleAndOrder({ title: "x", displayOrder: "-1" })).toBe(
      "表示順は 0 以上 9999 以下の整数で入力してください。",
    );
  });

  it("formFromItem: 新規は、タイトルも表示順も空", () => {
    const form = formFromItem(null);
    expect(form.title).toBe("");
    expect(form.displayOrder).toBe("");
  });

  it("toScheduleBody: 常に title と display_order を持つ（空は null）", () => {
    const form: ScheduleForm = { ...emptyForm, condition: "daily", time: "07:00", actionType: "scene", scene: "out" };
    expect(toScheduleBody(form)).toMatchObject({ title: null, display_order: null });
    expect(toScheduleBody({ ...form, title: " 朝 ", displayOrder: " 4 " })).toMatchObject({
      title: "朝",
      display_order: 4,
    });
  });
});
