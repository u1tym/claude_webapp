<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { AuthError, SwitchError, createSchedule, updateSchedule } from "../api";
import {
  CONDITION_OPTIONS,
  SCENES,
  WEEKDAY_CHIPS,
  formFromItem,
  toScheduleBody,
  validateScheduleForm,
  type ScheduleForm,
  type ScheduleItem,
} from "../room";
import Icon from "./Icon.vue";

const props = defineProps<{
  /** 変更する定期実行。null は新規 */
  item: ScheduleItem | null;
}>();

const emit = defineEmits<{
  saved: [item: ScheduleItem, mode: "created" | "updated"];
  cancel: [];
  "auth-error": [error: unknown];
}>();

const form = ref<ScheduleForm>(formFromItem(props.item));
const error = ref("");
const saving = ref(false);
const firstField = ref<HTMLInputElement | null>(null);

const title = props.item === null ? "定期実行の登録" : "定期実行の変更";

function toggleWeekday(value: number): void {
  const list = form.value.weekdays;
  form.value.weekdays = list.includes(value) ? list.filter((d) => d !== value) : [...list, value];
}

async function save(): Promise<void> {
  if (saving.value) {
    return;
  }
  const problem = validateScheduleForm(form.value);
  if (problem !== null) {
    // 送信しない。理由をモーダルの先頭に示す
    error.value = problem;
    return;
  }
  error.value = "";
  saving.value = true;
  try {
    const body = toScheduleBody(form.value);
    if (props.item === null) {
      emit("saved", await createSchedule(body), "created");
    } else {
      emit("saved", await updateSchedule(props.item.id, body), "updated");
    }
  } catch (e) {
    if (e instanceof AuthError) {
      emit("auth-error", e);
    } else {
      // 入力は残したまま、モーダルの先頭に一文を示す（内部理由は出さない）
      error.value = e instanceof SwitchError ? e.message : "操作に失敗しました。";
    }
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await nextTick();
  firstField.value?.focus();
});
</script>

<template>
  <!-- 背景（オーバーレイ）を押しても閉じない。閉じるのは、ボタンと Esc だけ -->
  <div class="dialog-overlay">
    <form
      class="dialog editor"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      novalidate
      @submit.prevent="save"
      @keydown.esc.prevent="emit('cancel')"
    >
      <h2 class="editor-title">{{ title }}</h2>
      <p v-if="error" class="msg-error" role="alert">{{ error }}</p>

      <fieldset class="editor-field">
        <legend>実行条件</legend>
        <label v-for="(option, index) in CONDITION_OPTIONS" :key="option.value" class="editor-radio">
          <input
            :ref="(el) => { if (index === 0) firstField = el as HTMLInputElement | null; }"
            v-model="form.condition"
            type="radio"
            name="condition"
            :value="option.value"
          />
          <span>{{ option.label }}</span>
        </label>
      </fieldset>

      <fieldset v-if="form.condition === 'weekdays'" class="editor-field">
        <legend>曜日</legend>
        <div class="chips">
          <button
            v-for="chip in WEEKDAY_CHIPS"
            :key="chip.value"
            class="chip"
            :class="{ 'is-selected': form.weekdays.includes(chip.value) }"
            type="button"
            role="checkbox"
            :aria-checked="form.weekdays.includes(chip.value)"
            :aria-label="`${chip.label}曜日`"
            @click="toggleWeekday(chip.value)"
          >
            <span aria-hidden="true">{{ form.weekdays.includes(chip.value) ? "✓ " : "" }}{{ chip.label }}</span>
          </button>
        </div>
      </fieldset>

      <div class="editor-field">
        <label class="editor-label" for="schedule-time">時刻</label>
        <input id="schedule-time" v-model="form.time" class="editor-input" type="time" step="60" />
      </div>

      <div class="editor-field">
        <label class="editor-label" for="schedule-scene">一括切替</label>
        <select id="schedule-scene" v-model="form.scene" class="editor-input">
          <option value="">選択してください</option>
          <option v-for="scene in SCENES" :key="scene.key" :value="scene.key">{{ scene.label }}</option>
        </select>
      </div>

      <div class="editor-field editor-enabled">
        <span class="editor-label" id="schedule-enabled-label">有効</span>
        <button
          class="sch-switch"
          :class="{ 'is-on': form.enabled }"
          type="button"
          role="switch"
          :aria-checked="form.enabled"
          aria-labelledby="schedule-enabled-label"
          @click="form.enabled = !form.enabled"
        >
          <span class="sch-switch-knob" aria-hidden="true"></span>
          <span class="sch-switch-text">{{ form.enabled ? "有効" : "無効" }}</span>
        </button>
      </div>

      <div class="dialog-actions">
        <button
          class="btn-secondary btn-icon"
          type="button"
          aria-label="キャンセル"
          title="キャンセル"
          :disabled="saving"
          @click="emit('cancel')"
        >
          <Icon name="close" />
        </button>
        <button
          class="btn-primary btn-icon"
          type="submit"
          aria-label="保存"
          title="保存"
          :disabled="saving"
        >
          <Icon name="check" />
        </button>
      </div>
    </form>
  </div>
</template>
