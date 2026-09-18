<script setup lang="ts">
import { inject, onMounted, ref } from "vue";
import { AuthError, getStatus, startPower } from "../api";

const onAuthError = inject<(error: unknown) => void>("onAuthError");
const loading = ref(true);
const starting = ref(false);
const isUp = ref<boolean | null>(null);
const error = ref("");
const success = ref("");
const confirmOpen = ref(false);

async function handleAuth(exc: unknown): Promise<boolean> {
  if (exc instanceof AuthError) {
    onAuthError?.(exc);
    return true;
  }
  return false;
}

async function loadStatus(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    isUp.value = await getStatus();
  } catch (exc) {
    if (await handleAuth(exc)) {
      return;
    }
    error.value = "状態を取得できませんでした";
  } finally {
    loading.value = false;
  }
}

async function runStart(confirmed: boolean): Promise<void> {
  starting.value = true;
  error.value = "";
  success.value = "";
  try {
    await startPower(confirmed);
    success.value = "起動を指示しました";
    window.setTimeout(() => {
      success.value = "";
    }, 4000);
  } catch (exc) {
    if (await handleAuth(exc)) {
      return;
    }
    error.value = "実行できませんでした";
  } finally {
    starting.value = false;
  }
}

function onStartClick(): void {
  if (isUp.value === null || starting.value || loading.value) {
    return;
  }
  if (isUp.value) {
    confirmOpen.value = true;
    return;
  }
  void runStart(false);
}

function onConfirm(): void {
  confirmOpen.value = false;
  void runStart(true);
}

function onCancel(): void {
  confirmOpen.value = false;
}

onMounted(() => {
  void loadStatus();
});
</script>

<template>
  <div class="power-page">
    <div v-if="loading" class="loading">読み込み中…</div>
    <template v-else>
      <p v-if="error" class="msg-error">{{ error }}</p>
      <p v-if="success" class="msg-success">{{ success }}</p>
      <p v-if="starting" class="caption">起動を実行中…</p>
      <p v-if="isUp !== null" class="status-text">{{ isUp ? "起動済み" : "未起動" }}</p>
      <div class="actions">
        <button class="btn-secondary" type="button" :disabled="starting" @click="loadStatus">
          確認
        </button>
        <button
          v-if="isUp !== null"
          class="btn-primary"
          type="button"
          :disabled="starting"
          @click="onStartClick"
        >
          起動
        </button>
      </div>
    </template>
    <div v-if="confirmOpen" class="overlay" role="dialog" aria-modal="true">
      <div class="modal">
        <p>起動済みです。続けて起動しますか？</p>
        <div class="modal-actions">
          <button class="btn-primary" type="button" @click="onConfirm">起動</button>
          <button class="btn-secondary" type="button" @click="onCancel">キャンセル</button>
        </div>
      </div>
    </div>
  </div>
</template>
