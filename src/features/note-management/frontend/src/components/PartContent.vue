<script setup lang="ts">
import { computed } from "vue";
import { partContentUrl } from "../api";
import type { Part } from "../types";
import { formatByteSize } from "../utils/file";
import { contentVersion } from "../utils/partDraft";
import { renderMarkdown, renderTex, safeHttpUrl } from "../utils/render";
import ActionPlanView from "./ActionPlanView.vue";
import ChecklistView from "./ChecklistView.vue";
import ImagePartView from "./ImagePartView.vue";

// パーツの種別に応じた表示（カード・ダイアログ・印刷用のレイアウトで共通）。
const props = defineProps<{
  part: Part;
  /** ファイル名と大きさも示す（ダイアログ・印刷） */
  detailed?: boolean;
  /** チェックリストを取得し直すための値 */
  refresh?: number;
}>();

const emit = defineEmits<{ ready: [] }>();

const html = computed(() => {
  if (props.part.type === "md") {
    return renderMarkdown(props.part.data);
  }
  if (props.part.type === "tex") {
    return renderTex(props.part.data);
  }
  return "";
});

const link = computed(() => (props.part.type === "url" ? safeHttpUrl(props.part.data) : null));
const isImage = computed(() => props.part.type === "jpeg" || props.part.type === "png");
</script>

<template>
  <div class="part-content" :data-type="part.type">
    <pre v-if="part.type === 'text'" class="part-text">{{ part.data }}</pre>
    <div v-else-if="part.type === 'md'" class="md-view" v-html="html"></div>
    <div v-else-if="part.type === 'tex'" class="tex-view" v-html="html"></div>
    <template v-else-if="part.type === 'url'">
      <a v-if="link" :href="link" target="_blank" rel="noopener noreferrer" class="part-url">{{ part.data }}</a>
      <span v-else class="part-url">{{ part.data }}</span>
    </template>
    <ActionPlanView v-else-if="part.type === 'action'" :data="part.data" />
    <ChecklistView
      v-else-if="part.type === 'checklist' && part.checklist_id !== null"
      :checklist-id="part.checklist_id"
      :refresh="refresh"
      @ready="emit('ready')"
    />
    <ImagePartView
      v-else-if="isImage"
      :src="partContentUrl(part.id, false, contentVersion(part))"
      :title="part.title"
      :filename="part.filename"
      :show-filename="detailed"
      :markers="part.markers"
      :image-scale="part.image_scale"
    />
    <div v-else-if="part.type === 'binary'" class="binary-view">
      <span class="binary-name">{{ part.filename || "（名前なし）" }}</span>
      <span v-if="detailed" class="caption">{{ formatByteSize(part.byte_size) }}</span>
    </div>
  </div>
</template>
