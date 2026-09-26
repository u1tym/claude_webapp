<script setup lang="ts">
import { ref } from "vue";
import Icon from "./Icon.vue";

const props = defineProps<{ name: string; apiKey: string }>();
const emit = defineEmits<{ close: [] }>();

const copyMessage = ref("");
const copyFailed = ref(false);
const keyElement = ref<HTMLElement | null>(null);
let timer: number | undefined;

function selectAll(): void {
  const el = keyElement.value;
  const selection = window.getSelection();
  if (!el || !selection) {
    return;
  }
  const range = document.createRange();
  range.selectNodeContents(el);
  selection.removeAllRanges();
  selection.addRange(range);
}

async function copy(): Promise<void> {
  window.clearTimeout(timer);
  try {
    await navigator.clipboard.writeText(props.apiKey);
    copyFailed.value = false;
    copyMessage.value = "コピーしました";
    timer = window.setTimeout(() => (copyMessage.value = ""), 3000);
  } catch {
    copyFailed.value = true;
    copyMessage.value = "コピーできませんでした。キーを選択してコピーしてください。";
    selectAll();
  }
}
</script>

<template>
  <div class="overlay">
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="issued-title">
      <h2 id="issued-title" class="title">API キーを発行しました</h2>
      <p class="warning">
        このキーは今しか表示されません。閉じる前にコピーして、安全な場所に保管してください。
      </p>
      <div class="field">
        <span class="field-label">名前</span>
        <span class="name">{{ name }}</span>
      </div>
      <div class="field">
        <span class="field-label">API キー</span>
        <div
          ref="keyElement"
          class="key-value mono"
          tabindex="0"
          aria-label="発行した API キー"
          @click="selectAll"
          @focus="selectAll"
        >{{ apiKey }}</div>
        <div class="copy-row">
          <button type="button" class="btn btn-secondary" @click="copy">コピー</button>
          <span
            v-if="copyMessage"
            :class="copyFailed ? 'copy-error' : 'caption'"
            role="status"
          >{{ copyMessage }}</span>
        </div>
      </div>
      <p class="caption">
        他システムからは、要求ヘッダ <code class="mono">Authorization: Bearer &lt;キー&gt;</code> として送ってください。
      </p>
      <div class="dialog-actions">
        <button type="button" class="btn btn-primary" aria-label="閉じる" @click="emit('close')">
          <Icon name="close" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.warning {
  margin: 0;
  color: var(--color-danger);
}

.name {
  overflow-wrap: anywhere;
}

.key-value {
  padding: var(--space);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
  overflow-wrap: anywhere;
  user-select: all;
  cursor: text;
}

.copy-row {
  display: flex;
  align-items: center;
  gap: var(--space);
  flex-wrap: wrap;
}

.copy-error {
  color: var(--color-danger);
  font-size: 14px;
}
</style>
