import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError, apiFetch, apiUrl, ensureOk, getSettings } from "../src/api/client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function respond(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

describe("API クライアント", () => {
  it("基点 URL は環境変数から取り、末尾のスラッシュを重ねない", () => {
    vi.stubEnv("VITE_API_CONTRACT_MANAGEMENT_URL", "http://example.test:8012/");
    expect(apiUrl("/contracts")).toBe("http://example.test:8012/contracts");
  });

  it("Cookie を送り、本文があれば JSON のヘッダを付ける", async () => {
    vi.stubEnv("VITE_API_CONTRACT_MANAGEMENT_URL", "http://api.test");
    const fetchMock = vi.fn().mockResolvedValue(respond(200, {}));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/contracts", { method: "POST", body: "{}" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/contracts");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    await apiFetch("/contracts");
    expect(new Headers((fetchMock.mock.calls[1] as [string, RequestInit])[1].headers).has("Content-Type")).toBe(false);
  });

  it("401 / 403 は AuthError、その他の失敗は本文の detail を持つ ApiError", async () => {
    await expect(ensureOk(respond(401, { detail: "未ログイン" }))).rejects.toMatchObject({ status: 401 });
    await expect(ensureOk(respond(403))).rejects.toBeInstanceOf(AuthError);
    const conflict = await ensureOk(respond(409, { detail: "保存できませんでした" })).catch((e: unknown) => e);
    expect(conflict).toBeInstanceOf(ApiError);
    expect(conflict).toMatchObject({ status: 409, message: "保存できませんでした" });
    // 本文が JSON でないとき・detail が文字列でないときは、内部情報を出さない既定の文言
    const broken = await ensureOk(new Response("<html>", { status: 500 })).catch((e: unknown) => e);
    expect(broken).toMatchObject({ status: 500, message: "サーバエラーです" });
    const odd = await ensureOk(respond(400, { detail: [{ loc: ["x"] }] })).catch((e: unknown) => e);
    expect(odd).toMatchObject({ message: "サーバエラーです" });
    const ok = respond(200, {});
    expect(await ensureOk(ok)).toBe(ok);
  });

  it("設定を取得する（認証不要。失敗は例外）", async () => {
    vi.stubEnv("VITE_API_CONTRACT_MANAGEMENT_URL", "http://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(respond(200, { login_url: "/login", menu_url: "/menu", icon_system: "", icon_back: "" })),
    );
    expect((await getSettings()).menu_url).toBe("/menu");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(500)));
    await expect(getSettings()).rejects.toThrow();
  });
});
