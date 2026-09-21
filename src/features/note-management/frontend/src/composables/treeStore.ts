// SCR-001 のツリーの状態。SCR-002 から戻ったとき、開いているフォルダと「削除済みを表示」を保つため、
// 画面の外（モジュール）に持つ。ブラウザを再読み込みしたときは、初期の状態に戻る。

import { reactive } from "vue";
import { errorMessage, listItems } from "../api";
import type { FileSummary, Folder } from "../types";

export interface ChildrenState {
  folders: Folder[];
  files: FileSummary[];
  loading: boolean;
  error: string;
  /** 開いているフォルダの、削除済みか（自身、または上位）。追加の操作の可否に使う */
  deleted: boolean;
}

interface TreeState {
  roots: Folder[];
  rootLoading: boolean;
  rootError: string;
  rootLoaded: boolean;
  showDeleted: boolean;
  expanded: Record<number, true>;
  children: Record<number, ChildrenState>;
}

export const tree = reactive<TreeState>({
  roots: [],
  rootLoading: false,
  rootError: "",
  rootLoaded: false,
  showDeleted: false,
  expanded: {},
  children: {},
});

export async function loadRoot(): Promise<void> {
  tree.rootLoading = true;
  tree.rootError = "";
  try {
    tree.roots = (await listItems(null, tree.showDeleted)).folders;
    tree.rootLoaded = true;
  } catch (e) {
    tree.rootError = errorMessage(e);
  } finally {
    tree.rootLoading = false;
  }
}

export async function loadChildren(folderId: number): Promise<void> {
  const previous = tree.children[folderId];
  tree.children[folderId] = {
    folders: previous?.folders ?? [],
    files: previous?.files ?? [],
    loading: true,
    error: "",
    deleted: previous?.deleted ?? false,
  };
  try {
    const res = await listItems(folderId, tree.showDeleted);
    tree.children[folderId] = {
      folders: res.folders,
      files: res.files,
      loading: false,
      error: "",
      deleted: res.parent ? res.parent.is_deleted || res.parent.ancestor_deleted : false,
    };
  } catch (e) {
    const state = tree.children[folderId];
    state.loading = false;
    state.error = errorMessage(e);
    // フォルダが無くなっている（他で削除されたなど）ときは、閉じる
    delete tree.expanded[folderId];
  }
}

export async function toggleFolder(folderId: number): Promise<void> {
  if (tree.expanded[folderId]) {
    delete tree.expanded[folderId];
    return;
  }
  tree.expanded[folderId] = true;
  await loadChildren(folderId);
}

/** 親（null はルート）の直下を取得し直す。 */
export async function reloadParent(parentId: number | null): Promise<void> {
  if (parentId === null) {
    await loadRoot();
  } else {
    await loadChildren(parentId);
  }
}

/** ルートと、開いているフォルダの中身を、すべて取得し直す。 */
export async function reloadOpen(): Promise<void> {
  const open = Object.keys(tree.expanded).map(Number);
  await Promise.all([loadRoot(), ...open.map((id) => loadChildren(id))]);
}

export async function setShowDeleted(value: boolean): Promise<void> {
  tree.showDeleted = value;
  await reloadOpen();
}
