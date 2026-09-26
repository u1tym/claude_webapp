<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { ApiError, revokeApiKey, type ApiKeyItem } from "../api/client";
import Icon from "./Icon.vue";

const props = defineProps<{ target: ApiKeyItem }>();
const emit = defineEmits<{
  cancel: [];
  revoked: [];
}>();

const error = ref("");
const sending = ref(false);
const cancelButton = ref<HTMLButtonElement | null>(null);

onMounted(async () => {
  await nextTick();
  cancelButton.value?.focus();
});

async function submit(): Promise<void> {
  error.value = "";
  sending.value = true;
  try {
    await revokeApiKey(props.target.id);
    emit("revoked");
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401)) {
      error.value = "API キーを失効できませんでした。";
    }
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <div class="overlay">
    <div class="dialog" role="alertdialog" aria-modal="true" aria-labelledby="revoke-title">
      <h2 id="revoke-title" class="title">API キーの失効</h2>
      <p v-if="error" class="message message-error" role="alert">{{ error }}</p>
      <p class="confirm">
        次の API キーを失効します。失効したキーは元に戻せず、このキーを使っている他システムは利用できなくなります。
      </p>
      <dl class="target">
        <dt class="caption">名前</dt>
        <dd>{{ target.name }}</dd>
        <dt class="caption">キー</dt>
        <dd class="mono">{{ target.key_prefix }}…</dd>
      </dl>
      <div class="dialog-actions">
        <button
          ref="cancelButton"
          type="button"
          class="btn btn-secondary"
          aria-label="キャンセル"
          :disabled="sending"
          @click="emit('cancel')"
        >
          <Icon name="close" />
        </button>
        <button
          type="button"
          class="btn btn-secondary btn-danger-text"
          aria-label="失効"
          :disabled="sending"
          @click="submit"
        >
          <Icon name="stop" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.confirm {
  margin: 0;
}

.target {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space) calc(var(--space) * 2);
  margin: 0;
}

.target dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
