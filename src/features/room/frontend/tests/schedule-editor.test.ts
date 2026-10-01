import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api";
import ScheduleEditor from "../src/components/ScheduleEditor.vue";
import {
  formFromItem,
  toScheduleBody,
  validateScheduleForm,
  type ScheduleForm,
  type ScheduleItem,
} from "../src/room";
import { deferred, mockApi, res, type Handler } from "./helpers";

function item(override: Partial<ScheduleItem> = {}): ScheduleItem {
  return {
    id: 7,
    condition: "weekdays",
    weekdays: [1, 3],
    run_time: "22:30",
    scene: "out",
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
    await wrapper.get("#schedule-scene").setValue(values.scene);
  }
}

const submit = (w: VueWrapper) => w.get("form").trigger("submit");
const errorText = (w: VueWrapper) => w.find("[role=alert]").text();
const chip = (w: VueWrapper, label: string) => w.get(`[aria-label="${label}曜日"]`);

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("入力フォームの補助関数", () => {
  const valid: ScheduleForm = {
    condition: "daily",
    weekdays: [],
    time: "07:00",
    scene: "out",
    enabled: true,
  };

  it("正しい入力は null（問題なし）", () => {
    expect(validateScheduleForm(valid)).toBeNull();
    expect(validateScheduleForm({ ...valid, condition: "holiday" })).toBeNull();
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
    expect(validateScheduleForm({ ...valid, condition: "holiday", weekdays: [1, 2] })).toBeNull();
  });

  it.each(["", "7:00", "24:00", "12:60", "07:00:30", "abc", "0700", "07-00"])(
    "時刻 %j は形式の誤り",
    (time) => {
      expect(validateScheduleForm({ ...valid, time })).toBe(
        "時刻を HH:MM の形式で入力してください。",
      );
    },
  );

  it("一括切替が未選択", () => {
    expect(validateScheduleForm({ ...valid, scene: "" })).toBe("一括切替を選択してください。");
  });

  it("問題が複数あるときは、最初の 1 件だけを返す（実行条件 → 曜日 → 時刻 → 一括切替の順）", () => {
    expect(validateScheduleForm({ condition: "", weekdays: [], time: "", scene: "", enabled: true })).toBe(
      "実行条件を選択してください。",
    );
    expect(
      validateScheduleForm({ condition: "weekdays", weekdays: [], time: "", scene: "", enabled: true }),
    ).toBe("曜日を 1 つ以上選択してください。");
    expect(
      validateScheduleForm({ condition: "daily", weekdays: [], time: "", scene: "", enabled: true }),
    ).toBe("時刻を HH:MM の形式で入力してください。");
  });

  it("本文は、曜日の指定のときだけ曜日を付け、昇順にする", () => {
    expect(toScheduleBody({ ...valid, condition: "weekdays", weekdays: [5, 1, 3] })).toEqual({
      condition: "weekdays",
      weekdays: [1, 3, 5],
      run_time: "07:00",
      scene: "out",
      is_enabled: true,
    });
    expect(toScheduleBody({ ...valid, condition: "daily", weekdays: [1, 2] }).weekdays).toEqual([]);
    expect(toScheduleBody({ ...valid, condition: "holiday", weekdays: [1, 2] }).weekdays).toEqual([]);
  });

  it("初期値: 新規は空で有効、変更は現在の値（元の配列を共有しない）", () => {
    expect(formFromItem(null)).toEqual({
      condition: "",
      weekdays: [],
      time: "",
      scene: "",
      enabled: true,
    });
    const source = item();
    const form = formFromItem(source);
    expect(form).toEqual({
      condition: "weekdays",
      weekdays: [1, 3],
      time: "22:30",
      scene: "out",
      enabled: false,
    });
    form.weekdays.push(7);
    expect(source.weekdays).toEqual([1, 3]);
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
      "holiday",
    ]);
    expect(radios.every((r) => !(r.element as HTMLInputElement).checked)).toBe(true);
    expect(wrapper.get('[role="switch"]').attributes("aria-checked")).toBe("true");
    expect(wrapper.find(".chips").exists()).toBe(false);
    expect((wrapper.get("#schedule-time").element as HTMLInputElement).value).toBe("");
    expect((wrapper.get("#schedule-scene").element as HTMLSelectElement).value).toBe("");
  });

  it("実行条件の選択肢は「毎日」「曜日の指定」「祝日の指定」", () => {
    const wrapper = mountEditor();
    expect(wrapper.findAll(".editor-radio").map((l) => l.text())).toEqual([
      "毎日",
      "曜日の指定",
      "祝日の指定",
    ]);
  });

  it("一括切替の選択肢は 5 種だけで、玄関ドアの施錠・開錠を含めない", () => {
    const wrapper = mountEditor();
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
    await fill(wrapper, { condition: "holiday" });
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
    [{ condition: "daily", time: "07:00" }, "一括切替を選択してください。"],
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
    ["祝日", { condition: "holiday", time: "09:15", scene: "ceiling_light" }, [], "holiday"],
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
      run_time: "22:30",
      scene: "out",
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
          run_time: "06:45",
          scene: "bedside_speaker",
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
    await fill(wrapper, { condition: "holiday" });
    await submit(wrapper);
    await flushPromises();
    expect(calls[0]!.body).toMatchObject({ condition: "holiday", weekdays: [] });
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
