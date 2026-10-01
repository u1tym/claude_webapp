import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError, apiFetch, apiUrl, getSettings, throwIfAuthFailed } from "../src/api";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function stubFetch(response: Partial<Response>) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("apiUrl", () => {
  it("環境変数の基点 URL にパスを足す（末尾のスラッシュは吸収する）", () => {
    vi.stubEnv("VITE_API_ROOM_URL", "http://api.example.test:8011/");
    expect(apiUrl("/state")).toBe("http://api.example.test:8011/state");
    vi.stubEnv("VITE_API_ROOM_URL", "http://api.example.test:8011");
    expect(apiUrl("/state")).toBe("http://api.example.test:8011/state");
  });
});

describe("apiFetch", () => {
  it("Cookie を送る（credentials: include）", async () => {
    const fetchMock = stubFetch({ ok: true, status: 200 });
    await apiFetch("/state");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(apiUrl("/state"));
    expect(init.credentials).toBe("include");
  });

  it("本文があるときだけ Content-Type を JSON にする", async () => {
    const fetchMock = stubFetch({ ok: true, status: 200 });
    await apiFetch("/schedules", { method: "POST", body: "{}" });
    await apiFetch("/state");
    const withBody = new Headers((fetchMock.mock.calls[0] as [string, RequestInit])[1].headers);
    const withoutBody = new Headers((fetchMock.mock.calls[1] as [string, RequestInit])[1].headers);
    expect(withBody.get("Content-Type")).toBe("application/json");
    expect(withoutBody.has("Content-Type")).toBe(false);
  });

  it("認証情報を URL・ヘッダ・ブラウザの保存領域に置かない", async () => {
    const fetchMock = stubFetch({ ok: true, status: 200 });
    await apiFetch("/state");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).not.toContain("session");
    expect(new Headers(init.headers).has("Authorization")).toBe(false);
    expect(localStorage.length).toBe(0);
  });
});

describe("throwIfAuthFailed", () => {
  it("401 と 403 は AuthError を投げる", () => {
    expect(() => throwIfAuthFailed({ status: 401 } as Response)).toThrow(AuthError);
    expect(() => throwIfAuthFailed({ status: 403 } as Response)).toThrow(AuthError);
    try {
      throwIfAuthFailed({ status: 403 } as Response);
    } catch (error) {
      expect((error as AuthError).status).toBe(403);
    }
  });

  it("それ以外は何もしない", () => {
    for (const status of [200, 204, 400, 404, 500, 502]) {
      expect(() => throwIfAuthFailed({ status } as Response)).not.toThrow();
    }
  });
});

describe("getSettings", () => {
  const settings = {
    login_url: "http://localhost/login",
    menu_url: "http://localhost/menu",
    icon_system: "data:image/png;base64,AAAA",
    icon_back: "data:image/png;base64,BBBB",
  };

  it("設定を返す", async () => {
    stubFetch({ ok: true, status: 200, json: async () => settings });
    await expect(getSettings()).resolves.toEqual(settings);
  });

  it("失敗したら例外にする", async () => {
    stubFetch({ ok: false, status: 500 });
    await expect(getSettings()).rejects.toThrow();
  });
});
