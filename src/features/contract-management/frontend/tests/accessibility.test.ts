// アクセシビリティの確認（rules/15-ui-style.md）: アイコンのみのボタンに aria-label、入力欄にラベル、ダイアログに名前。
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "../src/App.vue";
import { createAppRouter } from "../src/router";
import { installFakeApi } from "./support/fakeApi";

async function mountApp(path: string) {
  const router = createAppRouter(createMemoryHistory("/portal_contract_management/"));
  await router.push(path);
  await router.isReady();
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body });
  await flushPromises();
  return wrapper;
}

/** 操作できる部品の、名前が無いものを返す。 */
function unnamed(root: Element): string[] {
  const problems: string[] = [];
  for (const button of root.querySelectorAll("button")) {
    const name = (button.getAttribute("aria-label") ?? button.textContent ?? "").trim();
    if (name === "") {
      problems.push(`button: ${button.outerHTML.slice(0, 80)}`);
    }
  }
  for (const control of root.querySelectorAll("input, select, textarea")) {
    const input = control as HTMLInputElement;
    if (input.type === "hidden") {
      continue;
    }
    const labelled = input.getAttribute("aria-label") !== null || input.closest("label")?.textContent?.trim();
    if (!labelled) {
      problems.push(`${control.tagName.toLowerCase()}: ${control.outerHTML.slice(0, 80)}`);
    }
  }
  for (const dialog of root.querySelectorAll('[role="dialog"]')) {
    if (!dialog.getAttribute("aria-label")) {
      problems.push("dialog without aria-label");
    }
  }
  for (const icon of root.querySelectorAll("svg.icon")) {
    if (icon.getAttribute("aria-hidden") !== "true") {
      problems.push("icon exposed to assistive technology");
    }
  }
  return problems;
}

let wrapper: VueWrapper | null = null;

beforeEach(() => {
  installFakeApi();
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
  document.body.innerHTML = "";
});

describe("操作できる部品に名前がある", () => {
  it("アカウント一覧", async () => {
    wrapper = await mountApp("/");
    expect(unnamed(document.body)).toEqual([]);
  });

  it("契約一覧・詳細・登録フォーム・削除の確認", async () => {
    wrapper = await mountApp("/contracts");
    expect(unnamed(document.body)).toEqual([]);
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    expect(unnamed(document.body)).toEqual([]);
    await wrapper.get('[aria-label="削除"]').trigger("click");
    expect(unnamed(document.body)).toEqual([]);
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    expect(unnamed(document.body)).toEqual([]);
    await wrapper.get('[aria-label="ステータス"]').setValue("cancelled");
    await wrapper.get('[aria-label="契約日の精度"]').setValue("day");
    expect(unnamed(document.body)).toEqual([]);
  });

  it("区分（編集中を含む）", async () => {
    wrapper = await mountApp("/categories");
    await flushPromises();
    expect(unnamed(document.body)).toEqual([]);
    await wrapper.get('[aria-label="銀行を編集"]').trigger("click");
    expect(unnamed(document.body)).toEqual([]);
  });

  it("解約順", async () => {
    wrapper = await mountApp("/cancellation");
    expect(unnamed(document.body)).toEqual([]);
  });

  it("殻（ヘッダの戻る・ナビ）", async () => {
    wrapper = await mountApp("/");
    expect(unnamed(wrapper.get(".header").element)).toEqual([]);
    expect(wrapper.get("nav").attributes("aria-label")).toBe("ナビゲーション");
  });
});

describe("キーボード操作", () => {
  it("ダイアログを開くと、フォーカスがダイアログ内に移る（詳細: 閉じる、フォーム: 名称、確認: キャンセル）", async () => {
    wrapper = await mountApp("/contracts");
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    await flushPromises();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("閉じる");
    await wrapper.get('[aria-label="削除"]').trigger("click");
    await flushPromises();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("キャンセル");
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("名称");
  });
});
