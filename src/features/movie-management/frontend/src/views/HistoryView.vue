<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { errorMessage, listHistory } from "../api";
import Pagination from "../components/Pagination.vue";
import type { HistoryItem, Pagination as PaginationInfo } from "../types";
import { formatDateTime, formatMs, progressPercent } from "../utils/format";

const router = useRouter();

const items = ref<HistoryItem[]>([]);
const pagination = ref<PaginationInfo | null>(null);
const loading = ref(true);
const error = ref("");
const page = ref(1);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const result = await listHistory(page.value);
    items.value = result.items;
    pagination.value = result.pagination;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}

function changePage(next: number): void {
  page.value = next;
  void load();
}

onMounted(load);
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h2>視聴履歴</h2>
    </div>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="items.length === 0" class="centered">データがありません</p>
      <ul v-else class="rows">
        <li v-for="item in items" :key="item.video_id" class="row">
          <button class="row-button" type="button" @click="router.push(`/videos/${item.video_id}`)">
            <span class="row-title">{{ item.title }}</span>
            <span class="row-meta">
              <span>{{ formatMs(item.position_ms) }} / {{ formatMs(item.duration_ms) }}</span>
              <span v-if="item.completed" class="badge primary">視聴済み</span>
              <span>{{ formatDateTime(item.last_played_at) }}</span>
            </span>
            <span v-if="!item.completed" class="progress" aria-hidden="true">
              <span :style="{ width: `${progressPercent(item.position_ms, item.duration_ms)}%` }"></span>
            </span>
          </button>
        </li>
      </ul>
    </div>
    <div class="page-foot">
      <Pagination :pagination="pagination" :disabled="loading" @change="changePage" />
    </div>
  </section>
</template>
