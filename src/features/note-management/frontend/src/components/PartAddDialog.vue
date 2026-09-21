<script setup lang="ts">
import { ref } from "vue";
import { createPart, errorMessage } from "../api";
import { buildCreateBody, emptyDraft, type PartDraft } from "../utils/partDraft";
import Icon from "./Icon.vue";
import PartForm from "./PartForm.vue";

// パーツの追加ダイアログ。種別を選び、種別に応じた入力をする。背景を押しても閉じない。
const props = defineProps<{ fileId: number }>();
const emit = defineEmits<{ close: []; done: [] }>();

const draft = ref<PartDraft>(emptyDraft("text"));
const busy = ref(false);
const error = ref("");

async function save(): Promise<void> {
  const built = buildCreateBody(draft.value);
  if ("error" in built) {
    error.value = built.error;
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await createPart(props.fileId, built.body);
    emit("done");
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="modal-back">
    <form class="modal part-dialog" role="dialog" aria-modal="true" aria-label="パーツを追加" novalidate @submit.prevent="save">
      <h3>パーツを追加</h3>
      <p v-if="error" class="msg-error" role="alert">{{ error }}</p>
      <div class="dialog-body">
        <PartForm v-model="draft" :part-id="null" :type-locked="false" :allow-checklist="true" :busy="busy" @error="(m: string) => (error = m)" />
      </div>
      <div class="actions actions-end">
        <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="emit('close')">
          <Icon name="close" />
        </button>
        <button class="btn-primary" type="submit" aria-label="保存" :disabled="busy">
          <Icon name="check" />
        </button>
      </div>
    </form>
  </div>
</template>
