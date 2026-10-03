import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError } from "../src/api/client";
import { getCandidates, getPlan, savePlan } from "../src/api/cancellation";
import { createCategory, deleteCategory, listCategories, updateCategory } from "../src/api/categories";
import {
  contractQuery,
  createContract,
  deleteContract,
  getContract,
  getContractPassword,
  listAccounts,
  listContracts,
  updateContract,
} from "../src/api/contracts";
import { emptyContractInput } from "../src/format";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubEnv("VITE_API_CONTRACT_MANAGEMENT_URL", "http://api.test");
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function reply(status: number, body?: unknown): void {
  fetchMock.mockResolvedValueOnce(new Response(body === undefined ? null : JSON.stringify(body), { status }));
}

function lastCall(): { url: string; method: string; body: unknown; credentials: RequestCredentials | undefined } {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return {
    url,
    method: init.method ?? "GET",
    body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
    credentials: init.credentials,
  };
}

describe("契約の絞り込みのクエリ", () => {
  it("空の条件は付けず、付ける条件は API の名前のまま渡す", () => {
    expect(contractQuery({})).toBe("");
    expect(contractQuery({ keyword: "  ", category_id: null, status: "", has_contract: null, password_unset: false })).toBe("");
    expect(contractQuery({ keyword: " Net flix ", category_id: 3, status: "paused", has_contract: false, password_unset: true })).toBe(
      "?keyword=Net+flix&category_id=3&status=paused&has_contract=false&password_unset=true",
    );
    expect(contractQuery({ has_contract: true })).toBe("?has_contract=true");
  });
});

describe("契約 API", () => {
  it("一覧・詳細・パスワードの取得", async () => {
    reply(200, { total: 1, items: [{ id: 1 }] });
    expect(await listContracts({ keyword: "a" })).toEqual([{ id: 1 }]);
    expect(lastCall()).toMatchObject({ url: "http://api.test/contracts?keyword=a", method: "GET", credentials: "include" });
    reply(200, { id: 7 });
    expect(await getContract(7)).toEqual({ id: 7 });
    expect(lastCall().url).toBe("http://api.test/contracts/7");
    reply(200, { password: "  複数\n行  " });
    expect(await getContractPassword(7)).toBe("  複数\n行  ");
    expect(lastCall().url).toBe("http://api.test/contracts/7/password");
    reply(200, { password: null });
    expect(await getContractPassword(7)).toBeNull();
  });

  it("登録・更新・削除は、メソッドと本文のとおりに呼ぶ", async () => {
    const input = { ...emptyContractInput(), name: "新規", password: "pw" };
    reply(201, { id: 9 });
    expect(await createContract(input)).toEqual({ id: 9 });
    expect(lastCall()).toMatchObject({ url: "http://api.test/contracts", method: "POST", body: input });
    reply(200, { id: 9 });
    await updateContract(9, emptyContractInput());
    expect(lastCall()).toMatchObject({ url: "http://api.test/contracts/9", method: "PATCH" });
    expect((lastCall().body as Record<string, unknown>).password).toBeUndefined(); // password を送らなければ、変わらない
    reply(204);
    await deleteContract(9);
    expect(lastCall()).toMatchObject({ url: "http://api.test/contracts/9", method: "DELETE" });
  });

  it("アカウント一覧（キーワードがあるときだけ付ける）", async () => {
    reply(200, { total: 1, items: [{ id: 3, name: "a" }] });
    expect(await listAccounts("  taro ")).toEqual([{ id: 3, name: "a" }]);
    expect(lastCall().url).toBe("http://api.test/accounts?keyword=taro");
    reply(200, { total: 0, items: [] });
    await listAccounts("");
    expect(lastCall().url).toBe("http://api.test/accounts");
  });

  it("401 / 403 は AuthError、409 は本文の一文を持つ ApiError", async () => {
    reply(401, { detail: "未ログイン" });
    await expect(listContracts()).rejects.toBeInstanceOf(AuthError);
    reply(403, { detail: "権限がありません" });
    await expect(getContractPassword(1)).rejects.toMatchObject({ status: 403 });
    reply(409, { detail: "保存できませんでした" });
    const error = await updateContract(1, emptyContractInput()).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, message: "保存できませんでした" });
    reply(400, { detail: "入力が不正です" });
    await expect(createContract(emptyContractInput())).rejects.toMatchObject({ status: 400, message: "入力が不正です" });
    reply(404, { detail: "対象がありません" });
    await expect(deleteContract(1)).rejects.toMatchObject({ status: 404 });
  });
});

describe("区分 API", () => {
  it("一覧・追加・更新・削除", async () => {
    reply(200, { items: [{ id: 1, name: "その他", is_default: true, is_financial: false }] });
    expect((await listCategories())[0]?.name).toBe("その他");
    reply(201, { id: 2, name: "銀行", is_default: false, is_financial: true });
    await createCategory({ name: "銀行", is_financial: true });
    expect(lastCall()).toMatchObject({ url: "http://api.test/categories", method: "POST", body: { name: "銀行", is_financial: true } });
    reply(200, { id: 2, name: "銀行2", is_default: false, is_financial: false });
    await updateCategory(2, { name: "銀行2", is_financial: false });
    expect(lastCall()).toMatchObject({ url: "http://api.test/categories/2", method: "PATCH", body: { name: "銀行2", is_financial: false } });
    reply(204);
    await deleteCategory(2);
    expect(lastCall()).toMatchObject({ url: "http://api.test/categories/2", method: "DELETE" });
    reply(409, { detail: "保存できませんでした" });
    await expect(deleteCategory(1)).rejects.toMatchObject({ status: 409 });
  });
});

describe("解約順 API", () => {
  it("取得・候補・保存", async () => {
    reply(200, { items: [], warnings: [] });
    expect(await getPlan()).toEqual({ items: [], warnings: [] });
    expect(lastCall().url).toBe("http://api.test/cancellation-plan");
    reply(200, { items: [{ id: 15, name: "ジム", category_name: "その他", has_cancellation_method: false }] });
    expect((await getCandidates())[0]?.name).toBe("ジム");
    expect(lastCall().url).toBe("http://api.test/cancellation-plan/candidates");
    reply(200, { items: [], warnings: [] });
    await savePlan([3, 1, 2]);
    expect(lastCall()).toMatchObject({ url: "http://api.test/cancellation-plan", method: "PUT", body: { contract_ids: [3, 1, 2] } });
    reply(400, { detail: "入力が不正です" });
    await expect(savePlan([1, 1])).rejects.toMatchObject({ status: 400 });
  });
});
