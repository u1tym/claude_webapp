<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  AuthError,
  getDimmingPatterns,
  getState,
  postScene,
  putDeviceState,
  SwitchError,
} from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import DimmingDialog from "../components/DimmingDialog.vue";
import RoomDiagram from "../components/RoomDiagram.vue";
import {
  DOOR_UNLOCK_NOTE,
  doorConfirmMessage,
  formatFetchedAt,
  nextState,
  patternName,
  SCENES,
  sceneStatus,
  switchSuccessMessage,
  type DeviceKey,
  type Devices,
  type DimmingPattern,
  type LockState,
  type OnOff,
  type OperableDeviceKey,
  type PatternKey,
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
// 調光パターンダイアログ。電灯のパーツ（device）と、一括切替「電灯選択」（scene）から開く。
// パターンは、初めて開くときに API から取得する
const dimmingOpen = ref(false);
const dimmingFor = ref<"device" | "scene">("device");
const patterns = ref<DimmingPattern[] | null>(null);

let clearTimer: ReturnType<typeof setTimeout> | undefined;

const busy = computed(
  () => loading.value || switching.value !== null || sceneRunning.value !== null,
);

/** 取得できた機器が 1 つもない。 */
const allFailed = computed(() => {
  const list = devices.value;
  if (!list) {
    return false;
  }
  return (
    ["ceiling_light", "indirect_light", "indoor_speaker", "bedside_speaker", "front_door"] as const
  ).every((key) => list[key].status !== "ok");
});

/** 電灯が ON か（調光パターンダイアログに「消灯」を出す条件）。 */
const ceilingIsOn = computed(
  () => devices.value?.ceiling_light.status === "ok" && devices.value.ceiling_light.state === "on",
);

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

async function doSwitch(
  key: OperableDeviceKey,
  target: OnOff | LockState,
  pattern?: PatternKey,
): Promise<void> {
  if (busy.value) {
    return;
  }
  switching.value = key;
  clearStatus();
  try {
    const response = await putDeviceState(key, target, pattern);
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
      const label = pattern !== undefined ? patternName(patterns.value ?? [], pattern) : undefined;
      showStatus("success", switchSuccessMessage(key, target, label));
    }
  } catch (error) {
    if (!passAuthError(error)) {
      showStatus("error", error instanceof SwitchError ? error.message : "操作に失敗しました。");
    }
  } finally {
    switching.value = null;
  }
}

async function runScene(scene: SceneKey, pattern?: PatternKey): Promise<void> {
  if (!scenesEnabled.value) {
    return;
  }
  sceneRunning.value = scene;
  clearStatus();
  try {
    const response = await postScene(scene, pattern);
    // 応答は、実行のあとに全機器を取得し直した結果（一部が失敗しても 200 で返る）
    devices.value = response.devices;
    fetchedAt.value = response.fetched_at;
    const label = pattern !== undefined ? patternName(patterns.value ?? [], pattern) : undefined;
    const result = sceneStatus(scene, response.outcome, response.results, label);
    showStatus(result.kind, result.text);
  } catch (error) {
    if (!passAuthError(error)) {
      showStatus("error", error instanceof SwitchError ? error.message : "操作に失敗しました。");
    }
  } finally {
    sceneRunning.value = null;
  }
}

/** 調光パターンダイアログを開く。パターンを取得できなければ、開かずに、ステータスへ一文を示す。 */
async function openDimming(target: "device" | "scene"): Promise<void> {
  clearStatus();
  if (patterns.value === null) {
    try {
      patterns.value = (await getDimmingPatterns()).patterns;
    } catch (error) {
      if (!passAuthError(error)) {
        showStatus("error", "調光パターンを取得できませんでした。");
      }
      return;
    }
  }
  dimmingFor.value = target;
  dimmingOpen.value = true;
}

async function chooseDimming(pattern: PatternKey): Promise<void> {
  if (dimmingFor.value === "scene") {
    await runScene("ceiling_light", pattern);
  } else {
    await doSwitch("ceiling_light", "on", pattern);
  }
  dimmingOpen.value = false;
}

/** 一括切替ボタン。電灯選択は、調光パターンを選んでから実行する。ほかは、確認を挟まず実行する。 */
function onScene(scene: SceneKey): void {
  if (scene === "ceiling_light") {
    if (scenesEnabled.value) {
      void openDimming("scene");
    }
    return;
  }
  void runScene(scene);
}

async function turnOffCeiling(): Promise<void> {
  await doSwitch("ceiling_light", "off");
  dimmingOpen.value = false;
}

function cancelDimming(): void {
  dimmingOpen.value = false;
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
  if (key === "ceiling_light") {
    // 電灯は、調光パターンを選んで切り替える（確認ダイアログではなく、パターンの選択）
    void openDimming("device");
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
          @click="onScene(scene.key)"
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

    <DimmingDialog
      v-if="dimmingOpen && patterns"
      :patterns="patterns"
      :can-turn-off="dimmingFor === 'device' && ceilingIsOn"
      :busy="switching !== null || sceneRunning !== null"
      @select="chooseDimming"
      @off="turnOffCeiling"
      @cancel="cancelDimming"
    />

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
