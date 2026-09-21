<script setup lang="ts">
import { computed, onMounted, provide, ref } from "vue";
import { useRouter } from "vue-router";
import {
  createFile,
  createFolder,
  deleteFile,
  deleteFolder,
  errorMessage,
  getFile,
  moveFile,
  moveFolder,
  renameFile,
  renameFolder,
  swapFiles,
  swapFolders,
  undeleteFile,
  undeleteFolder,
} from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import FolderPicker from "../components/FolderPicker.vue";
import Icon from "../components/Icon.vue";
import NameDialog from "../components/NameDialog.vue";
import PrintDocument from "../components/PrintDocument.vue";
import TreeNode from "../components/TreeNode.vue";
import { treeActionsKey, type PdfItem, type TreeActions } from "../composables/treeActions";
import { loadChildren, loadRoot, reloadOpen, reloadParent, setShowDeleted, tree } from "../composables/treeStore";
import type { FileSummary, Folder, PrintFile } from "../types";

const router = useRouter();

const editMode = ref(false);
const pdfMode = ref(false);
const pdfSelected = ref<PdfItem[]>([]);
const pageBreak = ref(true);
const busy = ref(false);
const error = ref("");
const success = ref("");
let successTimer: ReturnType<typeof setTimeout> | undefined;

function flash(message: string): void {
  success.value = message;
  clearTimeout(successTimer);
  successTimer = setTimeout(() => (success.value = ""), 3000);
}

// ---- モード ----------------------------------------------------------------

function toggleEdit(): void {
  editMode.value = !editMode.value;
  if (editMode.value) {
    pdfMode.value = false;
    pdfSelected.value = [];
  }
}

function togglePdfMode(): void {
  pdfMode.value = !pdfMode.value;
  if (pdfMode.value) {
    editMode.value = false;
  }
  pdfSelected.value = [];
  pdfError.value = "";
  pageBreak.value = true;
}

async function onShowDeleted(event: Event): Promise<void> {
  await setShowDeleted((event.target as HTMLInputElement).checked);
}

// ---- 入力・確認・移動先のダイアログ --------------------------------------------------

type NameKind = "createRootFolder" | "createFolder" | "createFile" | "renameFolder" | "renameFile";

interface NameState {
  kind: NameKind;
  title: string;
  label: string;
  initial: string;
  /** 作成のときの親（フォルダの中）。名前変更のときは対象の識別子 */
  targetId: number | null;
  /** 変更後に取得し直す親（null はルート） */
  parentId: number | null;
}

const nameDialog = ref<NameState | null>(null);
const dialogBusy = ref(false);
const dialogError = ref("");

interface ConfirmState {
  kind: "folder" | "file";
  id: number;
  name: string;
  parentId: number | null;
}

const confirming = ref<ConfirmState | null>(null);

interface MoveState {
  kind: "folder" | "file";
  id: number;
  name: string;
  currentParentId: number | null;
}

const moving = ref<MoveState | null>(null);

function closeDialogs(): void {
  nameDialog.value = null;
  moving.value = null;
  dialogError.value = "";
}

async function onSaveName(value: string): Promise<void> {
  const state = nameDialog.value;
  if (!state) {
    return;
  }
  dialogBusy.value = true;
  dialogError.value = "";
  try {
    if (state.kind === "createRootFolder") {
      await createFolder(null, value);
    } else if (state.kind === "createFolder") {
      await createFolder(state.targetId, value);
    } else if (state.kind === "createFile") {
      await createFile(state.targetId as number, value);
    } else if (state.kind === "renameFolder") {
      await renameFolder(state.targetId as number, value);
    } else {
      await renameFile(state.targetId as number, value);
    }
    const isCreate = state.kind.startsWith("create");
    if (state.kind === "createFolder" || state.kind === "createFile") {
      tree.expanded[state.targetId as number] = true; // 追加したものが見えるよう、親を開く
    }
    nameDialog.value = null;
    await reloadParent(state.parentId);
    if (state.kind === "createFolder" || state.kind === "createFile") {
      await loadChildren(state.targetId as number);
    }
    flash(isCreate ? "作成しました" : "変更しました");
  } catch (e) {
    dialogError.value = errorMessage(e);
  } finally {
    dialogBusy.value = false;
  }
}

async function run(action: () => Promise<void>, message?: string): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    await action();
    if (message) {
      flash(message);
    }
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}

async function onConfirmDelete(): Promise<void> {
  const state = confirming.value;
  confirming.value = null;
  if (!state) {
    return;
  }
  await run(async () => {
    if (state.kind === "folder") {
      await deleteFolder(state.id);
      // 中のフォルダ・ファイルは、「上位が削除済み」になるため、開いているものを取得し直す
      await reloadOpen();
    } else {
      await deleteFile(state.id);
      await reloadParent(state.parentId);
    }
  }, "削除しました");
}

async function onPickDestination(destination: number | null): Promise<void> {
  const state = moving.value;
  if (!state) {
    return;
  }
  dialogBusy.value = true;
  dialogError.value = "";
  try {
    if (state.kind === "folder") {
      await moveFolder(state.id, destination);
    } else {
      await moveFile(state.id, destination as number);
    }
    moving.value = null;
    if (destination !== null) {
      tree.expanded[destination] = true;
    }
    await reloadOpen();
    flash("移動しました");
  } catch (e) {
    dialogError.value = errorMessage(e);
  } finally {
    dialogBusy.value = false;
  }
}

// ---- ツリーの操作（TreeNode から呼ばれる） ----------------------------------------------

function openNameDialog(state: NameState): void {
  dialogError.value = "";
  nameDialog.value = state;
}

function createRootFolder(): void {
  openNameDialog({ kind: "createRootFolder", title: "フォルダ追加", label: "フォルダ名", initial: "", targetId: null, parentId: null });
}

const actions: TreeActions = {
  editMode,
  pdfMode,
  pdfSelected,
  busy,
  openFile: (id) => void router.push(`/files/${id}`),
  togglePdf: (file: FileSummary, folderName: string) => {
    const index = pdfSelected.value.findIndex((item) => item.fileId === file.id);
    if (index >= 0) {
      pdfSelected.value = pdfSelected.value.filter((item) => item.fileId !== file.id);
    } else {
      pdfSelected.value = [...pdfSelected.value, { fileId: file.id, folderName, title: file.title }];
    }
  },
  createFolder: (parentId) =>
    openNameDialog({ kind: "createFolder", title: "フォルダ追加", label: "フォルダ名", initial: "", targetId: parentId, parentId }),
  createFile: (folderId) =>
    openNameDialog({ kind: "createFile", title: "ファイル追加", label: "タイトル", initial: "", targetId: folderId, parentId: folderId }),
  renameFolder: (folder: Folder) =>
    openNameDialog({ kind: "renameFolder", title: "名前変更", label: "フォルダ名", initial: folder.name, targetId: folder.id, parentId: folder.parent_id }),
  renameFile: (file: FileSummary) =>
    openNameDialog({ kind: "renameFile", title: "タイトル変更", label: "タイトル", initial: file.title, targetId: file.id, parentId: file.folder_id }),
  moveFolder: (folder: Folder) => {
    dialogError.value = "";
    moving.value = { kind: "folder", id: folder.id, name: folder.name, currentParentId: folder.parent_id };
  },
  moveFile: (file: FileSummary) => {
    dialogError.value = "";
    moving.value = { kind: "file", id: file.id, name: file.title, currentParentId: file.folder_id };
  },
  deleteFolder: (folder: Folder) => {
    confirming.value = { kind: "folder", id: folder.id, name: folder.name, parentId: folder.parent_id };
  },
  deleteFile: (file: FileSummary) => {
    confirming.value = { kind: "file", id: file.id, name: file.title, parentId: file.folder_id };
  },
  undeleteFolder: (folder: Folder) =>
    void run(async () => {
      await undeleteFolder(folder.id);
      await reloadOpen();
    }, "削除を解除しました"),
  undeleteFile: (file: FileSummary) =>
    void run(async () => {
      await undeleteFile(file.id);
      await reloadParent(file.folder_id);
    }, "削除を解除しました"),
  swapFolders: (parentId, first, second) =>
    void run(async () => {
      await swapFolders(first.id, second.id);
      await reloadParent(parentId);
    }),
  swapFiles: (folderId, first, second) =>
    void run(async () => {
      await swapFiles(first.id, second.id);
      await reloadParent(folderId);
    }),
};

provide(treeActionsKey, actions);

// ---- PDF 出力 ---------------------------------------------------------------

const pdfError = ref("");
const exporting = ref(false);
const printFiles = ref<PrintFile[]>([]);
let printReady: (() => void) | null = null;

function movePdf(index: number, delta: -1 | 1): void {
  const target = index + delta;
  if (target < 0 || target >= pdfSelected.value.length) {
    return;
  }
  const next = [...pdfSelected.value];
  const [item] = next.splice(index, 1);
  next.splice(target, 0, item);
  pdfSelected.value = next;
}

function removePdf(fileId: number): void {
  pdfSelected.value = pdfSelected.value.filter((item) => item.fileId !== fileId);
}

function onPrintReady(): void {
  printReady?.();
}

async function exportPdf(): Promise<void> {
  if (pdfSelected.value.length === 0 || exporting.value) {
    return;
  }
  exporting.value = true;
  pdfError.value = "";
  try {
    const loaded: PrintFile[] = [];
    for (const item of pdfSelected.value) {
      const detail = await getFile(item.fileId, false);
      loaded.push({
        fileId: item.fileId,
        folderName: detail.folder.name,
        title: detail.title,
        parts: detail.parts.filter((part) => !part.is_deleted),
      });
    }
    const ready = new Promise<void>((resolve) => {
      printReady = resolve;
    });
    printFiles.value = loaded;
    await ready;
    window.print();
  } catch (e) {
    pdfError.value = errorMessage(e);
  } finally {
    printFiles.value = [];
    printReady = null;
    exporting.value = false;
  }
}

// ---- 表示 -------------------------------------------------------------------

const isEmpty = computed(() => tree.rootLoaded && tree.roots.length === 0 && !tree.rootError);

onMounted(async () => {
  if (tree.rootLoaded) {
    await reloadOpen();
  } else {
    await loadRoot();
  }
});
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h2>ノート</h2>
      <div class="toolbar push-end">
        <button class="btn-secondary" type="button" :disabled="busy || pdfMode" @click="createRootFolder">フォルダ追加</button>
        <button
          class="btn-secondary"
          :class="{ 'is-pressed': editMode }"
          type="button"
          aria-label="編集モード"
          :aria-pressed="editMode"
          :disabled="pdfMode"
          @click="toggleEdit"
        >
          <Icon name="edit" />
        </button>
        <button
          class="btn-secondary"
          :class="{ 'is-pressed': pdfMode }"
          type="button"
          :aria-pressed="pdfMode"
          :disabled="editMode"
          @click="togglePdfMode"
        >
          PDF 出力
        </button>
        <label class="check">
          <input type="checkbox" :checked="tree.showDeleted" @change="onShowDeleted" />
          削除済みを表示
        </label>
      </div>
    </div>
    <p v-if="success" class="msg-success" role="status">{{ success }}</p>
    <p v-if="error || tree.rootError" class="msg-error" role="alert">{{ error || tree.rootError }}</p>
    <p v-if="pdfMode" class="caption">ファイルを選ぶと、選んだ順に PDF へ連結します。</p>

    <div class="page-body">
      <p v-if="tree.rootLoading && !tree.rootLoaded" class="centered">読み込み中…</p>
      <p v-else-if="isEmpty" class="centered">データがありません</p>
      <ul v-else class="tree-list">
        <TreeNode v-for="folder in tree.roots" :key="folder.id" :folder="folder" :depth="0" :parent-id="null" :siblings="tree.roots" />
      </ul>

      <section v-if="pdfMode" class="pdf-panel">
        <p v-if="pdfError" class="msg-error" role="alert">{{ pdfError }}</p>
        <h3>出力するファイル（{{ pdfSelected.length }} 件）</h3>
        <p v-if="pdfSelected.length === 0" class="muted">一覧からファイルを選択してください。</p>
        <ol v-else class="pdf-list">
          <li v-for="(item, index) in pdfSelected" :key="item.fileId">
            <span class="pdf-label"><span class="muted">{{ index + 1 }}.</span> {{ item.folderName }} / {{ item.title }}</span>
            <span class="tree-actions">
              <button class="btn-secondary" type="button" :disabled="index === 0" @click="movePdf(index, -1)">上へ</button>
              <button class="btn-secondary" type="button" :disabled="index === pdfSelected.length - 1" @click="movePdf(index, 1)">下へ</button>
              <button class="btn-secondary" type="button" @click="removePdf(item.fileId)">除外</button>
            </span>
          </li>
        </ol>
        <label class="check"><input v-model="pageBreak" type="checkbox" /> ファイルごとに改ページ</label>
        <div>
          <button class="btn-primary" type="button" :disabled="pdfSelected.length === 0 || exporting" @click="exportPdf">
            {{ exporting ? "準備中…" : "PDF に出力" }}
          </button>
        </div>
      </section>
    </div>

    <NameDialog
      v-if="nameDialog"
      :title="nameDialog.title"
      :label="nameDialog.label"
      :initial="nameDialog.initial"
      :busy="dialogBusy"
      :error="dialogError"
      @save="onSaveName"
      @cancel="closeDialogs"
    />
    <ConfirmDialog
      v-if="confirming"
      :title="confirming.kind === 'folder' ? 'フォルダの削除' : 'ファイルの削除'"
      :message="
        confirming.kind === 'folder'
          ? `「${confirming.name}」を削除します。中のフォルダ・ファイルも、表示されなくなります。よろしいですか？`
          : `「${confirming.name}」を削除します。よろしいですか？`
      "
      confirm-label="削除"
      danger
      @confirm="onConfirmDelete"
      @cancel="confirming = null"
    />
    <FolderPicker
      v-if="moving"
      :title="`「${moving.name}」の移動先`"
      :moving-folder-id="moving.kind === 'folder' ? moving.id : null"
      :current-parent-id="moving.currentParentId"
      :allow-root="moving.kind === 'folder'"
      :busy="dialogBusy"
      :error="dialogError"
      @pick="onPickDestination"
      @cancel="closeDialogs"
    />

    <Teleport to="body">
      <div v-if="printFiles.length > 0" class="print-only" aria-hidden="true">
        <PrintDocument :files="printFiles" :page-break="pageBreak" @ready="onPrintReady" />
      </div>
    </Teleport>
  </section>
</template>
