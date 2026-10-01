<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { AuthError, getState, postScene, putDeviceState, SwitchError } from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import RoomDiagram from "../components/RoomDiagram.vue";
import {
  DOOR_UNLOCK_NOTE,
  doorConfirmMessage,
  formatFetchedAt,
  nextState,
  SCENES,
  sceneStatus,
  switchSuccessMessage,
  type DeviceKey,
  type Devices,
  type LockState,
  type OnOff,
  type OperableDeviceKey,
  type SceneKey,
} from "../room";

const emit = defineEmits<{
  "auth-error": [error: unknown];
}>();

const SUCCESS_MESSAGE_MS = 4000;

const devices = ref<Devices | null>(null);
const fetchedAt = ref("");
// 取得中。初期値は false（true にすると、初回の取得が「取得中は重ねて取得しない」の判定に止められる）
const loading = ref(false);
const loadError = ref("");
const switching = ref<DeviceKey | null>(null);
// 実行中の一括切替
const sceneRunning = ref<SceneKey | null>(null);
const status = ref<{ kind: "success" | "error"; text: string } | null>(null);
// 玄関ドアの確認ダイアログ（目標の状態）
const doorTarget = ref<LockState | null>(null);

let clearTimer: ReturnType<typeof setTimeout> | undefined;

const busy = computed(
  () => loading.value || switching.value !== null || sceneRunning.value !== null,
);

/** 取得できた機器が 1 つもない（電灯は常に OK なので、それ以外の 4 機器で判定する）。 */
const allFailed = computed(() => {
  const list = devices.value;
  if (!list) {
    return false;
  }
  return (["indirect_light", "indoor_speaker", "bedside_speaker", "front_door"] as const).every(
    (key) => list[key].status !== "ok",
  );
});

/** 一括切替を押せるか。状態を取得できていない間と、取得中・切替中は押せない（操作は更新だけ有効）。 */
const scenesEnabled = computed(
  () => devices.value !== null && !loadError.value && !allFailed.value && !busy.value,
);

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

/** 認証の失敗は親（殻）へ伝え、それ以外は呼び出し元で処理する。 */
function passAuthError(error: unknown): boolean {
  if (error instanceof AuthError) {
    emit("auth-error", error);
    return true;
  }
  return false;
}

async function load(): Promise<void> {
  if (busy.value) {
    return;
  }
  loading.value = true;
  loadError.value = "";
  clearStatus();
  try {
    const state = await getState();
    devices.value = state.devices;
    fetchedAt.value = state.fetched_at;
  } catch (error) {
    if (!passAuthError(error)) {
      loadError.value = "状態を取得できませんでした。";
    }
  } finally {
    loading.value = false;
  }
}

async function doSwitch(key: OperableDeviceKey, target: OnOff | LockState): Promise<void> {
  if (busy.value) {
    return;
  }
  switching.value = key;
  clearStatus();
  try {
    const response = await putDeviceState(key, target);
    if (devices.value) {
      devices.value = { ...devices.value, [key]: response.result };
    }
    // 取得日時は、機器から最後に状態を取得した日時にする
    fetchedAt.value = response.fetched_at;
    if (response.result.status !== "ok") {
      showStatus("error", "指示は送りましたが、状態を確認できませんでした。更新してください。");
    } else if (response.result.state !== target) {
      showStatus("error", "切り替えを指示しましたが、状態が変わっていません。更新して確認してください。");
    } else {
      showStatus("success", switchSuccessMessage(key, target));
    }
  } catch (error) {
    if (!passAuthError(error)) {
      showStatus("error", error instanceof SwitchError ? error.message : "操作に失敗しました。");
    }
  } finally {
    switching.value = null;
  }
}

async function runScene(scene: SceneKey): Promise<void> {
  if (!scenesEnabled.value) {
    return;
  }
  sceneRunning.value = scene;
  clearStatus();
  try {
    const response = await postScene(scene);
    // 応答は、実行のあとに全機器を取得し直した結果（一部が失敗しても 200 で返る）
    devices.value = response.devices;
    fetchedAt.value = response.fetched_at;
    const result = sceneStatus(scene, response.outcome, response.results);
    showStatus(result.kind, result.text);
  } catch (error) {
    if (!passAuthError(error)) {
      showStatus("error", error instanceof SwitchError ? error.message : "操作に失敗しました。");
    }
  } finally {
    sceneRunning.value = null;
  }
}

function onSelect(key: OperableDeviceKey): void {
  const list = devices.value;
  if (!list || busy.value) {
    return;
  }
  const target = nextState(key, list[key]);
  if (target === null) {
    return;
  }
  if (key === "front_door") {
    // 玄関ドアは、確認で承認したときだけ切り替える
    doorTarget.value = target as LockState;
    return;
  }
  void doSwitch(key, target);
}

function confirmDoor(): void {
  const target = doorTarget.value;
  doorTarget.value = null;
  if (target !== null) {
    void doSwitch("front_door", target);
  }
}

function cancelDoor(): void {
  doorTarget.value = null;
}

onMounted(load);
onBeforeUnmount(() => clearTimeout(clearTimer));
</script>

<template>
  <section class="page room-page" aria-labelledby="room-heading">
    <h2 id="room-heading" class="visually-hidden">ROOM</h2>

    <div class="room-diagram-area">
      <p v-if="loadError" class="msg-error" role="alert">{{ loadError }}</p>
      <p v-else-if="allFailed" class="msg-error" role="alert">状態を取得できませんでした。</p>
      <div v-if="!devices && !loadError" class="center-message">
        <p class="caption">読み込み中…</p>
      </div>
      <RoomDiagram
        v-else-if="devices"
        :devices="devices"
        :switching="switching"
        :disabled="loading || sceneRunning !== null"
        @select="onSelect"
      />
    </div>

    <div class="room-fetch">
      <h3 class="room-heading">取得日時</h3>
      <p class="room-fetched-at" data-testid="fetched-at">{{ fetchedAt ? formatFetchedAt(fetchedAt) : "—" }}</p>
      <button class="btn-secondary" type="button" :disabled="busy" @click="load">更新</button>
    </div>

    <div class="room-scenes">
      <h3 class="room-heading">一括切替</h3>
      <div class="scene-buttons">
        <button
          v-for="scene in SCENES"
          :key="scene.key"
          class="btn-secondary scene-button"
          :class="{ 'is-out': scene.key === 'out' }"
          type="button"
          :data-scene="scene.key"
          :aria-busy="sceneRunning === scene.key"
          :disabled="!scenesEnabled"
          @click="runScene(scene.key)"
        >
          {{ scene.label }}
        </button>
      </div>
    </div>

    <p
      class="room-status"
      :class="{ 'is-error': status?.kind === 'error' }"
      :role="status?.kind === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      {{ sceneRunning ? "実行中…" : status?.text }}
    </p>

    <ConfirmDialog
      v-if="doorTarget"
      title="玄関ドアの確認"
      :message="doorConfirmMessage(doorTarget)"
      :note="doorTarget === 'unlocked' ? DOOR_UNLOCK_NOTE : undefined"
      @confirm="confirmDoor"
      @cancel="cancelDoor"
    />
  </section>
</template>
