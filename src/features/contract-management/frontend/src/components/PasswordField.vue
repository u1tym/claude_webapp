<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import CopyButton from "./CopyButton.vue";

const props = defineProps<{
  /** パスワードが設定されているか（一覧・詳細の応答の has_password） */
  hasPassword: boolean;
  /** パスワードの値を 1 件取得する。「表示」「コピー」を操作した時点で呼ぶ（一覧の応答には値が含まれない） */
  fetchPassword: () => Promise<string | null>;
}>();

const emit = defineEmits<{
  error: [error: unknown];
}>();

const MASK = "••••••••";
// 取得した値は、表示している間だけ保持する。隠したとき・この部品を離れるときに破棄する
const revealed = ref<string | null>(null);
const loading = ref(false);

async function toggle(): Promise<void> {
  if (revealed.value !== null) {
    revealed.value = null;
    return;
  }
  loading.value = true;
  try {
    revealed.value = (await props.fetchPassword()) ?? "";
  } catch (error) {
    emit("error", error);
  } finally {
    loading.value = false;
  }
}

async function valueToCopy(): Promise<string> {
  // マスク表示中でも、実際の値をコピーする。コピーのためだけに取得した値は、保持しない
  const text = revealed.value ?? (await props.fetchPassword());
  if (text === null) {
    throw new Error("password unset");
  }
  return text;
}

onBeforeUnmount(() => {
  revealed.value = null;
});
</script>

<template>
  <span v-if="!hasPassword" class="badge badge-warn">パスワード未設定</span>
  <span v-else class="password-field">
    <span class="password-value" data-testid="password-value">{{ revealed !== null ? revealed : MASK }}</span>
    <button
      class="btn-text btn-compact"
      type="button"
      :aria-label="revealed !== null ? 'パスワードを隠す' : 'パスワードを表示'"
      :disabled="loading"
      @click="toggle"
    >
      {{ revealed !== null ? "隠す" : "表示" }}
    </button>
    <CopyButton :value="valueToCopy" label="パスワードをコピー" @error="(e) => emit('error', e)" />
  </span>
</template>
