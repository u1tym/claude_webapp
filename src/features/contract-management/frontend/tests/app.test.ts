import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.vue";
import { AuthError } from "../src/api/client";
import { createAppRouter } from "../src/router";

const navigateTo = vi.fn();
vi.mock("../src/navigation", () => ({ navigateTo: (url: string) => navigateTo(url) }));

const SETTINGS = {
  login_url: "https://host/portal/login",
  menu_url: "https://host/portal/menu",
  icon_system: "data:image/png;base64,AAAA",
  icon_back: "",
};

function stubFetch(settingsStatus = 200): void {
  // 設定（/settings）以外は、画面が呼ぶ API。ここでは、空の一覧を返す
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).endsWith("/settings")) {
        return new Response(settingsStatus === 200 ? JSON.stringify(SETTINGS) : null, { status: settingsStatus });
      }
      return new Response(JSON.stringify({ total: 0, items: [] }), { status: 200 });
    }),
  );
}

async function mountApp(path = "/") {
  const router = createAppRouter(createMemoryHistory("/portal_contract_management/"));
  await router.push(path);
  await router.isReady();
  const wrapper = mount(App, { global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

beforeEach(() => navigateTo.mockClear());
afterEach(() => vi.unstubAllGlobals());

describe("殻", () => {
  it("設定の取得中は「読み込み中…」を出す", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    const router = createAppRouter(createMemoryHistory());
    await router.push("/");
    const wrapper = mount(App, { global: { plugins: [router] } });
    expect(wrapper.text()).toContain("読み込み中…");
  });

  it("ナビは 4 項目をこの順に常時表示し、現在地に aria-current が付く", async () => {
    stubFetch();
    const { wrapper } = await mountApp("/contracts");
    const items = wrapper.findAll(".nav-item");
    expect(items.map((i) => i.text())).toEqual(["アカウント一覧", "契約一覧", "区分", "解約順"]);
    expect(items.map((i) => i.attributes("href"))).toEqual([
      "/portal_contract_management/",
      "/portal_contract_management/contracts",
      "/portal_contract_management/categories",
      "/portal_contract_management/cancellation",
    ]);
    expect(items.filter((i) => i.attributes("aria-current") === "page").map((i) => i.text())).toEqual(["契約一覧"]);
    expect(wrapper.find("nav").attributes("aria-label")).toBe("ナビゲーション");
  });

  it("本機能を開くと、アカウント一覧を表示する。ヘッダの題は画面ごとに変わる", async () => {
    stubFetch();
    const { wrapper, router } = await mountApp("/");
    expect(wrapper.get(".header-title").text()).toBe("アカウント一覧");
    // 基点では、アカウント一覧の画面（検索欄がある）を表示する
    expect(wrapper.find('.content input[aria-label="検索"]').exists()).toBe(true);
    await router.push("/cancellation");
    await flushPromises();
    expect(wrapper.get(".header-title").text()).toBe("解約順");
    expect(wrapper.get(".header-icon").attributes("src")).toBe(SETTINGS.icon_system);
  });

  it("「戻る」はメニュー画面 URL へ移る（aria-label 付きのアイコンボタン）", async () => {
    stubFetch();
    const { wrapper } = await mountApp();
    const back = wrapper.get('[aria-label="戻る"]');
    expect(back.find("svg.icon").exists()).toBe(true);
    await back.trigger("click");
    expect(navigateTo).toHaveBeenCalledWith(SETTINGS.menu_url);
  });

  it("未ログイン（401）の通知で、ログイン画面 URL へ誘導する", async () => {
    stubFetch();
    const { wrapper } = await mountApp();
    wrapper.findComponent({ name: "RouterView" }).vm.$emit("auth-error", new AuthError(401));
    await flushPromises();
    expect(navigateTo).toHaveBeenCalledWith(SETTINGS.login_url);
  });

  it("権限なし（403）の通知で、「この機能は利用できません」を出す。他のエラーは無視する", async () => {
    stubFetch();
    const { wrapper } = await mountApp();
    wrapper.findComponent({ name: "RouterView" }).vm.$emit("auth-error", new Error("other"));
    await flushPromises();
    expect(wrapper.text()).not.toContain("この機能は利用できません");
    wrapper.findComponent({ name: "RouterView" }).vm.$emit("auth-error", new AuthError(403));
    await flushPromises();
    expect(wrapper.text()).toContain("この機能は利用できません");
    expect(navigateTo).not.toHaveBeenCalled();
    await wrapper.get('main [aria-label="戻る"]').trigger("click");
    expect(navigateTo).toHaveBeenCalledWith(SETTINGS.menu_url);
  });

  it("設定を取得できないときは、内部理由を含まない一文を出す", async () => {
    stubFetch(500);
    const { wrapper } = await mountApp();
    expect(wrapper.get('[role="alert"]').text()).toBe("サーバエラーです");
    expect(wrapper.find(".shell").exists()).toBe(false);
  });
});
