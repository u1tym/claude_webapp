<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ApiError, errorMessage, getFile, swapParts } from "../api";
import Icon from "../components/Icon.vue";
import PartAddDialog from "../components/PartAddDialog.vue";
import PartContent from "../components/PartContent.vue";
import PartDialog from "../components/PartDialog.vue";
import PrintDocument from "../components/PrintDocument.vue";
import type { FileDetail, Part, PrintFile } from "../types";

const props = defineProps<{ id: string }>();
const router = useRouter();

const file = ref<FileDetail | null>(null);
const loading = ref(true);
const error = ref("");
const notFound = ref(false);
const showDeletedParts = ref(false);
const busy = ref(false);
const adding = ref(false);
const openedId = ref<number | null>(null);
const checklistRefresh = ref(0);

const fileId = computed(() => Number(props.id));
/** ファイル自身、または上位のフォルダが削除済み。内容の表示だけできる */
const fileDeleted = computed(() => Boolean(file.value && (file.value.is_deleted || file.value.ancestor_deleted)));
const editable = computed(() => !fileDeleted.value);
const opened = computed<Part | null>(() => file.value?.parts.find((p) => p.id === openedId.value) ?? null);

/** 並び替えの相手は、隣りの、削除されていないパーツ */
const liveParts = computed(() => (file.value?.parts ?? []).filter((p) => !p.is_deleted));

async function load(): Promise<void> {
  error.value = "";
  notFound.value = false;
  try {
    file.value = await getFile(fileId.value, showDeletedParts.value);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound.value = true;
    } else {
      error.value = errorMessage(e);
    }
  } finally {
    loading.value = false;
  }
}

async function swap(part: Part, delta: -1 | 1): Promise<void> {
  const index = liveParts.value.findIndex((p) => p.id === part.id);
  const other = liveParts.value[index + delta];
  if (!other) {
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await swapParts(part.id, other.id);
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}

function partIndex(part: Part): number {
  return liveParts.value.findIndex((p) => p.id === part.id);
}

async function onDone(): Promise<void> {
  openedId.value = null;
  adding.value = false;
  await load();
}

// ---- PDF 出力（このファイル 1 件） ---------------------------------------------------

const printFiles = ref<PrintFile[]>([]);
const exporting = ref(false);
let printReady: (() => void) | null = null;

async function exportPdf(): Promise<void> {
  if (!file.value || exporting.value) {
    return;
  }
  exporting.value = true;
  error.value = "";
  try {
    const detail = await getFile(fileId.value, false);
    const ready = new Promise<void>((resolve) => {
      printReady = resolve;
    });
    printFiles.value = [
      {
        fileId: detail.id,
        folderName: detail.folder.name,
        title: detail.title,
        parts: detail.parts.filter((p) => !p.is_deleted),
      },
    ];
    await ready;
    window.print();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    printFiles.value = [];
    printReady = null;
    exporting.value = false;
  }
}

onMounted(load);
watch(showDeletedParts, load);
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" @click="router.push('/')">
        <Icon name="back" />
      </button>
      <div v-if="file" class="title-block">
        <p class="caption">{{ file.folder.name }}</p>
        <h2>{{ file.title }}</h2>
      </div>
      <div v-if="file" class="toolbar push-end">
        <label class="check">
          <input v-model="showDeletedParts" type="checkbox" />
          削除済みのパーツを表示
        </label>
        <button class="btn-secondary" type="button" :disabled="exporting" @click="exportPdf">
          {{ exporting ? "準備中…" : "PDF 出力" }}
        </button>
      </div>
    </div>
    <p v-if="error" class="msg-error" role="alert">{{ error }}</p>
    <p v-if="fileDeleted" class="msg-notice" role="status">このファイルは削除済みです。内容の表示だけできます。</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="notFound" class="centered">ファイルが見つかりません</p>
      <template v-else-if="file">
        <p v-if="file.parts.length === 0" class="centered">データがありません</p>
        <ul v-else class="part-list">
          <li v-for="part in file.parts" :key="part.id" class="part-card" :class="{ 'is-deleted': part.is_deleted }">
            <div v-if="editable && !part.is_deleted" class="part-order">
              <button class="btn-secondary" type="button" :disabled="busy || partIndex(part) <= 0" @click="swap(part, -1)">上へ</button>
              <button
                class="btn-secondary"
                type="button"
                :disabled="busy || partIndex(part) >= liveParts.length - 1"
                @click="swap(part, 1)"
              >
                下へ
              </button>
            </div>
            <div class="part-body" role="button" tabindex="0" @click="openedId = part.id" @keydown.enter="openedId = part.id">
              <span v-if="part.is_deleted" class="badge danger">削除済み</span>
              <PartContent :part="part" :refresh="checklistRefresh" />
            </div>
          </li>
        </ul>
        <div v-if="editable" class="add-part">
          <button class="btn-secondary" type="button" @click="adding = true">パーツを追加</button>
        </div>
      </template>
    </div>

    <PartDialog
      v-if="opened"
      :key="opened.id"
      :part="opened"
      :editable="editable"
      :refresh="checklistRefresh"
      @close="openedId = null"
      @done="onDone"
      @checklist-changed="checklistRefresh += 1"
    />
    <PartAddDialog v-if="adding && file" :file-id="file.id" @close="adding = false" @done="onDone" />

    <Teleport to="body">
      <div v-if="printFiles.length > 0" class="print-only" aria-hidden="true">
        <PrintDocument :files="printFiles" :page-break="false" @ready="printReady?.()" />
      </div>
    </Teleport>
  </section>
</template>
