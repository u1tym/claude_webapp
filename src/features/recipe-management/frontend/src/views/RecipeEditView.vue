<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ApiError, errorMessage, getRecipe, updateRecipe } from "../api";
import Icon from "../components/Icon.vue";
import RecipeForm from "../components/RecipeForm.vue";
import { useOptions } from "../composables/useOptions";
import type { FormState, RecipeBody } from "../types";
import { formFromRecipe } from "../utils/recipeForm";

const props = defineProps<{ id: string }>();
const router = useRouter();
const { ingredients, measurements, loading: optionsLoading, error: optionsError, load, reload } = useOptions();

const form = ref<FormState | null>(null);
const loading = ref(true);
const loadError = ref("");
const notFound = ref(false);
const saving = ref(false);
const saveError = ref("");

async function submit(body: RecipeBody): Promise<void> {
  saving.value = true;
  saveError.value = "";
  try {
    const updated = await updateRecipe(Number(props.id), body);
    await router.push(`/recipes/${updated.id}`);
  } catch (e) {
    // 入力内容は残す
    saveError.value = errorMessage(e);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    const [recipe] = await Promise.all([getRecipe(Number(props.id)), load()]);
    form.value = formFromRecipe(recipe);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound.value = true;
    } else {
      loadError.value = errorMessage(e);
    }
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button
        class="btn-text"
        type="button"
        aria-label="戻る"
        :disabled="saving"
        @click="router.push(notFound ? '/' : `/recipes/${id}`)"
      >
        <Icon name="back" />
      </button>
      <h2>レシピ編集</h2>
    </div>
    <p v-if="loadError || optionsError" class="msg-error" role="alert">{{ loadError || optionsError }}</p>
    <p v-if="loading || optionsLoading" class="centered">読み込み中…</p>
    <p v-else-if="notFound" class="centered">レシピが見つかりません</p>
    <RecipeForm
      v-else-if="form"
      v-model="form"
      :ingredients="ingredients"
      :measurements="measurements"
      :saving="saving"
      :error="saveError"
      :reload-options="reload"
      @submit="submit"
      @cancel="router.push(`/recipes/${id}`)"
    />
  </section>
</template>
