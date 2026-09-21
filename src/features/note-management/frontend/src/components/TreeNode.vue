<script setup lang="ts">
import { computed, inject } from "vue";
import { toggleFolder, tree } from "../composables/treeStore";
import { treeActionsKey } from "../composables/treeActions";
import type { FileSummary, Folder } from "../types";
import Icon from "./Icon.vue";

// ツリーの 1 つのフォルダと、開いているときはその直下（フォルダ、続いてファイル）。自分自身を再帰で使う。
const props = defineProps<{
  folder: Folder;
  depth: number;
  parentId: number | null;
  siblings: Folder[];
}>();

const actions = inject(treeActionsKey);
if (!actions) {
  throw new Error("treeActions が提供されていません");
}

const expanded = computed(() => Boolean(tree.expanded[props.folder.id]));
const state = computed(() => tree.children[props.folder.id]);
const hidden = computed(() => props.folder.is_deleted || props.folder.ancestor_deleted);
const indent = computed(() => ({ paddingLeft: `${props.depth * 16 + 8}px` }));

/** 並び替えの相手は、隣りの、削除されていない項目 */
const liveSiblings = computed(() => props.siblings.filter((f) => !f.is_deleted && !f.ancestor_deleted));
const folderIndex = computed(() => liveSiblings.value.findIndex((f) => f.id === props.folder.id));

function moveFolder(delta: -1 | 1): void {
  const other = liveSiblings.value[folderIndex.value + delta];
  if (other) {
    actions!.swapFolders(props.parentId, props.folder, other);
  }
}

const liveFiles = computed(() => (state.value?.files ?? []).filter((f) => !f.is_deleted && !f.ancestor_deleted));

function fileIndex(file: FileSummary): number {
  return liveFiles.value.findIndex((f) => f.id === file.id);
}

function moveFile(file: FileSummary, delta: -1 | 1): void {
  const other = liveFiles.value[fileIndex(file) + delta];
  if (other) {
    actions!.swapFiles(props.folder.id, file, other);
  }
}

function isFileHidden(file: FileSummary): boolean {
  return file.is_deleted || file.ancestor_deleted;
}

function isSelected(file: FileSummary): boolean {
  return actions!.pdfSelected.value.some((item) => item.fileId === file.id);
}

function onFileClick(file: FileSummary): void {
  if (actions!.pdfMode.value) {
    if (!isFileHidden(file)) {
      actions!.togglePdf(file, props.folder.name);
    }
    return;
  }
  actions!.openFile(file.id);
}
</script>

<template>
  <li class="tree-node">
    <div class="tree-row folder-row" :class="{ 'is-deleted': hidden }" :style="indent">
      <button
        class="tree-toggle"
        type="button"
        :aria-label="expanded ? '閉じる' : '開く'"
        :aria-expanded="expanded"
        @click="toggleFolder(folder.id)"
      >
        <span class="chevron" :class="{ open: expanded }" aria-hidden="true"></span>
      </button>
      <button class="tree-name" type="button" @click="toggleFolder(folder.id)">{{ folder.name }}</button>
      <span v-if="folder.is_deleted" class="badge danger">削除済み</span>
      <span v-else-if="folder.ancestor_deleted" class="badge">上位が削除済み</span>
      <div class="tree-actions">
        <button v-if="folder.is_deleted" class="btn-secondary" type="button" :disabled="actions.busy.value" @click="actions.undeleteFolder(folder)">
          削除解除
        </button>
        <template v-else-if="!hidden && !actions.pdfMode.value && !actions.editMode.value">
          <button class="btn-secondary" type="button" :disabled="actions.busy.value" @click="actions.createFolder(folder.id)">フォルダ追加</button>
          <button class="btn-secondary" type="button" :disabled="actions.busy.value" @click="actions.createFile(folder.id)">ファイル追加</button>
        </template>
        <template v-else-if="!hidden && actions.editMode.value">
          <button class="btn-secondary" type="button" :disabled="actions.busy.value || folderIndex <= 0" @click="moveFolder(-1)">上へ</button>
          <button
            class="btn-secondary"
            type="button"
            :disabled="actions.busy.value || folderIndex < 0 || folderIndex >= liveSiblings.length - 1"
            @click="moveFolder(1)"
          >
            下へ
          </button>
          <button class="btn-secondary" type="button" aria-label="名前変更" :disabled="actions.busy.value" @click="actions.renameFolder(folder)">
            <Icon name="edit" />
          </button>
          <button class="btn-secondary" type="button" :disabled="actions.busy.value" @click="actions.moveFolder(folder)">移動</button>
          <button class="btn-secondary danger" type="button" aria-label="フォルダの削除" :disabled="actions.busy.value" @click="actions.deleteFolder(folder)">
            <Icon name="delete" />
          </button>
        </template>
      </div>
    </div>

    <ul v-if="expanded" class="tree-children">
      <li v-if="state?.loading" class="tree-note" :style="{ paddingLeft: `${(depth + 1) * 16 + 8}px` }">読み込み中…</li>
      <li v-else-if="state?.error" class="tree-note msg-error" :style="{ marginLeft: `${(depth + 1) * 16 + 8}px` }" role="alert">
        {{ state.error }}
      </li>
      <template v-else-if="state">
        <li
          v-if="state.folders.length === 0 && state.files.length === 0"
          class="tree-note"
          :style="{ paddingLeft: `${(depth + 1) * 16 + 8}px` }"
        >
          データがありません
        </li>
        <TreeNode
          v-for="child in state.folders"
          :key="`d${child.id}`"
          :folder="child"
          :depth="depth + 1"
          :parent-id="folder.id"
          :siblings="state.folders"
        />
        <li
          v-for="file in state.files"
          :key="`f${file.id}`"
          class="tree-row file-row"
          :class="{ 'is-deleted': isFileHidden(file), 'is-picked': actions.pdfMode.value && isSelected(file) }"
          :style="{ paddingLeft: `${(depth + 1) * 16 + 8}px` }"
        >
          <input
            v-if="actions.pdfMode.value && !isFileHidden(file)"
            type="checkbox"
            class="tree-check"
            :checked="isSelected(file)"
            :aria-label="`${file.title} を PDF 出力に含める`"
            @change="onFileClick(file)"
          />
          <button class="tree-name" type="button" @click="onFileClick(file)">{{ file.title }}</button>
          <span v-if="file.is_deleted" class="badge danger">削除済み</span>
          <span v-else-if="file.ancestor_deleted" class="badge">上位が削除済み</span>
          <div class="tree-actions">
            <button v-if="file.is_deleted" class="btn-secondary" type="button" :disabled="actions.busy.value" @click="actions.undeleteFile(file)">
              削除解除
            </button>
            <template v-else-if="!isFileHidden(file) && actions.editMode.value">
              <button class="btn-secondary" type="button" :disabled="actions.busy.value || fileIndex(file) <= 0" @click="moveFile(file, -1)">上へ</button>
              <button
                class="btn-secondary"
                type="button"
                :disabled="actions.busy.value || fileIndex(file) >= liveFiles.length - 1"
                @click="moveFile(file, 1)"
              >
                下へ
              </button>
              <button class="btn-secondary" type="button" aria-label="タイトル変更" :disabled="actions.busy.value" @click="actions.renameFile(file)">
                <Icon name="edit" />
              </button>
              <button class="btn-secondary" type="button" :disabled="actions.busy.value" @click="actions.moveFile(file)">移動</button>
              <button class="btn-secondary danger" type="button" aria-label="ファイルの削除" :disabled="actions.busy.value" @click="actions.deleteFile(file)">
                <Icon name="delete" />
              </button>
            </template>
          </div>
        </li>
      </template>
    </ul>
  </li>
</template>
