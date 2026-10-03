import { apiFetch, ensureOk } from "./client";
import type { Category, CategoryInput } from "./types";

/** 区分の一覧（「その他」が先頭）。 */
export async function listCategories(): Promise<Category[]> {
  const res = await ensureOk(await apiFetch("/categories"));
  return ((await res.json()) as { items: Category[] }).items;
}

export async function createCategory(input: CategoryInput): Promise<Category> {
  const res = await ensureOk(await apiFetch("/categories", { method: "POST", body: JSON.stringify(input) }));
  return (await res.json()) as Category;
}

export async function updateCategory(id: number, input: CategoryInput): Promise<Category> {
  const res = await ensureOk(await apiFetch(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(input) }));
  return (await res.json()) as Category;
}

export async function deleteCategory(id: number): Promise<void> {
  await ensureOk(await apiFetch(`/categories/${id}`, { method: "DELETE" }));
}
