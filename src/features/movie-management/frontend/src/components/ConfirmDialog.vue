<script setup lang="ts">
import Icon from "./Icon.vue";

// 背景（オーバーレイ）を押しても閉じない。閉じるのは、実行ボタンとキャンセルだけ。
defineProps<{
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
}>();

const emit = defineEmits<{ confirm: []; cancel: [] }>();
</script>

<template>
  <div class="modal-back">
    <div class="modal" role="dialog" aria-modal="true" :aria-label="title">
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
      <div class="actions actions-end">
        <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="emit('cancel')">
          <Icon name="close" />
        </button>
        <button
          :class="danger ? 'btn-secondary danger' : 'btn-primary'"
          type="button"
          :disabled="busy"
          @click="emit('confirm')"
        >
          {{ confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
