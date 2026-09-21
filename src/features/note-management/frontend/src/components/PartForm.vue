<script setup lang="ts">
import { computed, ref } from "vue";
import { partContentUrl } from "../api";
import type { PartType } from "../types";
import { formatByteSize, pickedFromFile } from "../utils/file";
import { changeDraftType, groupOf, isImageType, TYPE_OPTIONS, type PartDraft } from "../utils/partDraft";
import { renderMarkdown, renderTex } from "../utils/render";
import { clampImageScale } from "../utils/imageScale";
import ActionPlanEditor from "./ActionPlanEditor.vue";
import ImagePartView from "./ImagePartView.vue";

// パーツの種別の選択と、種別に応じた入力欄（追加・編集で共通）。
const props = defineProps<{
  /** 編集のとき、既存のパーツの識別子（画像の現在の内容を表示する） */
  partId: number | null;
  /** 既存のパーツの中身の版（差し替え後に、古い画像を使い続けないため） */
  version?: number;
  /** 種別の選択欄を無効にする（チェックリストのパーツの編集） */
  typeLocked: boolean;
  /** チェックリストを種別の選択肢に含める（追加のときだけ） */
  allowChecklist: boolean;
  busy: boolean;
}>();

const draft = defineModel<PartDraft>({ required: true });
const emit = defineEmits<{ error: [message: string] }>();

const fileInput = ref<HTMLInputElement | null>(null);
const reading = ref(false);

const options = computed(() =>
  TYPE_OPTIONS.filter((o) => (o.value === "checklist" ? props.allowChecklist || props.typeLocked : true)),
);
const group = computed(() => groupOf(draft.value.type));
const image = computed(() => isImageType(draft.value.type));

const previewHtml = computed(() => {
  if (draft.value.type === "md") {
    return renderMarkdown(draft.value.text);
  }
  if (draft.value.type === "tex") {
    return renderTex(draft.value.text);
  }
  return "";
});

const mime = computed(() => (draft.value.type === "jpeg" ? "image/jpeg" : "image/png"));

/** 画像の表示元。選んだファイルがあればそれ、なければ、保存済みの内容。 */
const imageSrc = computed(() => {
  if (draft.value.picked) {
    return `data:${mime.value};base64,${draft.value.picked.data}`;
  }
  return props.partId !== null ? partContentUrl(props.partId, false, props.version ?? 0) : "";
});

const scalePreview = computed(() => {
  const n = Number(draft.value.scalePercent);
  return Number.isFinite(n) ? clampImageScale(n / 100) : 1;
});

function onTypeChange(event: Event): void {
  changeDraftType(draft.value, (event.target as HTMLSelectElement).value as PartType);
}

async function onFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) {
    return;
  }
  reading.value = true;
  try {
    const result = await pickedFromFile(file);
    if ("error" in result) {
      emit("error", result.error);
      return;
    }
    draft.value.picked = result;
    // 画像を差し替えたときは、マーカーを空にする
    draft.value.markers = [];
  } finally {
    reading.value = false;
  }
}

const accept = computed(() => (draft.value.type === "jpeg" ? "image/jpeg" : draft.value.type === "png" ? "image/png" : "*/*"));
const shownName = computed(() => draft.value.picked?.filename ?? draft.value.existingFilename);
const shownSize = computed(() => (draft.value.picked ? draft.value.picked.size : draft.value.existingSize));
</script>

<template>
  <div class="part-form">
    <div class="field">
      <label for="part-type">種別</label>
      <select id="part-type" :value="draft.type" :disabled="busy || typeLocked" @change="onTypeChange">
        <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </div>

    <template v-if="group === 'text'">
      <div class="field">
        <label for="part-text">{{ draft.type === "url" ? "URL" : "内容" }}</label>
        <input v-if="draft.type === 'url'" id="part-text" v-model="draft.text" type="text" placeholder="https://..." :disabled="busy" />
        <textarea v-else id="part-text" v-model="draft.text" rows="8" placeholder="内容を入力" :disabled="busy"></textarea>
      </div>
      <div v-if="(draft.type === 'md' || draft.type === 'tex') && draft.text" class="part-preview">
        <p class="caption">プレビュー</p>
        <div :class="draft.type === 'md' ? 'md-view' : 'tex-view'" v-html="previewHtml"></div>
      </div>
    </template>

    <ActionPlanEditor v-else-if="group === 'action'" v-model="draft.action" />

    <p v-else-if="group === 'checklist'" class="muted">
      {{ partId === null ? "空のチェックリストを作成します。" : "チェックリストの項目は、この画面で編集します。" }}
    </p>

    <template v-else>
      <div class="file-pick">
        <button class="btn-secondary" type="button" :disabled="busy || reading" @click="fileInput?.click()">
          {{ reading ? "読み込み中…" : "ファイルを選択" }}
        </button>
        <input ref="fileInput" class="visually-hidden" type="file" :accept="accept" tabindex="-1" @change="onFile" />
        <span v-if="shownName" class="file-info">{{ shownName }}（{{ formatByteSize(shownSize) }}）</span>
        <span v-else class="muted">ファイルが選ばれていません</span>
      </div>
      <template v-if="image">
        <div class="field">
          <label for="part-title">タイトル（任意）</label>
          <input id="part-title" v-model="draft.title" type="text" :disabled="busy" />
        </div>
        <div class="field">
          <label for="part-scale">表示倍率（%）</label>
          <input id="part-scale" v-model="draft.scalePercent" type="number" min="25" max="400" step="5" inputmode="numeric" :disabled="busy" />
        </div>
        <ImagePartView
          v-if="imageSrc"
          v-model:markers="draft.markers"
          :src="imageSrc"
          :image-scale="scalePreview"
          editable
        />
      </template>
    </template>
  </div>
</template>
