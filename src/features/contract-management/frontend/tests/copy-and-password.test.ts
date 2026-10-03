import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api/client";
import CopyButton from "../src/components/CopyButton.vue";
import PasswordField from "../src/components/PasswordField.vue";

let clipboard: string[];

beforeEach(() => {
  clipboard = [];
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(async (text: string) => void clipboard.push(text)) },
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("コピーボタン", () => {
  it("値をコピーし、直後は「コピー済」になって、数秒で戻る", async () => {
    vi.useFakeTimers();
    const wrapper = mount(CopyButton, { props: { value: "taro", label: "ユーザ名をコピー" } });
    expect(wrapper.text()).toBe("コピー");
    expect(wrapper.attributes("aria-label")).toBe("ユーザ名をコピー");
    await wrapper.trigger("click");
    await flushPromises();
    expect(clipboard).toEqual(["taro"]);
    expect(wrapper.text()).toBe("コピー済");
    await vi.advanceTimersByTimeAsync(2100);
    expect(wrapper.text()).toBe("コピー");
  });

  it("関数の値は、押された時点で呼ぶ（それまでは呼ばない）", async () => {
    const getter = vi.fn(async () => "遅れて取得");
    const wrapper = mount(CopyButton, { props: { value: getter, label: "コピー" } });
    expect(getter).not.toHaveBeenCalled();
    await wrapper.trigger("click");
    await flushPromises();
    expect(getter).toHaveBeenCalledTimes(1);
    expect(clipboard).toEqual(["遅れて取得"]);
  });

  it("取得に失敗したときは、コピーせず、error を通知する", async () => {
    const wrapper = mount(CopyButton, {
      props: { value: async () => Promise.reject(new AuthError(401)), label: "コピー" },
    });
    await wrapper.trigger("click");
    await flushPromises();
    expect(clipboard).toEqual([]);
    expect(wrapper.text()).toBe("コピー");
    const errors = wrapper.emitted("error");
    expect(errors).toHaveLength(1);
    expect((errors?.[0]?.[0] as AuthError).status).toBe(401);
  });

  it("Clipboard API が使えないときは、一時的な入力欄でコピーする", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    document.execCommand = vi.fn(() => true);
    const wrapper = mount(CopyButton, { props: { value: "fallback", label: "コピー" } });
    await wrapper.trigger("click");
    await flushPromises();
    expect(document.execCommand).toHaveBeenCalledWith("copy");
    expect(wrapper.text()).toBe("コピー済");
    expect(document.querySelectorAll("textarea")).toHaveLength(0);
  });
});

describe("パスワードの表示部品", () => {
  it("未設定のときは「パスワード未設定」だけを出し、ボタンは出さない", () => {
    const fetchPassword = vi.fn();
    const wrapper = mount(PasswordField, { props: { hasPassword: false, fetchPassword } });
    expect(wrapper.text()).toBe("パスワード未設定");
    expect(wrapper.findAll("button")).toHaveLength(0);
    expect(fetchPassword).not.toHaveBeenCalled();
  });

  it("操作するまで値を取得せず、マスク表示のままにする", () => {
    const fetchPassword = vi.fn(async () => "secret");
    const wrapper = mount(PasswordField, { props: { hasPassword: true, fetchPassword } });
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
    expect(wrapper.html()).not.toContain("secret");
    expect(fetchPassword).not.toHaveBeenCalled();
  });

  it("「表示」で取得して平文を出し、「隠す」で戻して、値を保持しない", async () => {
    const fetchPassword = vi.fn(async () => "  複数\n行  ");
    const wrapper = mount(PasswordField, { props: { hasPassword: true, fetchPassword } });
    const toggle = wrapper.get('[aria-label="パスワードを表示"]');
    expect(toggle.text()).toBe("表示");
    await toggle.trigger("click");
    await flushPromises();
    expect(fetchPassword).toHaveBeenCalledTimes(1);
    expect(wrapper.get('[data-testid="password-value"]').text()).toContain("複数");
    expect(wrapper.get('[aria-label="パスワードを隠す"]').text()).toBe("隠す");
    await wrapper.get('[aria-label="パスワードを隠す"]').trigger("click");
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
    expect(wrapper.html()).not.toContain("複数");
    // 再び表示するときは、取得し直す
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(fetchPassword).toHaveBeenCalledTimes(2);
  });

  it("マスク表示中でもコピーでき、コピーのために取得した値を画面に出さない", async () => {
    const fetchPassword = vi.fn(async () => "S3cret-Pass");
    const wrapper = mount(PasswordField, { props: { hasPassword: true, fetchPassword } });
    await wrapper.get('[aria-label="パスワードをコピー"]').trigger("click");
    await flushPromises();
    expect(clipboard).toEqual(["S3cret-Pass"]);
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
    expect(wrapper.html()).not.toContain("S3cret-Pass");
  });

  it("取得に失敗したら error を通知し、平文を出さない", async () => {
    const fetchPassword = vi.fn(async () => Promise.reject(new AuthError(403)));
    const wrapper = mount(PasswordField, { props: { hasPassword: true, fetchPassword } });
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
    expect(wrapper.emitted("error")).toHaveLength(1);
    await wrapper.get('[aria-label="パスワードをコピー"]').trigger("click");
    await flushPromises();
    expect(wrapper.emitted("error")).toHaveLength(2);
    expect(clipboard).toEqual([]);
  });
});
