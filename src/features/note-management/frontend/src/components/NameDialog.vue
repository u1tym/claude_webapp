<script setup lang="ts">
import { ref } from "vue";
import Icon from "./Icon.vue";

// 名前（フォルダ名・ファイルのタイトル）の入力ダイアログ。背景を押しても閉じない。
// 保存は親が行い、失敗したときは、error に文言を渡す（ダイアログは閉じない）。
const props = defineProps<{
  title: string;
  label: string;
  initial: string;
  busy: boolean;
  error: string;
}>();

const emit = defineEmits<{ save: [value: string]; cancel: [] }>();

const value = ref(props.initial);
const localError = ref("");

function submit(): void {
  localError.value = "";
  if (value.value.trim() === "") {
    localError.value = `${props.label}を入力してください`;
    return;
  }
  emit("save", value.value.trim());
}
</script>

<template>
  <div class="modal-back">
    <form class="modal" role="dialog" aria-modal="true" :aria-label="title" @submit.prevent="submit">
      <h3>{{ title }}</h3>
      <p v-if="localError || error" class="msg-error" role="alert">{{ localError || error }}</p>
      <div class="field">
        <label for="name-dialog-input">{{ label }}</label>
        <input id="name-dialog-input" v-model="value" type="text" :disabled="busy" autofocus />
      </div>
      <div class="actions actions-end">
        <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="emit('cancel')">
          <Icon name="close" />
        </button>
        <button class="btn-primary" type="submit" aria-label="保存" :disabled="busy">
          <Icon name="check" />
        </button>
      </div>
    </form>
  </div>
</template>
