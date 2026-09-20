<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { createSeries, errorMessage, listSeries } from "../api";
import Icon from "../components/Icon.vue";
import Pagination from "../components/Pagination.vue";
import type { Pagination as PaginationInfo, Series } from "../types";
import { formatDateTime } from "../utils/format";

const router = useRouter();

const items = ref<Series[]>([]);
const pagination = ref<PaginationInfo | null>(null);
const loading = ref(true);
const error = ref("");
const query = ref("");
const appliedQuery = ref("");
const page = ref(1);

const showForm = ref(false);
const title = ref("");
const description = ref("");
const formError = ref("");
const saving = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const result = await listSeries(page.value, appliedQuery.value || undefined);
    items.value = result.items;
    pagination.value = result.pagination;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}

function search(): void {
  appliedQuery.value = query.value.trim();
  page.value = 1;
  void load();
}

function clearSearch(): void {
  query.value = "";
  search();
}

function changePage(next: number): void {
  page.value = next;
  void load();
}

function openForm(): void {
  title.value = "";
  description.value = "";
  formError.value = "";
  showForm.value = true;
}

async function save(): Promise<void> {
  const trimmed = title.value.trim();
  if (!trimmed || trimmed.length > 500) {
    formError.value = "タイトルは 1〜500 文字で入力してください";
    return;
  }
  saving.value = true;
  formError.value = "";
  try {
    await createSeries(trimmed, description.value.trim());
    showForm.value = false;
    page.value = 1;
    await load();
  } catch (e) {
    formError.value = errorMessage(e);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h2>作品</h2>
      <button class="btn-primary push-end" type="button" aria-label="新規" @click="openForm">
        <Icon name="plus" />
      </button>
    </div>
    <form class="search" role="search" @submit.prevent="search">
      <input v-model="query" type="search" placeholder="タイトルで検索" aria-label="タイトルで検索" />
      <button class="btn-secondary" type="submit">検索</button>
      <button class="btn-text" type="button" aria-label="クリア" :disabled="!query && !appliedQuery" @click="clearSearch">
        <Icon name="close" />
      </button>
    </form>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="items.length === 0" class="centered">
        {{ appliedQuery ? "該当するデータがありません" : "データがありません" }}
      </p>
      <ul v-else class="rows">
        <li v-for="series in items" :key="series.id" class="row">
          <button class="row-button" type="button" @click="router.push(`/series/${series.id}`)">
            <span class="row-title">{{ series.title }}</span>
            <span v-if="series.description" class="caption clamp">{{ series.description }}</span>
            <span class="caption">{{ formatDateTime(series.created_at) }}</span>
          </button>
        </li>
      </ul>
    </div>
    <div class="page-foot">
      <Pagination :pagination="pagination" :disabled="loading" @change="changePage" />
    </div>

    <div v-if="showForm" class="modal-back">
      <form class="modal" @submit.prevent="save">
        <h3>作品の登録</h3>
        <p v-if="formError" class="msg-error">{{ formError }}</p>
        <div class="field">
          <label for="series-title">タイトル</label>
          <input id="series-title" v-model="title" type="text" maxlength="500" :disabled="saving" />
        </div>
        <div class="field">
          <label for="series-desc">説明</label>
          <textarea id="series-desc" v-model="description" :disabled="saving"></textarea>
        </div>
        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="saving" @click="showForm = false">
            <Icon name="close" />
          </button>
          <button class="btn-primary" type="submit" aria-label="保存" :disabled="saving">
            <Icon name="check" />
          </button>
        </div>
      </form>
    </div>
  </section>
</template>
