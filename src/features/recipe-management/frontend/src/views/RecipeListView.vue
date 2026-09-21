<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { errorMessage, listRecipes } from "../api";
import Icon from "../components/Icon.vue";
import type { RecipeSummary } from "../types";

const router = useRouter();

const recipes = ref<RecipeSummary[]>([]);
const loading = ref(true);
const error = ref("");
// 削除後の一覧への遷移で、成功メッセージを数秒示す（history.state 経由）
const success = ref("");

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    recipes.value = (await listRecipes()).items;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  const state = window.history.state as { flash?: unknown } | null;
  if (state && typeof state.flash === "string") {
    success.value = state.flash;
    window.history.replaceState({ ...window.history.state, flash: undefined }, "");
    setTimeout(() => (success.value = ""), 3000);
  }
  void load();
});
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h2>レシピ</h2>
      <button class="btn-primary push-end" type="button" aria-label="新規" @click="router.push('/recipes/new')">
        <Icon name="plus" />
      </button>
    </div>
    <p v-if="success" class="msg-success" role="status">{{ success }}</p>
    <p v-if="error" class="msg-error" role="alert">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="recipes.length === 0 && !error" class="centered">データがありません</p>
      <ul v-else class="rows narrow">
        <li v-for="recipe in recipes" :key="recipe.id" class="row">
          <button class="row-button" type="button" @click="router.push(`/recipes/${recipe.id}`)">
            <span class="row-title">{{ recipe.name }}</span>
            <span class="row-meta">{{ recipe.kana }}</span>
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>
