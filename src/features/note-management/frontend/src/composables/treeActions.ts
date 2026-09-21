// ツリーの各行（TreeNode）が呼ぶ操作。SCR-001 の画面（NoteListView）が提供する。

import type { InjectionKey, Ref } from "vue";
import type { FileSummary, Folder } from "../types";

/** PDF 出力の対象に選んだファイル */
export interface PdfItem {
  fileId: number;
  folderName: string;
  title: string;
}

export interface TreeActions {
  editMode: Ref<boolean>;
  pdfMode: Ref<boolean>;
  pdfSelected: Ref<PdfItem[]>;
  busy: Ref<boolean>;
  openFile(id: number): void;
  togglePdf(file: FileSummary, folderName: string): void;
  createFolder(parentId: number): void;
  createFile(folderId: number): void;
  renameFolder(folder: Folder): void;
  renameFile(file: FileSummary): void;
  moveFolder(folder: Folder): void;
  moveFile(file: FileSummary): void;
  deleteFolder(folder: Folder): void;
  deleteFile(file: FileSummary): void;
  undeleteFolder(folder: Folder): void;
  undeleteFile(file: FileSummary): void;
  swapFolders(parentId: number | null, first: Folder, second: Folder): void;
  swapFiles(folderId: number, first: FileSummary, second: FileSummary): void;
}

export const treeActionsKey: InjectionKey<TreeActions> = Symbol("treeActions");
