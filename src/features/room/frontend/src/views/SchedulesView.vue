<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import {
  AuthError,
  deleteSchedule,
  getSchedules,
  setScheduleEnabled,
  SwitchError,
} from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Icon from "../components/Icon.vue";
import ScheduleEditor from "../components/ScheduleEditor.vue";
import {
  DEVICE_LABELS,
  RUN_RESULT_TEXT,
  actionText,
  conditionText,
  formatLastRunAt,
  type ScheduleItem,
} from "../room";

const emit = defineEmits<{
  "auth-error": [error: unknown];
}>();

const SUCCESS_MESSAGE_MS = 4000;

const schedules = ref<ScheduleItem[] | null>(null);
const loading = ref(false);
const loadError = ref("");
const status = ref<{ kind: "success" | "error"; text: string } | null>(null);
// 操作中の定期実行（有効／無効の切替・削除）。同じ行を重ねて操作しない
const pendingIds = ref<Set<number>>(new Set());
// 削除の確認ダイアログの対象
const deleting = ref<ScheduleItem | null>(null);
// 定期実行入力（モーダル）の対象。item が null なら新規
const editor = ref<{ item: ScheduleItem | null } | null>(null);

let clearTimer: ReturnType<typeof setTimeout> | undefined;

function showStatus(kind: "success" | "error", text: string): void {
  clearTimeout(clearTimer);
  status.value = { kind, text };
  // 成功は数秒で消す。失敗は次の操作まで残す
  if (kind === "success") {
    clearTimer = setTimeout(() => {
      status.value = null;
    }, SUCCESS_MESSAGE_MS);
  }
}

function clearStatus(): void {
  clearTimeout(clearTimer);
  status.value = null;
}

function passAuthError(error: unknown): boolean {
  if (error instanceof AuthError) {
    emit("auth-error", error);
    return true;
  }
  return false;
}

function setPending(id: number, on: boolean): void {
  const next = new Set(pendingIds.value);
  if (on) {
    next.add(id);
  } else {
    next.delete(id);
  }
  pendingIds.value = next;
}

async function load(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  try {
    schedules.value = await getSchedules();
  } catch (error) {
    if (!passAuthError(error)) {
      loadError.value = "定期実行を取得できませんでした。";
    }
  } finally {
    loading.value = false;
  }
}

function replaceItem(updated: ScheduleItem): void {
  schedules.value = (schedules.value ?? []).map((item) => (item.id === updated.id ? updated : item));
}

async function toggleEnabled(item: ScheduleItem): Promise<void> {
  if (pendingIds.value.has(item.id)) {
    return;
  }
  setPending(item.id, true);
  clearStatus();
  try {
    replaceItem(await setScheduleEnabled(item.id, !item.is_enabled));
  } catch (error) {
    if (!passAuthError(error)) {
      showStatus("error", error instanceof SwitchError ? error.message : "操作に失敗しました。");
    }
  } finally {
    setPending(item.id, false);
  }
}

function askDelete(item: ScheduleItem): void {
  if (!pendingIds.value.has(item.id)) {
    deleting.value = item;
  }
}

async function confirmDelete(): Promise<void> {
  const target = deleting.value;
  deleting.value = null;
  if (target === null) {
    return;
  }
  setPending(target.id, true);
  clearStatus();
  try {
    await deleteSchedule(target.id);
    schedules.value = (schedules.value ?? []).filter((item) => item.id !== target.id);
    showStatus("success", "削除しました。");
  } catch (error) {
    if (!passAuthError(error)) {
      showStatus("error", error instanceof SwitchError ? error.message : "操作に失敗しました。");
    }
  } finally {
    setPending(target.id, false);
  }
}

function openEditor(item: ScheduleItem | null): void {
  editor.value = { item };
}

/**
 * 登録・変更が成功したとき。一覧を取り直して反映し、モーダルを閉じる。
 * 一覧の並びは、Web アプリが決める（表示順の小さいものから。表示順が無いものは末尾）ので、画面では並べ替えず、
 * 取り直した順のまま示す。取り直せなかったときは、保存した 1 件だけを反映する（並びは、取り直すまで正しくない）。
 */
async function onSaved(saved: ScheduleItem, mode: "created" | "updated"): Promise<void> {
  editor.value = null;
  if (schedules.value === null) {
    // 一覧を取得できていない状態で登録したときは、1 件だけの一覧にせず、取得し直す
    await load();
  } else {
    try {
      schedules.value = await getSchedules();
    } catch (error) {
      if (passAuthError(error)) {
        return;
      }
      const list = schedules.value;
      schedules.value =
        mode === "created" ? [...list, saved] : list.map((item) => (item.id === saved.id ? saved : item));
    }
  }
  showStatus("success", mode === "created" ? "登録しました。" : "変更しました。");
}

/** モーダル内で認証の失敗が起きたとき。モーダルを閉じ、親（殻）へ伝える。 */
function onEditorAuthError(error: unknown): void {
  editor.value = null;
  passAuthError(error);
}

onMounted(load);
onBeforeUnmount(() => clearTimeout(clearTimer));
</script>

<template>
  <section class="page schedules-page" aria-labelledby="schedules-heading">
    <div class="schedules-top">
      <h2 id="schedules-heading" class="schedules-title">定期実行</h2>
      <button
        class="btn-primary btn-icon"
        type="button"
        aria-label="新規"
        title="新規"
        :disabled="loading && !schedules"
        @click="openEditor(null)"
      >
        <Icon name="new" />
      </button>
    </div>

    <p v-if="loadError" class="msg-error" role="alert">{{ loadError }}</p>

    <div v-if="loading && !schedules" class="center-message">
      <p class="caption">読み込み中…</p>
    </div>
    <div v-else-if="schedules && schedules.length === 0" class="center-message">
      <p class="caption">データがありません</p>
    </div>
    <div v-else-if="schedules" class="sch-table" role="table" aria-label="定期実行の一覧">
      <!-- ヘッダ行は固定し、本体だけスクロールする -->
      <div class="sch-row sch-head" role="row">
        <span role="columnheader">有効</span>
        <span role="columnheader">実行条件</span>
        <span role="columnheader">時刻</span>
        <span role="columnheader">実行内容</span>
        <span role="columnheader">最終実行</span>
        <span role="columnheader">操作</span>
      </div>
      <div class="sch-body">
        <div
          v-for="item in schedules"
          :key="item.id"
          class="sch-row"
          :class="{ 'is-disabled': !item.is_enabled, 'has-title': Boolean(item.title) }"
          role="row"
          :data-schedule-id="item.id"
        >
          <!-- 1 行目: タイトル（付いているときだけ。行の全幅）。2 行目以降が、本体 -->
          <span
            v-if="item.title"
            class="sch-title"
            role="cell"
            :title="item.title"
            :aria-label="`タイトル ${item.title}`"
            >{{ item.title }}</span
          >
          <span class="sch-enabled" role="cell">
            <button
              class="sch-switch"
              :class="{ 'is-on': item.is_enabled }"
              type="button"
              role="switch"
              :aria-checked="item.is_enabled"
              :aria-label="`${actionText(item)} ${item.run_time} の定期実行`"
              :disabled="pendingIds.has(item.id)"
              @click="toggleEnabled(item)"
            >
              <span class="sch-switch-knob" aria-hidden="true"></span>
              <span class="sch-switch-text">{{ item.is_enabled ? "有効" : "無効" }}</span>
            </button>
          </span>
          <span class="sch-condition" role="cell">{{ conditionText(item) }}</span>
          <span class="sch-time" role="cell">{{ item.run_time }}</span>
          <span class="sch-scene" role="cell">{{ actionText(item) }}</span>
          <span class="sch-last" role="cell">
            <template v-if="item.last_run">
              <span>{{ formatLastRunAt(item.last_run.at) }}</span>
              <span class="sch-result" :data-result="item.last_run.result">
                {{ RUN_RESULT_TEXT[item.last_run.result] }}
              </span>
              <span v-if="item.last_run.failed_devices.length > 0" class="sch-failed">
                失敗: {{ item.last_run.failed_devices.map((d) => DEVICE_LABELS[d]).join("、") }}
              </span>
            </template>
            <span v-else class="caption">未実行</span>
          </span>
          <span class="sch-actions" role="cell">
            <button
              class="btn-text btn-icon"
              type="button"
              aria-label="編集"
              title="編集"
              :disabled="pendingIds.has(item.id)"
              @click="openEditor(item)"
            >
              <Icon name="edit" />
            </button>
            <button
              class="btn-text btn-icon sch-delete"
              type="button"
              aria-label="削除"
              title="削除"
              :disabled="pendingIds.has(item.id)"
              @click="askDelete(item)"
            >
              <Icon name="delete" />
            </button>
          </span>
        </div>
      </div>
    </div>

    <p
      class="status-line"
      :class="{ 'is-error': status?.kind === 'error' }"
      :role="status?.kind === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      {{ status?.text }}
    </p>

    <ScheduleEditor
      v-if="editor"
      :item="editor.item"
      @saved="onSaved"
      @cancel="editor = null"
      @auth-error="onEditorAuthError"
    />

    <ConfirmDialog
      v-if="deleting"
      title="定期実行の削除の確認"
      message="この定期実行を削除します。よろしいですか?"
      @confirm="confirmDelete"
      @cancel="deleting = null"
    />
  </section>
</template>
