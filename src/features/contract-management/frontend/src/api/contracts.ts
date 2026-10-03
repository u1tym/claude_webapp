import { apiFetch, ensureOk } from "./client";
import type { AccountItem, Contract, ContractFilters, ContractInput } from "./types";

/** 絞り込み条件を、クエリ文字列にする。空の条件は付けない。 */
export function contractQuery(filters: ContractFilters): string {
  const params = new URLSearchParams();
  const keyword = filters.keyword?.trim();
  if (keyword) {
    params.set("keyword", keyword);
  }
  if (filters.category_id !== undefined && filters.category_id !== null) {
    params.set("category_id", String(filters.category_id));
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.has_contract !== undefined && filters.has_contract !== null) {
    params.set("has_contract", String(filters.has_contract));
  }
  if (filters.password_unset) {
    params.set("password_unset", "true");
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** 契約の一覧。401 / 403 は AuthError。 */
export async function listContracts(filters: ContractFilters = {}): Promise<Contract[]> {
  const res = await ensureOk(await apiFetch(`/contracts${contractQuery(filters)}`));
  return ((await res.json()) as { items: Contract[] }).items;
}

export async function getContract(id: number): Promise<Contract> {
  const res = await ensureOk(await apiFetch(`/contracts/${id}`));
  return (await res.json()) as Contract;
}

/** パスワードの値を 1 件取得する。一覧・詳細の応答には含まれないので、「表示」「コピー」の操作時に呼ぶ。 */
export async function getContractPassword(id: number): Promise<string | null> {
  const res = await ensureOk(await apiFetch(`/contracts/${id}/password`));
  return ((await res.json()) as { password: string | null }).password;
}

export async function createContract(input: ContractInput): Promise<Contract> {
  const res = await ensureOk(await apiFetch("/contracts", { method: "POST", body: JSON.stringify(input) }));
  return (await res.json()) as Contract;
}

export async function updateContract(id: number, input: ContractInput): Promise<Contract> {
  const res = await ensureOk(await apiFetch(`/contracts/${id}`, { method: "PATCH", body: JSON.stringify(input) }));
  return (await res.json()) as Contract;
}

export async function deleteContract(id: number): Promise<void> {
  await ensureOk(await apiFetch(`/contracts/${id}`, { method: "DELETE" }));
}

/** アカウント一覧（ユーザ名またはパスワードを持つ契約）。パスワードの値は含まれない。 */
export async function listAccounts(keyword = ""): Promise<AccountItem[]> {
  const text = keyword.trim();
  const query = text ? `?${new URLSearchParams({ keyword: text }).toString()}` : "";
  const res = await ensureOk(await apiFetch(`/accounts${query}`));
  return ((await res.json()) as { items: AccountItem[] }).items;
}
