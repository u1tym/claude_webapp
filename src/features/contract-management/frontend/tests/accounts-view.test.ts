import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api/client";
import type { AccountItem } from "../src/api/types";
import AccountsView from "../src/views/AccountsView.vue";

const listAccounts = vi.fn<(keyword?: string) => Promise<AccountItem[]>>();
const getContractPassword = vi.fn<(id: number) => Promise<string | null>>();

vi.mock("../src/api/contracts", () => ({
  listAccounts: (keyword?: string) => listAccounts(keyword),
  getContractPassword: (id: number) => getContractPassword(id),
}));

let clipboard: string[];

function item(id: number, overrides: Partial<AccountItem> = {}): AccountItem {
  return { id, name: `契約${id}`, username: `user${id}`, homepage: null, has_password: true, password_unset: false, ...overrides };
}

async function mountView(items: AccountItem[] = [item(1), item(2)]) {
  listAccounts.mockResolvedValue(items);
  const wrapper = mount(AccountsView);
  await flushPromises();
  return wrapper;
}

beforeEach(() => {
  clipboard = [];
  listAccounts.mockReset();
  getContractPassword.mockReset();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(async (text: string) => void clipboard.push(text)) },
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("アカウント一覧", () => {
  it("取得中は「読み込み中…」を出し、取得後に名称・ユーザ名を一覧する", async () => {
    let resolve: (value: AccountItem[]) => void = () => undefined;
    listAccounts.mockReturnValue(new Promise((r) => (resolve = r)));
    const wrapper = mount(AccountsView);
    expect(wrapper.text()).toContain("読み込み中…");
    resolve([item(1), item(2)]);
    await flushPromises();
    expect(wrapper.text()).not.toContain("読み込み中…");
    const rows = wrapper.findAll(".list-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.text()).toContain("契約1");
    expect(rows[0]?.text()).toContain("user1");
    expect(listAccounts).toHaveBeenCalledWith("");
  });

  it("ホームページは、http(s) のときだけ新しいタブで開けるリンクにする", async () => {
    const wrapper = await mountView([
      item(1, { homepage: "https://example.com" }),
      item(2, { homepage: "javascript:alert(1)" }),
    ]);
    const links = wrapper.findAll("a");
    expect(links).toHaveLength(1);
    expect(links[0]?.attributes()).toMatchObject({ href: "https://example.com", target: "_blank", rel: "noopener noreferrer" });
    expect(wrapper.html()).not.toContain("javascript:");
  });

  it("パスワードは、一覧の取得でも、描画でも取得せず、マスク表示にする", async () => {
    const wrapper = await mountView();
    expect(getContractPassword).not.toHaveBeenCalled();
    expect(wrapper.findAll('[data-testid="password-value"]').map((e) => e.text())).toEqual(["••••••••", "••••••••"]);
  });

  it("「表示」で、その行のパスワードだけを取得して表示する。「隠す」で戻す", async () => {
    getContractPassword.mockResolvedValue("S3cret-Pass");
    const wrapper = await mountView();
    const rows = wrapper.findAll(".list-row");
    await rows[1]?.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(getContractPassword).toHaveBeenCalledTimes(1);
    expect(getContractPassword).toHaveBeenCalledWith(2);
    expect(rows[1]?.get('[data-testid="password-value"]').text()).toBe("S3cret-Pass");
    expect(rows[0]?.get('[data-testid="password-value"]').text()).toBe("••••••••");
    await rows[1]?.get('[aria-label="パスワードを隠す"]').trigger("click");
    expect(wrapper.html()).not.toContain("S3cret-Pass");
  });

  it("ユーザ名とパスワードをコピーできる（パスワードは、マスク中でもコピーできる）", async () => {
    getContractPassword.mockResolvedValue("pw-1");
    const wrapper = await mountView([item(1)]);
    await wrapper.get('[aria-label="契約1のユーザ名をコピー"]').trigger("click");
    await flushPromises();
    await wrapper.get('[aria-label="パスワードをコピー"]').trigger("click");
    await flushPromises();
    expect(clipboard).toEqual(["user1", "pw-1"]);
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
  });

  it("パスワードが未設定の行は「パスワード未設定」とし、ボタンを出さない。パスワードを使わない行は「-」", async () => {
    const wrapper = await mountView([
      item(1, { has_password: false, password_unset: true }),
      item(2, { has_password: false, password_unset: false, username: null }),
    ]);
    const rows = wrapper.findAll(".list-row");
    expect(rows[0]?.text()).toContain("パスワード未設定");
    expect(rows[0]?.findAll('[aria-label^="パスワード"]')).toHaveLength(0);
    expect(rows[1]?.text()).not.toContain("パスワード未設定");
    expect(rows[1]?.findAll("button")).toHaveLength(0);
    expect(rows[1]?.findAll(".caption").map((e) => e.text())).toEqual(["-", "-"]);
  });

  it("検索欄の入力で、一覧を再取得する（入力が続く間は間引く）", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView([item(1), item(2)]);
    listAccounts.mockClear();
    listAccounts.mockResolvedValue([item(2)]);
    const input = wrapper.get('input[aria-label="検索"]');
    expect(input.attributes("placeholder")).toBe("検索");
    await input.setValue("c");
    await input.setValue("co");
    await vi.advanceTimersByTimeAsync(100);
    expect(listAccounts).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    expect(listAccounts).toHaveBeenCalledTimes(1);
    expect(listAccounts).toHaveBeenCalledWith("co");
    expect(wrapper.findAll(".list-row")).toHaveLength(1);
  });

  it("0 件の文言は、検索の有無で変わる", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView([]);
    expect(wrapper.text()).toContain("データがありません");
    expect(wrapper.text()).not.toContain("該当するデータがありません");
    listAccounts.mockResolvedValue([]);
    await wrapper.get("input").setValue("存在しない");
    await vi.advanceTimersByTimeAsync(400);
    await flushPromises();
    expect(wrapper.text()).toContain("該当するデータがありません");
  });

  it("古い検索の応答は捨てる（後の検索の結果を上書きしない）", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView([item(1)]);
    let resolveSlow: (value: AccountItem[]) => void = () => undefined;
    listAccounts.mockReturnValueOnce(new Promise((r) => (resolveSlow = r)));
    await wrapper.get("input").setValue("a");
    await vi.advanceTimersByTimeAsync(300);
    listAccounts.mockResolvedValueOnce([item(9, { name: "新しい結果" })]);
    await wrapper.get("input").setValue("ab");
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    resolveSlow([item(8, { name: "古い結果" })]);
    await flushPromises();
    expect(wrapper.text()).toContain("新しい結果");
    expect(wrapper.text()).not.toContain("古い結果");
  });

  it("取得に失敗したら、内部理由を含まないメッセージを先頭に出す", async () => {
    listAccounts.mockRejectedValue(new Error("boom: internal detail"));
    const wrapper = mount(AccountsView);
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("読み込みに失敗しました");
    expect(wrapper.text()).not.toContain("internal detail");
  });

  it("未ログイン・権限なしは、メッセージを出さずに、殻へ通知する", async () => {
    listAccounts.mockRejectedValue(new AuthError(401));
    const wrapper = mount(AccountsView);
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    const events = wrapper.emitted("auth-error");
    expect(events).toHaveLength(1);
    expect((events?.[0]?.[0] as AuthError).status).toBe(401);
  });

  it("パスワードの取得の失敗は、通知する（401）か、メッセージを出す（その他）。平文は出さない", async () => {
    const wrapper = await mountView([item(1)]);
    getContractPassword.mockRejectedValueOnce(new AuthError(401));
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
    getContractPassword.mockRejectedValueOnce(new Error("x"));
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("パスワードの取得に失敗しました");
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
  });
});
