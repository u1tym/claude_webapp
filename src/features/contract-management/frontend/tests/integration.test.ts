// 実際の API クライアントと、殻・ルータ・各画面をつないだ結合テスト（API だけを fetch の代役にする）。
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.vue";
import { createAppRouter } from "../src/router";
import { SECRET_PASSWORD, installFakeApi, type RequestRecord } from "./support/fakeApi";

let log: RequestRecord[];
let clipboard: string[];

async function mountApp(path = "/") {
  const router = createAppRouter(createMemoryHistory("/portal_contract_management/"));
  await router.push(path);
  await router.isReady();
  const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body });
  await flushPromises();
  return { wrapper, router };
}

const passwordRequests = () => log.filter((r) => r.path.endsWith("/password"));

beforeEach(() => {
  log = installFakeApi();
  clipboard = [];
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(async (text: string) => void clipboard.push(text)) },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  document.body.innerHTML = "";
});

describe("結合: アカウント一覧", () => {
  it("開いた直後は、設定と一覧だけを取得する。パスワードは取得せず、画面にも出ない", async () => {
    const { wrapper } = await mountApp("/");
    expect(log.map((r) => `${r.method} ${r.path}`)).toEqual(["GET /settings", "GET /accounts"]);
    expect(wrapper.findAll(".list-row")).toHaveLength(2);
    expect(wrapper.html()).not.toContain(SECRET_PASSWORD);
    expect(passwordRequests()).toHaveLength(0);
    wrapper.unmount();
  });

  it("「表示」「コピー」を操作した時点で、その契約のパスワードだけを取得する（Cookie を送る）", async () => {
    const { wrapper } = await mountApp("/");
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(passwordRequests()).toEqual([
      { method: "GET", path: "/contracts/1/password", body: undefined, credentials: "include" },
    ]);
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe(SECRET_PASSWORD);
    await wrapper.get('[aria-label="パスワードを隠す"]').trigger("click");
    expect(wrapper.html()).not.toContain(SECRET_PASSWORD);
    await wrapper.get('[aria-label="パスワードをコピー"]').trigger("click");
    await flushPromises();
    expect(clipboard).toEqual([SECRET_PASSWORD]);
    expect(passwordRequests()).toHaveLength(2);
    wrapper.unmount();
  });

  it("すべての要求で、Cookie を送る", async () => {
    const { wrapper } = await mountApp("/");
    expect(log.every((r) => r.credentials === "include")).toBe(true);
    wrapper.unmount();
  });
});

describe("結合: 契約一覧", () => {
  it("一覧・詳細・編集フォームを開く間、パスワードを取得しない。パスワードを入力しなければ、更新の本文に password が無い", async () => {
    const { wrapper } = await mountApp("/contracts");
    expect(wrapper.findAll(".list-row")).toHaveLength(2);
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    expect(wrapper.get('[role="dialog"]').attributes("aria-label")).toBe("動画の詳細");
    await wrapper.get('[aria-label="編集"]').trigger("click");
    await flushPromises();
    expect(passwordRequests()).toHaveLength(0);
    log.length = 0;
    await wrapper.get('[aria-label="名称"]').setValue("動画サービス");
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    const patch = log.find((r) => r.method === "PATCH");
    expect(patch?.path).toBe("/contracts/1");
    expect(patch?.body).toMatchObject({ name: "動画サービス", has_contract: true, category_id: 1 });
    expect(patch?.body).not.toHaveProperty("password");
    expect(passwordRequests()).toHaveLength(0);
    expect(wrapper.get('[role="status"]').text()).toBe("更新しました");
    wrapper.unmount();
  });

  it("新規登録の本文は、入力したパスワードを含む（名称だけなら含まない）", async () => {
    const { wrapper } = await mountApp("/contracts");
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    await wrapper.get('[aria-label="名称"]').setValue("新規");
    await wrapper.get('[aria-label="パスワード"]').setValue("typed-pass");
    log.length = 0;
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    const post = log.find((r) => r.method === "POST");
    expect(post?.path).toBe("/contracts");
    expect(post?.body).toMatchObject({ name: "新規", password: "typed-pass" });
    wrapper.unmount();
  });
});

describe("結合: 解約順", () => {
  it("取得・候補・保存の要求を、API の契約どおりに送る", async () => {
    const { wrapper } = await mountApp("/cancellation");
    expect(log.map((r) => `${r.method} ${r.path}`)).toEqual(
      expect.arrayContaining(["GET /cancellation-plan", "GET /cancellation-plan/candidates", "GET /contracts"]),
    );
    await wrapper.get('[aria-label="音楽を解約順に加える"]').trigger("click");
    log.length = 0;
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(log[0]).toMatchObject({ method: "PUT", path: "/cancellation-plan", body: { contract_ids: [1, 2] }, credentials: "include" });
    wrapper.unmount();
  });
});

describe("結合: ナビ", () => {
  it("ナビで 4 つの画面を行き来できる（ヘッダの題が変わる）", async () => {
    const { wrapper } = await mountApp("/");
    for (const [label, title] of [
      ["契約一覧", "契約一覧"],
      ["区分", "区分"],
      ["解約順", "解約順"],
      ["アカウント一覧", "アカウント一覧"],
    ] as const) {
      await wrapper.findAll(".nav-item").find((a) => a.text() === label)?.trigger("click");
      await flushPromises();
      expect(wrapper.get(".header-title").text()).toBe(title);
    }
    wrapper.unmount();
  });
});
