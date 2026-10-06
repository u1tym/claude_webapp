import { mount, type VueWrapper } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RoomDiagram from "../src/components/RoomDiagram.vue";
import type { DeviceKey, DeviceState, Devices } from "../src/room";

function devices(override: Partial<Devices> = {}): Devices {
  return {
    ceiling_light: { status: "ok", state: "off" },
    indirect_light: { status: "ok", state: "on" },
    indoor_speaker: { status: "ok", state: "off" },
    bedside_speaker: { status: "ok", state: "off" },
    front_door: { status: "ok", state: "locked", battery: 35 },
    ...override,
  };
}

const ERROR: DeviceState = { status: "error", state: null };

function render(
  props: { devices?: Devices; switching?: DeviceKey | null; disabled?: boolean } = {},
): VueWrapper {
  return mount(RoomDiagram, { props: { devices: props.devices ?? devices(), ...props } });
}

const part = (wrapper: VueWrapper, key: DeviceKey) => wrapper.get(`[data-device="${key}"]`);

describe("表示", () => {
  it("5 機器のパーツと、機器名・状態の文言を表示する", () => {
    const wrapper = render();
    const texts: Record<DeviceKey, [string, string]> = {
      ceiling_light: ["電灯", "OFF"],
      indirect_light: ["間接照明", "ON"],
      indoor_speaker: ["屋内スピーカー", "OFF"],
      bedside_speaker: ["枕元スピーカー", "OFF"],
      front_door: ["玄関ドア", "施錠中"],
    };
    for (const [key, [label, state]] of Object.entries(texts) as [DeviceKey, [string, string]][]) {
      const text = part(wrapper, key).text();
      expect(text).toContain(label);
      expect(text).toContain(state);
    }
    expect(wrapper.findAll("[data-device]")).toHaveLength(5);
  });

  it("状態は色だけでなく形（塗り・光線・音波）と文言でも区別する", () => {
    const on = render({
      devices: devices({
        indirect_light: { status: "ok", state: "on" },
        indoor_speaker: { status: "ok", state: "on" },
      }),
    });
    const off = render();

    // ON: 光線・音波の記号が描かれ、is-on が付く
    expect(part(on, "indirect_light").classes()).toContain("is-on");
    expect(part(on, "indirect_light").find(".rd-rays").exists()).toBe(true);
    expect(part(on, "indoor_speaker").classes()).toContain("is-on");
    expect(part(on, "indoor_speaker").find(".rd-waves").exists()).toBe(true);
    // OFF: 記号なし（輪郭のみ）
    expect(part(off, "indoor_speaker").classes()).not.toContain("is-on");
    expect(part(off, "indoor_speaker").find(".rd-waves").exists()).toBe(false);
    expect(part(off, "indoor_speaker").text()).toContain("OFF");
    expect(part(on, "indoor_speaker").text()).toContain("ON");
  });

  it("玄関ドアは施錠中と開錠中で錠の形と文言が変わる", () => {
    const locked = render();
    const unlocked = render({
      devices: devices({ front_door: { status: "ok", state: "unlocked", battery: 35 } }),
    });
    const shackle = (w: VueWrapper) => part(w, "front_door").get(".rd-shackle").attributes("d");
    expect(part(locked, "front_door").text()).toContain("施錠中");
    expect(part(unlocked, "front_door").text()).toContain("開錠中");
    expect(shackle(locked)).not.toBe(shackle(unlocked));
    expect(part(locked, "front_door").classes()).toContain("is-on");
    expect(part(unlocked, "front_door").classes()).not.toContain("is-on");
  });

  it("電灯は ON / OFF を状態どおりに示し、未実装の文言を出さない", () => {
    const off = render();
    expect(part(off, "ceiling_light").text()).toContain("OFF");
    expect(part(off, "ceiling_light").text()).not.toContain("未実装");
    expect(part(off, "ceiling_light").classes()).not.toContain("is-on");
    expect(part(off, "ceiling_light").find(".rd-rays").exists()).toBe(false);

    const on = render({ devices: devices({ ceiling_light: { status: "ok", state: "on" } }) });
    expect(part(on, "ceiling_light").text()).toContain("ON");
    expect(part(on, "ceiling_light").text()).not.toContain("未実装");
    expect(part(on, "ceiling_light").classes()).toContain("is-on");
    expect(part(on, "ceiling_light").find(".rd-rays").exists()).toBe(true);
  });

  it("電灯の明るさと色温度は表示しない", () => {
    const wrapper = render({ devices: devices({ ceiling_light: { status: "ok", state: "on" } }) });
    const text = part(wrapper, "ceiling_light").text();
    expect(text).not.toMatch(/明るさ|色温度|%|K/);
  });

  it("電池残量を割合と塗りで示す", () => {
    const wrapper = render();
    const battery = wrapper.get('[data-part="battery"]');
    expect(battery.text()).toContain("35%");
    expect(battery.attributes("aria-label")).toBe("玄関ドアの電池残量 35%");
    // 満タン 90 に対して 35%（枠の内側 3px ずつを除く）
    const fill = Number(wrapper.get('[data-testid="battery-fill"]').attributes("width"));
    expect(fill).toBe(Math.round((90 * 35) / 100) - 6);

    const full = render({
      devices: devices({ front_door: { status: "ok", state: "locked", battery: 100 } }),
    });
    expect(Number(full.get('[data-testid="battery-fill"]').attributes("width"))).toBe(90 - 6);
    const empty = render({
      devices: devices({ front_door: { status: "ok", state: "locked", battery: 0 } }),
    });
    expect(Number(empty.get('[data-testid="battery-fill"]').attributes("width"))).toBe(0);
  });

  it("電池残量が取れないときは「不明」", () => {
    const wrapper = render({
      devices: devices({ front_door: { status: "ok", state: "locked", battery: null } }),
    });
    expect(wrapper.get('[data-part="battery"]').text()).toContain("不明");
    expect(wrapper.get('[data-part="battery"]').attributes("aria-label")).toBe(
      "玄関ドアの電池残量 不明",
    );
  });
});

describe("取得できなかった機器", () => {
  it("「取得できません」と警告の記号を示し、他の機器は妨げない", () => {
    const wrapper = render({ devices: devices({ indoor_speaker: ERROR }) });
    const broken = part(wrapper, "indoor_speaker");
    expect(broken.text()).toContain("⚠ 取得できません");
    expect(broken.classes()).toContain("is-error");
    expect(part(wrapper, "indirect_light").text()).toContain("ON");
    expect(part(wrapper, "indirect_light").classes()).not.toContain("is-error");
  });

  it("切り替えられない（押しても何も起きず、フォーカスもできない）", async () => {
    const wrapper = render({ devices: devices({ indoor_speaker: ERROR }) });
    const broken = part(wrapper, "indoor_speaker");
    expect(broken.attributes("aria-disabled")).toBe("true");
    expect(broken.attributes("tabindex")).toBe("-1");
    expect(broken.attributes("aria-label")).toBe("屋内スピーカー 取得できません");
    await broken.trigger("click");
    await broken.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("玄関ドアが取得できないときは電池残量も「不明」で、操作できない", async () => {
    const wrapper = render({ devices: devices({ front_door: ERROR }) });
    expect(wrapper.get('[data-part="battery"]').text()).toContain("不明");
    await part(wrapper, "front_door").trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();
  });
});

describe("操作", () => {
  const operable: DeviceKey[] = ["indirect_light", "indoor_speaker", "bedside_speaker", "front_door"];

  it.each(operable)("%s はボタンとして振る舞い、クリックで select を出す", async (key) => {
    const wrapper = render();
    const target = part(wrapper, key);
    expect(target.attributes("role")).toBe("button");
    expect(target.attributes("tabindex")).toBe("0");
    expect(target.attributes("aria-disabled")).toBe("false");
    await target.trigger("click");
    expect(wrapper.emitted("select")).toEqual([[key]]);
  });

  it.each(operable)("%s は Enter と Space でも操作できる", async (key) => {
    const wrapper = render();
    await part(wrapper, key).trigger("keydown", { key: "Enter" });
    await part(wrapper, key).trigger("keydown", { key: " " });
    expect(wrapper.emitted("select")).toEqual([[key], [key]]);
  });

  it("他のキーでは操作できない", async () => {
    const wrapper = render();
    await part(wrapper, "indirect_light").trigger("keydown", { key: "a" });
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("電灯はボタンで、操作すると選択を伝える（調光パターンは親が選ばせる）", async () => {
    const wrapper = render();
    const ceiling = part(wrapper, "ceiling_light");
    expect(ceiling.attributes("role")).toBe("button");
    expect(ceiling.attributes("tabindex")).toBe("0");
    expect(ceiling.attributes("aria-label")).toBe("電灯 OFF。押すと調光パターンを選んで点灯します");
    await ceiling.trigger("click");
    await ceiling.trigger("keydown", { key: "Enter" });
    await ceiling.trigger("keydown", { key: " " });
    expect(wrapper.emitted("select")).toEqual([["ceiling_light"], ["ceiling_light"], ["ceiling_light"]]);
  });

  it("点灯中の電灯の aria-label は、調光パターンの変更または消灯ができることを示す", () => {
    const wrapper = render({ devices: devices({ ceiling_light: { status: "ok", state: "on" } }) });
    expect(part(wrapper, "ceiling_light").attributes("aria-label")).toBe(
      "電灯 ON。押すと調光パターンの変更または消灯ができます",
    );
  });

  it("取得できなかった電灯は操作できない", async () => {
    const wrapper = render({ devices: devices({ ceiling_light: ERROR }) });
    const ceiling = part(wrapper, "ceiling_light");
    expect(ceiling.attributes("aria-disabled")).toBe("true");
    expect(ceiling.attributes("tabindex")).toBe("-1");
    await ceiling.trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("電池残量は操作しても何も起きない", async () => {
    const wrapper = render();
    const battery = wrapper.get('[data-part="battery"]');
    expect(battery.attributes("role")).toBe("img");
    expect(battery.attributes("tabindex")).toBeUndefined();
    await battery.trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("操作できるパーツの aria-label は、機器名・現在の状態・押したときの結果を示す", () => {
    const wrapper = render();
    expect(part(wrapper, "indirect_light").attributes("aria-label")).toBe(
      "間接照明 ON。押すと OFF にします",
    );
    expect(part(wrapper, "front_door").attributes("aria-label")).toBe(
      "玄関ドア 施錠中。押すと開錠の確認を開きます",
    );
  });

  it("タップ領域は、スマートフォン幅（約 0.5 倍）でも 44px 以上になる大きさ", () => {
    const wrapper = render();
    for (const key of operable) {
      const hit = part(wrapper, key).get(".rd-hit");
      expect(Number(hit.attributes("width"))).toBeGreaterThanOrEqual(88);
      expect(Number(hit.attributes("height"))).toBeGreaterThanOrEqual(88);
    }
  });
});

describe("切替中・取得中", () => {
  it("切替中のパーツは「切替中…」を示し、すべてのパーツを操作できない", async () => {
    const wrapper = render({ switching: "indirect_light" });
    expect(part(wrapper, "indirect_light").text()).toContain("切替中…");
    expect(part(wrapper, "indirect_light").classes()).toContain("is-switching");
    for (const key of ["indirect_light", "indoor_speaker", "bedside_speaker", "front_door"] as const) {
      expect(part(wrapper, key).attributes("aria-disabled")).toBe("true");
      await part(wrapper, key).trigger("click");
    }
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("disabled の間は、どのパーツも操作できない", async () => {
    const wrapper = render({ disabled: true });
    for (const key of ["indirect_light", "front_door"] as const) {
      expect(part(wrapper, key).attributes("aria-disabled")).toBe("true");
      await part(wrapper, key).trigger("click");
      await part(wrapper, key).trigger("keydown", { key: "Enter" });
    }
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("操作できない間も、状態の文言は読める", () => {
    const wrapper = render({ disabled: true });
    expect(part(wrapper, "indirect_light").text()).toContain("ON");
    expect(part(wrapper, "front_door").text()).toContain("施錠中");
  });
});

describe("アクセシビリティ", () => {
  it("図全体にラベルがあり、飾りは読み上げの対象にしない", () => {
    const wrapper = render();
    expect(wrapper.get("svg").attributes("aria-label")).toBe("部屋の図");
    expect(wrapper.get(".rd-wall").attributes("aria-hidden")).toBe("true");
  });
});

/** パーツの位置（translate(x y)）を読む。 */
function positionOf(wrapper: VueWrapper, selector: string): { x: number; y: number } {
  const match = /translate\(([\d.]+) ([\d.]+)\)/.exec(wrapper.get(selector).attributes("transform") ?? "");
  expect(match, selector).not.toBeNull();
  return { x: Number(match![1]), y: Number(match![2]) };
}

describe("配置（2 列 × 3 行）", () => {
  //   電灯            間接照明
  //   屋内スピーカー  枕元スピーカー
  //   玄関ドア        電池残量
  it("左の列に 電灯・屋内スピーカー・玄関ドア、右の列に 間接照明・枕元スピーカー・電池残量が並ぶ", () => {
    const wrapper = render();
    const at = (key: DeviceKey) => positionOf(wrapper, `[data-device="${key}"]`);
    const battery = positionOf(wrapper, '[data-part="battery"]');

    // 左の列: 同じ x
    expect(at("ceiling_light").x).toBe(at("indoor_speaker").x);
    expect(at("indoor_speaker").x).toBe(at("front_door").x);
    // 右の列: 間接照明と枕元スピーカーは同じ x。電池残量の中心も、同じ列の中心にそろう
    expect(at("indirect_light").x).toBe(at("bedside_speaker").x);
    expect(at("indirect_light").x).toBeGreaterThan(at("ceiling_light").x);
    // 行: 同じ行は同じ y。上から 電灯・間接照明 → 屋内・枕元 → 玄関ドア・電池残量
    expect(at("ceiling_light").y).toBe(at("indirect_light").y);
    expect(at("indoor_speaker").y).toBe(at("bedside_speaker").y);
    expect(at("ceiling_light").y).toBeLessThan(at("indoor_speaker").y);
    expect(at("indoor_speaker").y).toBeLessThan(at("front_door").y);
    // 電池残量は、玄関ドアと同じ行（ゲージの位置は、行の上端からの少しの下がり）
    expect(battery.y).toBeGreaterThanOrEqual(at("front_door").y);
    expect(battery.y).toBeLessThan(at("front_door").y + 60);
    expect(battery.x).toBeGreaterThan(at("front_door").x + 150);
    // 電池残量の文字の中心（ゲージの左端 + 45）が、右の列のパーツの中心（x + 75）にそろう
    expect(battery.x + 45).toBe(at("indirect_light").x + 75);
  });

  it("DOM の順（読み上げ・キーボードのフォーカスの順）も、左 → 右、上 → 下", () => {
    const wrapper = render();
    const order = wrapper.findAll("[data-device]").map((g) => g.attributes("data-device"));
    expect(order).toEqual([
      "ceiling_light",
      "indirect_light",
      "indoor_speaker",
      "bedside_speaker",
      "front_door",
    ]);
    // 電池残量は、その後ろ
    const all = wrapper.findAll("[data-device], [data-part='battery']").map(
      (g) => g.attributes("data-device") ?? g.attributes("data-part"),
    );
    expect(all.at(-1)).toBe("battery");
  });

  it("5 つのパーツと電池残量が、重ならない", () => {
    const wrapper = render();
    const boxes = [
      ...(["ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker", "front_door"] as const).map(
        (key) => {
          const { x, y } = positionOf(wrapper, `[data-device="${key}"]`);
          const hit = wrapper.get(`[data-device="${key}"] .rd-hit`);
          return { key, x, y, w: Number(hit.attributes("width")), h: Number(hit.attributes("height")) };
        },
      ),
      { key: "battery", ...positionOf(wrapper, '[data-part="battery"]'), w: 97, h: 100 },
    ];
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i]!;
        const b = boxes[j]!;
        const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
        expect(overlap, `${a.key} と ${b.key}`).toBe(false);
      }
    }
  });

  it("全パーツが、壁の内側に収まる", () => {
    const wrapper = render();
    const wall = wrapper.get(".rd-wall");
    const [wx, wy, ww, wh] = ["x", "y", "width", "height"].map((a) => Number(wall.attributes(a)));
    for (const key of ["ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker", "front_door"] as const) {
      const { x, y } = positionOf(wrapper, `[data-device="${key}"]`);
      const hit = wrapper.get(`[data-device="${key}"] .rd-hit`);
      expect(x).toBeGreaterThan(wx!);
      expect(x + Number(hit.attributes("width"))).toBeLessThan(wx! + ww!);
      expect(y).toBeGreaterThan(wy!);
      expect(y + Number(hit.attributes("height"))).toBeLessThanOrEqual(wy! + wh!);
    }
  });

  it("ベッドと、玄関の切れ目は描かない（飾りは、壁だけ）", () => {
    const wrapper = render();
    expect(wrapper.find(".rd-bed").exists()).toBe(false);
    expect(wrapper.find(".rd-door-gap").exists()).toBe(false);
    // 壁の外の、読み上げの対象にならない図形は、壁（rd-wall）だけ
    expect(wrapper.findAll('[aria-hidden="true"]:not(.icon)').map((e) => e.classes()[0])).toEqual(["rd-wall"]);
  });
});
