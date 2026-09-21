// api-design.md の全エンドポイントに対応する呼び出し。

import { apiUrl, jsonBody, queryString, request, requestVoid } from "./client";
import type {
  Checklist,
  FileDetail,
  FileSummary,
  Folder,
  ItemsResponse,
  Part,
  PartCreateBody,
  PartUpdateBody,
  Settings,
} from "../types";

export * from "./client";

// ---- 設定 ------------------------------------------------------------

export const getSettings = (): Promise<Settings> => request<Settings>("/settings");

// ---- ツリー・フォルダ ------------------------------------------------------

export const listItems = (folderId: number | null, includeDeleted: boolean): Promise<ItemsResponse> =>
  request(`/items${queryString({ folder_id: folderId ?? undefined, include_deleted: includeDeleted ? "true" : undefined })}`);

export const createFolder = (parentId: number | null, name: string): Promise<Folder> =>
  request("/folders", { method: "POST", body: jsonBody({ parent_id: parentId, name }) });

export const renameFolder = (id: number, name: string): Promise<Folder> =>
  request(`/folders/${id}`, { method: "PATCH", body: jsonBody({ name }) });

export const moveFolder = (id: number, newParentId: number | null): Promise<Folder> =>
  request(`/folders/${id}/move`, { method: "POST", body: jsonBody({ new_parent_id: newParentId }) });

export const swapFolders = (id1: number, id2: number): Promise<void> =>
  requestVoid("/folders/swap-order", { method: "POST", body: jsonBody({ folder_id_1: id1, folder_id_2: id2 }) });

export const deleteFolder = (id: number): Promise<void> => requestVoid(`/folders/${id}`, { method: "DELETE" });

export const undeleteFolder = (id: number): Promise<Folder> =>
  request(`/folders/${id}/undelete`, { method: "POST" });

// ---- ファイル ------------------------------------------------------------

export const createFile = (folderId: number, title: string): Promise<FileSummary> =>
  request("/files", { method: "POST", body: jsonBody({ folder_id: folderId, title }) });

export const getFile = (id: number, includeDeletedParts: boolean): Promise<FileDetail> =>
  request(`/files/${id}${queryString({ include_deleted_parts: includeDeletedParts ? "true" : undefined })}`);

export const renameFile = (id: number, title: string): Promise<FileSummary> =>
  request(`/files/${id}`, { method: "PATCH", body: jsonBody({ title }) });

export const moveFile = (id: number, newFolderId: number): Promise<FileSummary> =>
  request(`/files/${id}/move`, { method: "POST", body: jsonBody({ new_folder_id: newFolderId }) });

export const swapFiles = (id1: number, id2: number): Promise<void> =>
  requestVoid("/files/swap-order", { method: "POST", body: jsonBody({ file_id_1: id1, file_id_2: id2 }) });

export const deleteFile = (id: number): Promise<void> => requestVoid(`/files/${id}`, { method: "DELETE" });

export const undeleteFile = (id: number): Promise<FileSummary> =>
  request(`/files/${id}/undelete`, { method: "POST" });

// ---- パーツ ------------------------------------------------------------

export const createPart = (fileId: number, body: PartCreateBody): Promise<Part> =>
  request(`/files/${fileId}/parts`, { method: "POST", body: jsonBody(body) });

export const updatePart = (id: number, body: PartUpdateBody): Promise<Part> =>
  request(`/parts/${id}`, { method: "PATCH", body: jsonBody(body) });

export const deletePart = (id: number): Promise<void> => requestVoid(`/parts/${id}`, { method: "DELETE" });

export const undeletePart = (id: number): Promise<Part> => request(`/parts/${id}/undelete`, { method: "POST" });

export const swapParts = (id1: number, id2: number): Promise<void> =>
  requestVoid("/parts/swap-order", { method: "POST", body: jsonBody({ part_id_1: id1, part_id_2: id2 }) });

/** 画像・バイナリの中身の取得先（`<img>` の参照先、ダウンロードのリンク）。Cookie はブラウザが送る。 */
export const partContentUrl = (id: number, download = false, version = 0): string =>
  apiUrl(`/parts/${id}/content${queryString({ download: download ? "true" : undefined, v: version || undefined })}`);

export const revisionContentUrl = (id: number): string => apiUrl(`/part-revisions/${id}/content`);

// ---- チェックリスト --------------------------------------------------------

export const getChecklist = (id: number): Promise<Checklist> => request(`/checklists/${id}`);

export const updateChecklistTitle = (id: number, title: string): Promise<Checklist> =>
  request(`/checklists/${id}`, { method: "PATCH", body: jsonBody({ title }) });

export const createCategory = (id: number, name: string): Promise<Checklist> =>
  request(`/checklists/${id}/categories`, { method: "POST", body: jsonBody({ name }) });

export const renameCategory = (id: number, categoryId: number, name: string): Promise<Checklist> =>
  request(`/checklists/${id}/categories/${categoryId}`, { method: "PATCH", body: jsonBody({ name }) });

export const deleteCategory = (id: number, categoryId: number): Promise<Checklist> =>
  request(`/checklists/${id}/categories/${categoryId}`, { method: "DELETE" });

export const reorderCategories = (id: number, orderedIds: number[]): Promise<Checklist> =>
  request(`/checklists/${id}/categories/reorder`, { method: "POST", body: jsonBody({ ordered_ids: orderedIds }) });

export const createItem = (id: number, categoryId: number | null, title: string): Promise<Checklist> =>
  request(`/checklists/${id}/items`, { method: "POST", body: jsonBody({ category_id: categoryId, title }) });

export const updateItem = (
  id: number,
  itemId: number,
  body: { title?: string; is_checked?: boolean },
): Promise<Checklist> => request(`/checklists/${id}/items/${itemId}`, { method: "PATCH", body: jsonBody(body) });

export const deleteItem = (id: number, itemId: number): Promise<Checklist> =>
  request(`/checklists/${id}/items/${itemId}`, { method: "DELETE" });

export const moveItem = (id: number, itemId: number, toCategoryId: number, toIndex: number): Promise<Checklist> =>
  request(`/checklists/${id}/items/${itemId}/move`, {
    method: "POST",
    body: jsonBody({ to_category_id: toCategoryId, to_index: toIndex }),
  });
