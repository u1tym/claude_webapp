<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { AuthError, SwitchError, createSchedule, getDimmingPatterns, updateSchedule } from "../api";
import {
  ACTION_TYPE_OPTIONS,
  CONDITION_OPTIONS,
  DAY_SHIFT_OPTIONS,
  DEFAULT_PATTERN,
  HOLIDAY_MODE_OPTIONS,
  PATTERN_OPTIONS,
  SCENES,
  STATE_OPTIONS,
  TIMER_DEVICES,
  WEEKDAY_CHIPS,
  formFromItem,
  isCeilingOn,
  patternCaption,
  toScheduleBody,
  validateScheduleForm,
  type DimmingPattern,
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

// 調光パターンは、電灯を ON にする個別切替のときだけ選べる。明るさと色温度の目安は、初めて出すときに API から取る
const showPattern = computed(() => isCeilingOn(form.value));
const patternInfo = ref<DimmingPattern[] | null>(null);
const patternInfoFailed = ref(false);

/** 選択肢に添える、明るさと色温度の目安。取得できていなければ、添えない。 */
function captionFor(id: string): string {
  const info = patternInfo.value?.find((p) => p.id === id);
  return info ? patternCaption(info) : "";
}

async function loadPatternInfo(): Promise<void> {
  if (patternInfo.value !== null) {
    return;
  }
  try {
    patternInfo.value = (await getDimmingPatterns()).patterns;
    patternInfoFailed.value = false;
  } catch (e) {
    if (e instanceof AuthError) {
      emit("auth-error", e);
    } else {
      patternInfoFailed.value = true;
    }
  }
}

watch(
  showPattern,
  (shown) => {
    if (shown) {
      void loadPatternInfo();
    } else {
      // 条件に合わなくなったら、選択を破棄する（次に出すときは、既定の全灯）
      form.value.pattern = DEFAULT_PATTERN;
    }
  },
  { immediate: true },
);

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

      <fieldset v-if="form.condition === 'weekdays'" class="editor-field">
        <legend>祝日の扱い</legend>
        <label v-for="option in HOLIDAY_MODE_OPTIONS" :key="option.value" class="editor-radio">
          <input v-model="form.holidayMode" type="radio" name="holiday-mode" :value="option.value" />
          <span>{{ option.label }}</span>
        </label>
        <p class="caption">
          祝日も実行は、指定した曜日に加えて祝日にも実行します。祝日は実行しないは、指定した曜日のうち祝日を除きます。
        </p>
      </fieldset>

      <fieldset v-if="form.condition === 'weekdays'" class="editor-field">
        <legend>実行日の取り方</legend>
        <label v-for="option in DAY_SHIFT_OPTIONS" :key="option.value" class="editor-radio">
          <input v-model="form.dayShift" type="radio" name="day-shift" :value="option.value" />
          <span>{{ option.label }}</span>
        </label>
        <p class="caption">
          上で決まる日に対して、実行する日を選びます。の前の日は前日、の次の日は翌日に実行します。
        </p>
      </fieldset>

      <div class="editor-field">
        <label class="editor-label" for="schedule-time">時刻</label>
        <input id="schedule-time" v-model="form.time" class="editor-input" type="time" step="60" />
      </div>

      <fieldset class="editor-field">
        <legend>実行内容</legend>
        <label v-for="option in ACTION_TYPE_OPTIONS" :key="option.value" class="editor-radio">
          <input v-model="form.actionType" type="radio" name="action-type" :value="option.value" />
          <span>{{ option.label }}</span>
        </label>
      </fieldset>

      <div v-if="form.actionType === 'scene'" class="editor-field">
        <label class="editor-label" for="schedule-scene">一括切替</label>
        <select id="schedule-scene" v-model="form.scene" class="editor-input">
          <option value="">選択してください</option>
          <option v-for="scene in SCENES" :key="scene.key" :value="scene.key">{{ scene.label }}</option>
        </select>
      </div>

      <template v-if="form.actionType === 'device'">
        <div class="editor-field">
          <label class="editor-label" for="schedule-device">機器</label>
          <select id="schedule-device" v-model="form.device" class="editor-input">
            <option value="">選択してください</option>
            <option v-for="device in TIMER_DEVICES" :key="device.key" :value="device.key">
              {{ device.label }}
            </option>
          </select>
        </div>
        <fieldset class="editor-field">
          <legend>状態</legend>
          <label v-for="option in STATE_OPTIONS" :key="option.value" class="editor-radio">
            <input v-model="form.state" type="radio" name="state" :value="option.value" />
            <span>{{ option.label }}</span>
          </label>
        </fieldset>
      </template>

      <fieldset v-if="showPattern" class="editor-field" data-field="pattern">
        <legend>調光パターン</legend>
        <label v-for="option in PATTERN_OPTIONS" :key="option.value" class="editor-radio">
          <input v-model="form.pattern" type="radio" name="pattern" :value="option.value" />
          <span>{{ option.label }}<span v-if="captionFor(option.value)" class="caption">（{{ captionFor(option.value) }}）</span></span>
        </label>
        <p class="caption">電灯を ON にするときの、明るさと色温度の組です。</p>
        <p v-if="patternInfoFailed" class="caption">明るさと色温度の目安を取得できませんでした。</p>
      </fieldset>

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
