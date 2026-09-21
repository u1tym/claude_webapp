<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { createRecipe, errorMessage } from "../api";
import Icon from "../components/Icon.vue";
import RecipeForm from "../components/RecipeForm.vue";
import { useOptions } from "../composables/useOptions";
import type { FormState, RecipeBody } from "../types";
import { emptyForm } from "../utils/recipeForm";

const router = useRouter();
const { ingredients, measurements, loading, error: optionsError, load, reload } = useOptions();

const form = ref<FormState | null>(null);
const saving = ref(false);
const saveError = ref("");

async function submit(body: RecipeBody): Promise<void> {
  saving.value = true;
  saveError.value = "";
  try {
    const created = await createRecipe(body);
    await router.push(`/recipes/${created.id}`);
  } catch (e) {
    // 入力内容は残す
    saveError.value = errorMessage(e);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await load();
  form.value = emptyForm(measurements.value);
});
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" :disabled="saving" @click="router.push('/')">
        <Icon name="back" />
      </button>
      <h2>レシピ登録</h2>
    </div>
    <p v-if="optionsError" class="msg-error" role="alert">{{ optionsError }}</p>
    <p v-if="loading" class="centered">選択肢を準備中…</p>
    <RecipeForm
      v-else-if="form"
      v-model="form"
      :ingredients="ingredients"
      :measurements="measurements"
      :saving="saving"
      :error="saveError"
      :reload-options="reload"
      @submit="submit"
      @cancel="router.push('/')"
    />
  </section>
</template>
