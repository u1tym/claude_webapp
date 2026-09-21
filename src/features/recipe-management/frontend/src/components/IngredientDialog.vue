<script setup lang="ts">
import { ref } from "vue";
import { createIngredient, errorMessage } from "../api";
import type { Ingredient } from "../types";
import Icon from "./Icon.vue";

// 材料の追加ダイアログ。背景（オーバーレイ）を押しても閉じない。
// 保存が成功したら saved を出す（閉じるかどうかは呼び出し側が決める）。失敗したときは開いたまま、先頭にエラーを示す。
const emit = defineEmits<{ saved: [ingredient: Ingredient]; cancel: [] }>();

const name = ref("");
const kana = ref("");
const error = ref("");
const saving = ref(false);

async function submit(): Promise<void> {
  error.value = "";
  if (name.value.trim() === "") {
    error.value = "材料名を入力してください";
    return;
  }
  if (kana.value.trim() === "") {
    error.value = "かなを入力してください";
    return;
  }
  saving.value = true;
  try {
    emit("saved", await createIngredient(name.value.trim(), kana.value.trim()));
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="modal-back">
    <form class="modal" role="dialog" aria-modal="true" aria-label="材料の追加" @submit.prevent="submit">
      <h3>材料の追加</h3>
      <p v-if="error" class="msg-error">{{ error }}</p>
      <div class="field">
        <label for="ingredient-name">材料名</label>
        <input id="ingredient-name" v-model="name" type="text" :disabled="saving" />
      </div>
      <div class="field">
        <label for="ingredient-kana">かな</label>
        <input id="ingredient-kana" v-model="kana" type="text" :disabled="saving" />
      </div>
      <div class="actions actions-end">
        <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="saving" @click="emit('cancel')">
          <Icon name="close" />
        </button>
        <button class="btn-primary" type="submit" aria-label="保存" :disabled="saving">
          <Icon name="check" />
        </button>
      </div>
    </form>
  </div>
</template>
