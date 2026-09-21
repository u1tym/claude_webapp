<script setup lang="ts">
import { ref } from "vue";
import { createMeasurement, errorMessage } from "../api";
import type { Measurement } from "../types";
import Icon from "./Icon.vue";

// 分量名称の追加ダイアログ。背景（オーバーレイ）を押しても閉じない。
// 保存が成功したら saved を出す（閉じるかどうかは呼び出し側が決める）。失敗したときは開いたまま、先頭にエラーを示す。
const emit = defineEmits<{ saved: [measurement: Measurement]; cancel: [] }>();

const nameBef = ref("");
const nameAft = ref("");
const nessAmount = ref(true);
const error = ref("");
const saving = ref(false);

async function submit(): Promise<void> {
  error.value = "";
  const bef = nameBef.value.trim();
  const aft = nameAft.value.trim();
  if (bef === "" && aft === "") {
    error.value = "接頭語と接尾語のどちらかを入力してください";
    return;
  }
  saving.value = true;
  try {
    emit("saved", await createMeasurement({ name_bef: bef, name_aft: aft, ness_amount: nessAmount.value }));
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="modal-back">
    <form class="modal" role="dialog" aria-modal="true" aria-label="分量名称の追加" @submit.prevent="submit">
      <h3>分量名称の追加</h3>
      <p v-if="error" class="msg-error">{{ error }}</p>
      <div class="field-row">
        <div class="field">
          <label for="measurement-bef">接頭語</label>
          <input id="measurement-bef" v-model="nameBef" type="text" :disabled="saving" />
        </div>
        <div class="field">
          <label for="measurement-aft">接尾語</label>
          <input id="measurement-aft" v-model="nameAft" type="text" :disabled="saving" />
        </div>
      </div>
      <label class="check">
        <input v-model="nessAmount" type="checkbox" :disabled="saving" />
        数量が必要
      </label>
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
