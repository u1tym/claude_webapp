import { describe, expect, it } from "vitest";
import {
  DEVICE_LABELS,
  ariaLabelFor,
  batteryText,
  isOperable,
  nextState,
  stateText,
  type DeviceState,
} from "../src/room";

const ok = (state: DeviceState["state"], extra: Partial<DeviceState> = {}): DeviceState => ({
  status: "ok",
  state,
  ...extra,
});
const error: DeviceState = { status: "error", state: null };

describe("stateText", () => {
  it("状態を日本語の文言にする", () => {
    expect(stateText(ok("on"))).toBe("ON");
    expect(stateText(ok("off"))).toBe("OFF");
    expect(stateText(ok("locked"))).toBe("施錠中");
    expect(stateText(ok("unlocked"))).toBe("開錠中");
  });

  it("取得できなかった機器は「取得できません」", () => {
    expect(stateText(error)).toBe("取得できません");
    expect(stateText({ status: "ok", state: null })).toBe("取得できません");
  });
});

describe("isOperable / nextState", () => {
  it("5 機器すべてが切り替えられる", () => {
    for (const key of [
      "ceiling_light",
      "indirect_light",
      "indoor_speaker",
      "bedside_speaker",
      "front_door",
    ] as const) {
      expect(isOperable(key)).toBe(true);
    }
  });

  it("ON なら OFF、OFF なら ON が目標になる", () => {
    expect(nextState("indirect_light", ok("on"))).toBe("off");
    expect(nextState("indoor_speaker", ok("off"))).toBe("on");
  });

  it("玄関ドアは施錠中なら開錠、開錠中なら施錠が目標になる", () => {
    expect(nextState("front_door", ok("locked"))).toBe("unlocked");
    expect(nextState("front_door", ok("unlocked"))).toBe("locked");
  });

  it("取得できていないときは目標を決めない（現在の状態が分からないため）", () => {
    expect(nextState("indirect_light", error)).toBeNull();
    expect(nextState("front_door", error)).toBeNull();
  });
});

describe("ariaLabelFor", () => {
  it("機器名、現在の状態、押したときの結果を示す", () => {
    expect(ariaLabelFor("indirect_light", ok("on"))).toBe("間接照明 ON。押すと OFF にします");
    expect(ariaLabelFor("bedside_speaker", ok("off"))).toBe("枕元スピーカー OFF。押すと ON にします");
  });

  it("玄関ドアは、押すと確認を開くことを示す", () => {
    expect(ariaLabelFor("front_door", ok("locked"))).toBe(
      "玄関ドア 施錠中。押すと開錠の確認を開きます",
    );
    expect(ariaLabelFor("front_door", ok("unlocked"))).toBe(
      "玄関ドア 開錠中。押すと施錠の確認を開きます",
    );
  });

  it("電灯は、押すと調光パターンの選択を開くことを示す", () => {
    expect(ariaLabelFor("ceiling_light", ok("off"))).toBe("電灯 OFF。押すと調光パターンを選んで点灯します");
    expect(ariaLabelFor("ceiling_light", ok("on"))).toBe(
      "電灯 ON。押すと調光パターンの変更または消灯ができます",
    );
    expect(ariaLabelFor("ceiling_light", error)).toBe("電灯 取得できません");
  });

  it("取得できない機器はそれだけを示す", () => {
    expect(ariaLabelFor("indoor_speaker", error)).toBe("屋内スピーカー 取得できません");
  });
});

describe("batteryText", () => {
  it("割合か「不明」", () => {
    expect(batteryText(35)).toBe("35%");
    expect(batteryText(0)).toBe("0%");
    expect(batteryText(null)).toBe("不明");
    expect(batteryText(undefined)).toBe("不明");
  });
});

it("機器名は 5 つ", () => {
  expect(Object.values(DEVICE_LABELS)).toEqual([
    "電灯",
    "間接照明",
    "屋内スピーカー",
    "枕元スピーカー",
    "玄関ドア",
  ]);
});
