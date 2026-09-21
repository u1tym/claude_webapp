<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ApiError, deleteRecipe, errorMessage, getRecipe } from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Icon from "../components/Icon.vue";
import type { RecipeDetail } from "../types";
import { formatAmount } from "../utils/measure";

const props = defineProps<{ id: string }>();
const router = useRouter();

const recipe = ref<RecipeDetail | null>(null);
const loading = ref(true);
const error = ref("");
const notFound = ref(false);
const confirming = ref(false);
const deleting = ref(false);

// 全工程の材料を、工程の順、工程内の並びの順に並べる
const allItems = computed(() => recipe.value?.steps.flatMap((step) => step.items) ?? []);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  notFound.value = false;
  try {
    recipe.value = await getRecipe(Number(props.id));
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

async function remove(): Promise<void> {
  deleting.value = true;
  try {
    await deleteRecipe(Number(props.id));
    await router.push({ path: "/", state: { flash: "削除しました" } });
  } catch (e) {
    // 失敗したときは、ダイアログを閉じて、エラーメッセージを示す
    confirming.value = false;
    error.value = errorMessage(e);
  } finally {
    deleting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" @click="router.push('/')">
        <Icon name="back" />
      </button>
      <h2 v-if="recipe">
        {{ recipe.name }}
        <span class="caption">{{ recipe.kana }}</span>
      </h2>
      <div v-if="recipe" class="actions push-end">
        <button class="btn-secondary" type="button" aria-label="編集" @click="router.push(`/recipes/${id}/edit`)">
          <Icon name="edit" />
        </button>
        <button class="btn-secondary danger" type="button" aria-label="削除" @click="confirming = true">
          <Icon name="delete" />
        </button>
      </div>
    </div>
    <p v-if="error" class="msg-error" role="alert">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="notFound" class="centered">レシピが見つかりません</p>
      <div v-else-if="recipe" class="detail">
        <section v-if="allItems.length > 0" class="card">
          <h3>材料</h3>
          <ul class="ingredient-list">
            <li v-for="(item, i) in allItems" :key="i">
              <span>{{ item.ingredient.name }}</span>
              <span class="muted">{{ formatAmount(item.measurement, item.amount) }}</span>
            </li>
          </ul>
        </section>

        <section v-for="step in recipe.steps" :key="step.step_no" class="card">
          <h3>手順 {{ step.step_no }}</h3>
          <p class="description">{{ step.description }}</p>
          <ul v-if="step.items.length > 0" class="ingredient-list">
            <li v-for="item in step.items" :key="item.item_no">
              <span>{{ item.ingredient.name }}</span>
              <span class="muted">{{ formatAmount(item.measurement, item.amount) }}</span>
            </li>
          </ul>
        </section>
      </div>
    </div>

    <ConfirmDialog
      v-if="confirming && recipe"
      title="レシピの削除"
      :message="`「${recipe.name}」を削除します。よろしいですか？`"
      confirm-label="削除"
      danger
      :busy="deleting"
      @confirm="remove"
      @cancel="confirming = false"
    />
  </section>
</template>
