<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { errorMessage, getChecklist } from "../api";
import type { Checklist } from "../types";

// チェックリストの表示（チェックの状態は、この画面では操作できない）。refresh が変わったら、取得し直す。
const props = defineProps<{ checklistId: number; refresh?: number }>();
const emit = defineEmits<{ ready: [] }>();

const state = ref<Checklist | null>(null);
const error = ref("");
const loading = ref(true);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    state.value = await getChecklist(props.checklistId);
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
    emit("ready");
  }
}

onMounted(load);
watch(() => [props.checklistId, props.refresh], load);
</script>

<template>
  <div class="checklist-view">
    <p v-if="loading && !state" class="muted">読み込み中…</p>
    <p v-else-if="error" class="msg-error" role="alert">{{ error }}</p>
    <template v-else-if="state">
      <p v-if="state.title" class="checklist-title">{{ state.title }}</p>
      <p v-if="state.categories.length === 0" class="muted">項目はありません</p>
      <section v-for="category in state.categories" :key="category.id" class="checklist-category">
        <h4 v-if="!category.is_unnamed">{{ category.name }}</h4>
        <ul class="checklist-items">
          <li v-for="item in category.items" :key="item.id" :class="{ checked: item.is_checked }">
            <input type="checkbox" :checked="item.is_checked" disabled :aria-label="item.title || '項目'" />
            <span>{{ item.title }}</span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>
