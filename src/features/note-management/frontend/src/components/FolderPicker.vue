<script setup lang="ts">
import { onMounted, ref } from "vue";
import { errorMessage, listItems } from "../api";
import type { Folder } from "../types";
import Icon from "./Icon.vue";
import PickerNode from "./PickerNode.vue";

// 移動先の選択ダイアログ。フォルダの移動のときは「（ルート）」も選べ、自分自身と子孫は選べない。
// ファイルの移動のときは、ルートは選べない。現在の親も選べない。背景を押しても閉じない。
const props = defineProps<{
  title: string;
  /** 移動するフォルダ（ファイルの移動のときは null） */
  movingFolderId: number | null;
  /** 現在の親（ファイルは所属フォルダ。ルートは null） */
  currentParentId: number | null;
  allowRoot: boolean;
  busy: boolean;
  error: string;
}>();

const emit = defineEmits<{ pick: [parentId: number | null]; cancel: [] }>();

const roots = ref<Folder[]>([]);
const loading = ref(true);
const loadError = ref("");
/** 選択中（undefined は未選択、null はルート） */
const selected = ref<number | null | undefined>(undefined);

onMounted(async () => {
  try {
    roots.value = (await listItems(null, false)).folders;
  } catch (e) {
    loadError.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
});

function pick(id: number | null): void {
  selected.value = id;
}

const rootDisabled = () => !props.allowRoot || props.currentParentId === null;
</script>

<template>
  <div class="modal-back">
    <div class="modal picker" role="dialog" aria-modal="true" :aria-label="title">
      <h3>{{ title }}</h3>
      <p v-if="error || loadError" class="msg-error" role="alert">{{ error || loadError }}</p>
      <div class="picker-body">
        <p v-if="loading" class="centered">読み込み中…</p>
        <ul v-else class="tree-list">
          <li v-if="allowRoot">
            <div class="picker-row" :class="{ 'is-selected': selected === null }">
              <button class="tree-name" type="button" :disabled="rootDisabled()" @click="pick(null)">（ルート）</button>
            </div>
          </li>
          <li v-if="roots.length === 0 && !loadError" class="tree-note">データがありません</li>
          <PickerNode
            v-for="folder in roots"
            :key="folder.id"
            :folder="folder"
            :depth="0"
            :moving-id="movingFolderId"
            :blocked="false"
            :current-id="currentParentId"
            :selected-id="selected ?? null"
            @pick="pick"
          />
        </ul>
      </div>
      <div class="actions actions-end">
        <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="emit('cancel')">
          <Icon name="close" />
        </button>
        <button class="btn-primary" type="button" aria-label="決定" :disabled="busy || selected === undefined" @click="emit('pick', selected ?? null)">
          <Icon name="check" />
        </button>
      </div>
    </div>
  </div>
</template>
