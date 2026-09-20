<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { createPlaylist, errorMessage, listPlaylists } from "../api";
import Icon from "../components/Icon.vue";
import Pagination from "../components/Pagination.vue";
import type { Pagination as PaginationInfo, PlaylistSummary } from "../types";

const router = useRouter();

const items = ref<PlaylistSummary[]>([]);
const pagination = ref<PaginationInfo | null>(null);
const loading = ref(true);
const error = ref("");
const page = ref(1);

const showForm = ref(false);
const name = ref("");
const description = ref("");
const formError = ref("");
const saving = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const result = await listPlaylists(page.value);
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

function openForm(): void {
  name.value = "";
  description.value = "";
  formError.value = "";
  showForm.value = true;
}

async function save(): Promise<void> {
  const trimmed = name.value.trim();
  if (!trimmed || trimmed.length > 500) {
    formError.value = "名前は 1〜500 文字で入力してください";
    return;
  }
  saving.value = true;
  formError.value = "";
  try {
    const created = await createPlaylist(trimmed, description.value.trim());
    // 作成後は、動画を加えるために編集画面へ進む
    await router.push(`/playlists/${created.id}/edit`);
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
      <h2>プレイリスト</h2>
      <button class="btn-primary push-end" type="button" aria-label="新規" @click="openForm">
        <Icon name="plus" />
      </button>
    </div>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="items.length === 0" class="centered">データがありません</p>
      <ul v-else class="rows">
        <li v-for="playlist in items" :key="playlist.id" class="row">
          <div class="row-button">
            <span class="row-title">{{ playlist.name }}</span>
            <span v-if="playlist.description" class="caption clamp">{{ playlist.description }}</span>
            <span class="caption">{{ playlist.item_count }} 本</span>
          </div>
          <div class="row-side">
            <button
              class="btn-secondary"
              type="button"
              :disabled="playlist.item_count === 0"
              @click="router.push(`/playlists/${playlist.id}/play`)"
            >
              再生
            </button>
            <button class="btn-text" type="button" aria-label="編集" @click="router.push(`/playlists/${playlist.id}/edit`)">
              <Icon name="edit" />
            </button>
          </div>
        </li>
      </ul>
    </div>
    <div class="page-foot">
      <Pagination :pagination="pagination" :disabled="loading" @change="changePage" />
    </div>

    <div v-if="showForm" class="modal-back">
      <form class="modal" @submit.prevent="save">
        <h3>プレイリストの作成</h3>
        <p v-if="formError" class="msg-error">{{ formError }}</p>
        <div class="field">
          <label for="pl-name">名前</label>
          <input id="pl-name" v-model="name" type="text" maxlength="500" :disabled="saving" />
        </div>
        <div class="field">
          <label for="pl-desc">説明</label>
          <textarea id="pl-desc" v-model="description" :disabled="saving"></textarea>
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
