<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { patternCaption, type DimmingPattern, type PatternKey } from "../room";
import Icon from "./Icon.vue";

defineProps<{
  /** 4 種の調光パターン（表示の順） */
  patterns: DimmingPattern[];
  /** 「消灯」を出すか（電灯のパーツから開いたとき、電灯が ON の場合だけ） */
  canTurnOff: boolean;
  /** 実行中。選択肢と「消灯」を無効にする */
  busy: boolean;
}>();

const emit = defineEmits<{
  select: [pattern: PatternKey];
  off: [];
  cancel: [];
}>();

const firstOption = ref<HTMLButtonElement | null>(null);

onMounted(async () => {
  await nextTick();
  firstOption.value?.focus();
});
</script>

<template>
  <!-- 背景（オーバーレイ）を押しても閉じない。閉じるのは、ダイアログ内のボタンと Esc だけ -->
  <div class="dialog-overlay">
    <div
      class="dialog dimming-dialog"
      role="dialog"
      aria-modal="true"
      aria-label="調光パターンを選択"
      :aria-busy="busy"
      @keydown.esc.prevent="!busy && emit('cancel')"
    >
      <h3 class="dialog-title">調光パターンを選択</h3>
      <!-- 4 つのパターンは、アイコンでは区別できないため、文字ラベルを持たせる -->
      <div class="dimming-options">
        <button
          v-for="(pattern, index) in patterns"
          :key="pattern.id"
          :ref="(el) => { if (index === 0) firstOption = el as HTMLButtonElement | null; }"
          class="btn-secondary dimming-option"
          type="button"
          :data-pattern="pattern.id"
          :disabled="busy"
          @click="emit('select', pattern.id)"
        >
          <span class="dimming-name">{{ pattern.name }}</span>
          <span class="caption dimming-caption">{{ patternCaption(pattern) }}</span>
        </button>
      </div>
      <button
        v-if="canTurnOff"
        class="btn-secondary dimming-off"
        type="button"
        data-action="off"
        :disabled="busy"
        @click="emit('off')"
      >
        消灯
      </button>
      <div class="dialog-actions">
        <button
          class="btn-secondary btn-icon"
          type="button"
          aria-label="キャンセル"
          title="キャンセル"
          :disabled="busy"
          @click="emit('cancel')"
        >
          <Icon name="close" />
        </button>
      </div>
    </div>
  </div>
</template>
