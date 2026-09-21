<script setup lang="ts">
import { ref } from "vue";
import { errorMessage, listItems } from "../api";
import type { Folder } from "../types";

// 移動先の選択のツリーの 1 行と、その直下（開いたとき取得する）。自分自身を再帰で使う。
const props = defineProps<{
  folder: Folder;
  depth: number;
  /** 移動するフォルダ（フォルダの移動のとき）。これと、その子孫は、選べない */
  movingId: number | null;
  /** 上位に、移動するフォルダがある（この行も選べない） */
  blocked: boolean;
  /** 現在の親（選べない） */
  currentId: number | null;
  selectedId: number | null;
}>();

const emit = defineEmits<{ pick: [id: number] }>();

const open = ref(false);
const loading = ref(false);
const error = ref("");
const children = ref<Folder[] | null>(null);

const disabledSelf = () => props.blocked || props.folder.id === props.movingId || props.folder.id === props.currentId;

async function toggle(): Promise<void> {
  open.value = !open.value;
  if (open.value && children.value === null) {
    loading.value = true;
    error.value = "";
    try {
      children.value = (await listItems(props.folder.id, false)).folders;
    } catch (e) {
      error.value = errorMessage(e);
      open.value = false;
    } finally {
      loading.value = false;
    }
  }
}
</script>

<template>
  <li>
    <div class="picker-row" :class="{ 'is-selected': selectedId === folder.id }" :style="{ paddingLeft: `${depth * 16 + 8}px` }">
      <button class="tree-toggle" type="button" :aria-label="open ? '閉じる' : '開く'" :aria-expanded="open" @click="toggle">
        <span class="chevron" :class="{ open }" aria-hidden="true"></span>
      </button>
      <button class="tree-name" type="button" :disabled="disabledSelf()" @click="emit('pick', folder.id)">{{ folder.name }}</button>
    </div>
    <ul v-if="open" class="tree-children">
      <li v-if="loading" class="tree-note" :style="{ paddingLeft: `${(depth + 1) * 16 + 8}px` }">読み込み中…</li>
      <li v-else-if="error" class="tree-note msg-error" role="alert">{{ error }}</li>
      <template v-else-if="children">
        <li v-if="children.length === 0" class="tree-note" :style="{ paddingLeft: `${(depth + 1) * 16 + 8}px` }">データがありません</li>
        <PickerNode
          v-for="child in children"
          :key="child.id"
          :folder="child"
          :depth="depth + 1"
          :moving-id="movingId"
          :blocked="blocked || folder.id === movingId"
          :current-id="currentId"
          :selected-id="selectedId"
          @pick="(id: number) => emit('pick', id)"
        />
      </template>
    </ul>
  </li>
</template>
