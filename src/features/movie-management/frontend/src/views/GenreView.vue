<script setup lang="ts">
import { onMounted, ref } from "vue";
import { createGenre, errorMessage, listGenres } from "../api";
import Icon from "../components/Icon.vue";
import type { Genre } from "../types";

const genres = ref<Genre[]>([]);
const loading = ref(true);
const error = ref("");
const formError = ref("");
const success = ref("");
const name = ref("");
const sortOrder = ref(0);
const saving = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    genres.value = (await listGenres()).items;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  formError.value = "";
  success.value = "";
  const trimmed = name.value.trim();
  if (!trimmed || trimmed.length > 100) {
    formError.value = "ジャンル名は 1〜100 文字で入力してください";
    return;
  }
  if (!Number.isInteger(sortOrder.value) || sortOrder.value < 0) {
    formError.value = "表示順は 0 以上の整数で入力してください";
    return;
  }
  saving.value = true;
  try {
    await createGenre(trimmed, sortOrder.value);
    name.value = "";
    sortOrder.value = 0;
    success.value = "追加しました";
    setTimeout(() => (success.value = ""), 3000);
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
      <h2>ジャンル</h2>
    </div>
    <p class="caption">共通ジャンルに加え、独自のジャンルを追加できます。</p>
    <p v-if="success" class="msg-success">{{ success }}</p>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <form class="form-panel" @submit.prevent="submit">
      <p v-if="formError" class="msg-error">{{ formError }}</p>
      <div class="field-row">
        <div class="field">
          <label for="genre-name">ジャンル名</label>
          <input id="genre-name" v-model="name" type="text" maxlength="100" :disabled="saving" />
        </div>
        <div class="field">
          <label for="genre-order">表示順</label>
          <input id="genre-order" v-model.number="sortOrder" type="number" min="0" :disabled="saving" />
        </div>
      </div>
      <div class="actions actions-end">
        <button class="btn-primary" type="submit" aria-label="保存" :disabled="saving">
          <Icon name="check" />
        </button>
      </div>
    </form>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="genres.length === 0" class="centered">データがありません</p>
      <ul v-else class="rows">
        <li v-for="genre in genres" :key="genre.id" class="row">
          <span class="row-button row-title">{{ genre.name }}</span>
          <span class="badge" :class="{ primary: genre.is_system }">{{ genre.is_system ? "共通" : "独自" }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>
