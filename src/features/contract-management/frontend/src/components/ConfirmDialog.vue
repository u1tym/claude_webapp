<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import Icon from "./Icon.vue";

defineProps<{
  /** ダイアログの見出し（読み上げ用） */
  title: string;
  message: string;
  /** 添える一文（任意） */
  note?: string;
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();

const cancelButton = ref<HTMLButtonElement | null>(null);

// 誤操作を避けるため、最初のフォーカスは「キャンセル」に置く
onMounted(async () => {
  await nextTick();
  cancelButton.value?.focus();
});
</script>

<template>
  <!-- 背景（オーバーレイ）を押しても閉じない。閉じるのは、ダイアログ内のボタンと Esc だけ -->
  <div class="dialog-overlay">
    <div
      class="dialog"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      @keydown.esc.prevent.stop="emit('cancel')"
    >
      <p class="dialog-message">{{ message }}</p>
      <p v-if="note" class="dialog-note">{{ note }}</p>
      <div class="dialog-actions">
        <button
          ref="cancelButton"
          class="btn-secondary btn-icon"
          type="button"
          aria-label="キャンセル"
          title="キャンセル"
          @click="emit('cancel')"
        >
          <Icon name="close" />
        </button>
        <button
          class="btn-primary btn-icon"
          type="button"
          aria-label="確定"
          title="確定"
          @click="emit('confirm')"
        >
          <Icon name="check" />
        </button>
      </div>
    </div>
  </div>
</template>
