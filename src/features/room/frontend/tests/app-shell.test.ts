import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { createMemoryHistory, createRouter, type RouteRecordRaw } from "vue-router";
import App from "../src/App.vue";
import { AuthError, apiUrl } from "../src/api";
import * as navigation from "../src/navigation";

const settings = {
  login_url: "http://localhost/login",
  menu_url: "http://localhost/menu",
  icon_system: "data:image/png;base64,AAAA",
  icon_back: "data:image/png;base64,BBBB",
};

const Plain = (text: string) => defineComponent({ emits: ["auth-error"], render: () => h("p", text) });

/** マウント時に認証の失敗を親へ伝える子の画面 */
const failing = (status: 401 | 403) =>
  defineComponent({
    emits: ["auth-error"],
    mounted() {
      this.$emit("auth-error", new AuthError(status));
    },
    render: () => h("p", "子の画面"),
  });

function stubSettings(ok = true) {
  const fetchMock = vi.fn().mockImplementation(async () =>
    ok ? { ok: true, status: 200, json: async () => settings } : { ok: false, status: 500 },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function mountApp(
  routes?: RouteRecordRaw[],
  path = "/",
): Promise<{ wrapper: VueWrapper; router: ReturnType<typeof createRouter> }> {
  const defaults: RouteRecordRaw[] = [
    { path: "/", component: Plain("ROOM の中身"), meta: { title: "ROOM" } },
    { path: "/schedules", component: Plain("定期実行の中身"), meta: { title: "定期実行" } },
  ];
  // ナビの「定期実行」のリンク先が無いと警告が出るため、指定のルートに足りないものを補う
  const given = routes ?? defaults;
  const merged = [...given, ...defaults.filter((d) => !given.some((g) => g.path === d.path))];
  const router = createRouter({ history: createMemoryHistory(), routes: merged });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(App, { global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

let navigateSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  navigateSpy = vi.spyOn(navigation, "navigateTo").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("殻（ヘッダとナビ）", () => {
  it("設定を取得して、ヘッダ（戻る、見出し、システムアイコン）とナビを表示する", async () => {
    const fetchMock = stubSettings();
    const { wrapper } = await mountApp();

    expect(fetchMock.mock.calls[0]?.[0]).toBe(apiUrl("/settings"));
    const header = wrapper.get("header.header");
    expect(header.get("h1").text()).toBe("ROOM");
    expect(header.get("button").attributes("aria-label")).toBe("戻る");
    expect(header.get("img.header-icon").attributes("src")).toBe(settings.icon_system);
    expect(header.get("img.header-icon").attributes("alt")).toBe("");

    const nav = wrapper.get("nav");
    expect(nav.attributes("aria-label")).toBe("ナビゲーション");
    expect(nav.findAll("a").map((a) => a.text())).toEqual(["ROOM", "定期実行"]);
    expect(wrapper.get("main").text()).toContain("ROOM の中身");
  });

  it("読み込み中は殻を出さず、「読み込み中…」を示す", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(new Promise((r) => (resolve = r))),
    );
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/", component: Plain("x"), meta: { title: "ROOM" } },
        { path: "/schedules", component: Plain("y"), meta: { title: "定期実行" } },
      ],
    });
    await router.push("/");
    const wrapper = mount(App, { global: { plugins: [router] } });
    expect(wrapper.text()).toContain("読み込み中…");
    expect(wrapper.find("header").exists()).toBe(false);

    resolve({ ok: true, status: 200, json: async () => settings });
    await flushPromises();
    expect(wrapper.find("header").exists()).toBe(true);
  });

  it("現在地のナビに aria-current が付き、見出しが画面名になる", async () => {
    stubSettings();
    const { wrapper } = await mountApp(undefined, "/schedules");

    expect(wrapper.get("h1").text()).toBe("定期実行");
    const current = wrapper.findAll("nav a").filter((a) => a.attributes("aria-current") === "page");
    expect(current.map((a) => a.text())).toEqual(["定期実行"]);
  });

  it("ナビで画面を切り替えられる", async () => {
    stubSettings();
    const { wrapper, router } = await mountApp();

    await wrapper.findAll("nav a")[1]!.trigger("click");
    await flushPromises();

    expect(router.currentRoute.value.path).toBe("/schedules");
    expect(wrapper.get("h1").text()).toBe("定期実行");
    expect(wrapper.get("main").text()).toContain("定期実行の中身");
  });

  it("戻るでメニュー画面（システム設定の URL）へ進む", async () => {
    stubSettings();
    const { wrapper } = await mountApp();
    await wrapper.get("header button").trigger("click");
    expect(navigateSpy).toHaveBeenCalledWith(settings.menu_url);
  });

  it("ナビも画面も 1 つだけ描画する（PC とスマートフォンの違いは CSS で切り替える）", async () => {
    stubSettings();
    const { wrapper } = await mountApp();
    expect(wrapper.findAll("nav")).toHaveLength(1);
    expect(wrapper.findAll("main")).toHaveLength(1);
  });

  it("セッション ID などをブラウザの保存領域に置かない", async () => {
    stubSettings();
    await mountApp();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});

describe("認証の失敗", () => {
  it("未ログイン（401）はログイン画面（システム設定の URL）へ進む", async () => {
    stubSettings();
    await mountApp([{ path: "/", component: failing(401), meta: { title: "ROOM" } }]);
    expect(navigateSpy).toHaveBeenCalledWith(settings.login_url);
  });

  it("権限なし（403）は「この機能は利用できません」と戻る操作だけを示す", async () => {
    stubSettings();
    const { wrapper } = await mountApp([{ path: "/", component: failing(403), meta: { title: "ROOM" } }]);

    expect(wrapper.get("main").text()).toContain("この機能は利用できません");
    // 子の画面の内容は見せない
    expect(wrapper.text()).not.toContain("子の画面");
    expect(navigateSpy).not.toHaveBeenCalled();

    await wrapper.get("main button").trigger("click");
    expect(navigateSpy).toHaveBeenCalledWith(settings.menu_url);
    expect(wrapper.get("main button").attributes("aria-label")).toBe("戻る");
  });

  it("AuthError 以外のエラーでは遷移も表示の切替もしない", async () => {
    stubSettings();
    const other = defineComponent({
      emits: ["auth-error"],
      mounted() {
        this.$emit("auth-error", new Error("other"));
      },
      render: () => h("p", "子の画面"),
    });
    const { wrapper } = await mountApp([{ path: "/", component: other, meta: { title: "ROOM" } }]);
    expect(navigateSpy).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("子の画面");
  });
});

describe("設定の取得に失敗したとき", () => {
  it("内部理由を出さず「サーバエラーです」だけを示し、殻は出さない", async () => {
    stubSettings(false);
    const { wrapper } = await mountApp();
    expect(wrapper.get("[role=alert]").text()).toBe("サーバエラーです");
    expect(wrapper.find("header").exists()).toBe(false);
    expect(wrapper.find("nav").exists()).toBe(false);
  });

  it("通信できないときも同じ表示にする", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { wrapper } = await mountApp();
    expect(wrapper.get("[role=alert]").text()).toBe("サーバエラーです");
    expect(wrapper.text()).not.toContain("Failed to fetch");
  });
});
