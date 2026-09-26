<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { ApiError, issueApiKey, type IssuedApiKey } from "../api/client";
import { localInputToIso } from "../format";
import Icon from "./Icon.vue";

const emit = defineEmits<{
  cancel: [];
  issued: [issued: IssuedApiKey];
}>();

const name = ref("");
const expiresAt = ref("");
const error = ref("");
const sending = ref(false);
const nameInput = ref<HTMLInputElement | null>(null);

onMounted(async () => {
  await nextTick();
  nameInput.value?.focus();
});

function validate(): string {
  if (name.value.trim() === "") {
    return "名前を入力してください。";
  }
  if (expiresAt.value !== "" && new Date(expiresAt.value).getTime() <= Date.now()) {
    return "有効期限には未来の日時を指定してください。";
  }
  return "";
}

async function submit(): Promise<void> {
  error.value = validate();
  if (error.value) {
    return;
  }
  sending.value = true;
  try {
    const issued = await issueApiKey(
      name.value.trim(),
      expiresAt.value === "" ? null : localInputToIso(expiresAt.value),
    );
    emit("issued", issued);
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401)) {
      error.value = "API キーを発行できませんでした。";
    }
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <div class="overlay">
    <form class="dialog" role="dialog" aria-modal="true" aria-labelledby="issue-title" @submit.prevent="submit">
      <h2 id="issue-title" class="title">API キーの発行</h2>
      <p v-if="error" class="message message-error" role="alert">{{ error }}</p>
      <label class="field">
        <span class="field-label">名前</span>
        <input
          ref="nameInput"
          v-model="name"
          class="input"
          type="text"
          maxlength="100"
          placeholder="例: 家計簿連携"
          required
        />
      </label>
      <label class="field">
        <span class="field-label">有効期限（任意）</span>
        <input v-model="expiresAt" class="input" type="datetime-local" />
        <span class="caption">空欄のときは無期限になります。</span>
      </label>
      <div class="dialog-actions">
        <button
          type="button"
          class="btn btn-secondary"
          aria-label="キャンセル"
          :disabled="sending"
          @click="emit('cancel')"
        >
          <Icon name="close" />
        </button>
        <button type="submit" class="btn btn-primary" aria-label="発行" :disabled="sending">
          <Icon name="check" />
        </button>
      </div>
    </form>
  </div>
</template>
