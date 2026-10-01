<script setup lang="ts">
import { computed } from "vue";
import {
  DEVICE_LABELS,
  ariaLabelFor,
  batteryText,
  isOperable,
  stateText,
  type DeviceKey,
  type Devices,
  type OperableDeviceKey,
} from "../room";

const props = defineProps<{
  devices: Devices;
  /** 切替中の機器（その間、すべてのパーツを操作できない） */
  switching?: DeviceKey | null;
  /** 取得中・一括切替中など、画面全体で操作を止めるとき */
  disabled?: boolean;
}>();

const emit = defineEmits<{
  select: [device: OperableDeviceKey];
}>();

type Part = { key: DeviceKey; x: number; y: number; width: number; height: number };

// 部屋を上から見た配置。タップ領域は、スマートフォン幅（約 0.5 倍）でも 44px 以上になる大きさにする
const PARTS: Part[] = [
  { key: "indirect_light", x: 30, y: 40, width: 150, height: 150 },
  { key: "ceiling_light", x: 245, y: 40, width: 150, height: 150 },
  { key: "bedside_speaker", x: 460, y: 40, width: 150, height: 150 },
  { key: "indoor_speaker", x: 30, y: 210, width: 150, height: 150 },
  { key: "front_door", x: 30, y: 370, width: 200, height: 130 },
];

const BATTERY = { x: 270, y: 385 };
const BATTERY_GAUGE_WIDTH = 90;

const blocked = computed(() => Boolean(props.disabled) || props.switching != null);

function stateOf(key: DeviceKey) {
  return props.devices[key];
}

function isOn(key: DeviceKey): boolean {
  const device = stateOf(key);
  return device.status === "ok" && (device.state === "on" || device.state === "locked");
}

function hasError(key: DeviceKey): boolean {
  return stateOf(key).status !== "ok";
}

/** 押せるか。取得できていない機器、切替中・取得中は押せない。 */
function canActivate(key: DeviceKey): boolean {
  return isOperable(key) && !hasError(key) && !blocked.value;
}

function activate(key: DeviceKey): void {
  if (isOperable(key) && canActivate(key)) {
    emit("select", key);
  }
}

const battery = computed(() => {
  const door = props.devices.front_door;
  const value = door.status === "ok" ? door.battery : null;
  const pct = typeof value === "number" ? Math.max(0, Math.min(100, value)) : null;
  return {
    text: door.status === "ok" ? batteryText(value) : "不明",
    fill: pct === null ? 0 : Math.round((BATTERY_GAUGE_WIDTH * pct) / 100),
    label: `玄関ドアの電池残量 ${door.status === "ok" ? batteryText(value) : "不明"}`,
  };
});
</script>

<template>
  <svg
    class="rd"
    viewBox="0 0 640 540"
    role="group"
    aria-label="部屋の図"
    preserveAspectRatio="xMidYMid meet"
  >
    <!-- 部屋の壁と、ベッド（飾り） -->
    <rect class="rd-wall" x="15" y="15" width="610" height="510" rx="14" aria-hidden="true" />
    <g class="rd-bed" aria-hidden="true">
      <rect x="400" y="215" width="210" height="200" rx="10" />
      <rect x="418" y="228" width="174" height="46" rx="10" />
    </g>
    <!-- 玄関の開口部（壁の切れ目） -->
    <rect class="rd-door-gap" x="55" y="516" width="150" height="18" aria-hidden="true" />

    <g
      v-for="part in PARTS"
      :key="part.key"
      class="rd-part"
      :class="{
        'is-on': isOn(part.key),
        'is-error': hasError(part.key),
        'is-operable': isOperable(part.key),
        'is-switching': switching === part.key,
        'is-blocked': isOperable(part.key) && !hasError(part.key) && blocked,
      }"
      :data-device="part.key"
      :data-state="stateOf(part.key).state ?? 'unknown'"
      :transform="`translate(${part.x} ${part.y})`"
      :role="isOperable(part.key) ? 'button' : 'img'"
      :tabindex="canActivate(part.key) ? 0 : isOperable(part.key) ? -1 : undefined"
      :aria-disabled="isOperable(part.key) ? !canActivate(part.key) : undefined"
      :aria-label="ariaLabelFor(part.key, stateOf(part.key))"
      @click="activate(part.key)"
      @keydown.enter.prevent="activate(part.key)"
      @keydown.space.prevent="activate(part.key)"
    >
      <!-- タップ領域（フォーカスリングもここに付ける） -->
      <rect class="rd-hit" x="0" y="0" :width="part.width" :height="part.height" rx="12" />

      <!-- 間接照明: 灯り。ON は塗りつぶし＋放射状の光 -->
      <g v-if="part.key === 'indirect_light'" class="rd-icon" transform="translate(0 0)">
        <path class="rd-shape" d="M55 34 L95 34 L106 68 L44 68 Z" />
        <line class="rd-line" x1="75" y1="68" x2="75" y2="92" />
        <line class="rd-line" x1="58" y1="92" x2="92" y2="92" />
        <g v-if="isOn(part.key)" class="rd-rays">
          <line x1="75" y1="12" x2="75" y2="24" />
          <line x1="40" y1="24" x2="48" y2="32" />
          <line x1="110" y1="24" x2="102" y2="32" />
          <line x1="28" y1="50" x2="40" y2="52" />
          <line x1="122" y1="50" x2="110" y2="52" />
        </g>
      </g>

      <!-- 電灯: 電球。常に OFF（輪郭のみ）。ON のときは塗りつぶし＋光線 -->
      <g v-else-if="part.key === 'ceiling_light'" class="rd-icon">
        <circle class="rd-shape" cx="75" cy="52" r="26" />
        <rect class="rd-shape" x="65" y="78" width="20" height="14" rx="3" />
        <g v-if="isOn(part.key)" class="rd-rays">
          <line x1="75" y1="10" x2="75" y2="18" />
          <line x1="36" y1="26" x2="42" y2="32" />
          <line x1="114" y1="26" x2="108" y2="32" />
          <line x1="24" y1="52" x2="32" y2="52" />
          <line x1="126" y1="52" x2="118" y2="52" />
        </g>
      </g>

      <!-- スピーカー: ON は塗りつぶし＋音波の記号 -->
      <g
        v-else-if="part.key === 'indoor_speaker' || part.key === 'bedside_speaker'"
        class="rd-icon"
      >
        <rect class="rd-shape" x="53" y="20" width="44" height="68" rx="7" />
        <circle class="rd-line-circle" cx="75" cy="38" r="5" />
        <circle class="rd-line-circle" cx="75" cy="66" r="14" />
        <g v-if="isOn(part.key)" class="rd-waves">
          <path d="M108 40 q12 18 0 36" />
          <path d="M118 30 q18 28 0 56" />
          <path d="M42 40 q-12 18 0 36" />
          <path d="M32 30 q-18 28 0 56" />
        </g>
      </g>

      <!-- 玄関ドア: 施錠中は閉じた錠、開錠中は開いた錠 -->
      <g v-else-if="part.key === 'front_door'" class="rd-icon">
        <rect class="rd-shape" x="80" y="26" width="40" height="32" rx="5" />
        <path
          class="rd-shackle"
          :d="isOn(part.key) ? 'M87 26 V16 a13 13 0 0 1 26 0 V26' : 'M87 26 V16 a13 13 0 0 1 26 0 V10'"
        />
      </g>

      <!-- 機器名と状態（文言でも区別する） -->
      <text
        class="rd-label"
        :x="part.width / 2"
        :y="part.key === 'front_door' ? 84 : 112"
        text-anchor="middle"
      >
        {{ DEVICE_LABELS[part.key] }}
      </text>
      <text
        class="rd-state"
        :class="{ 'rd-state-error': hasError(part.key) }"
        :x="part.width / 2"
        :y="part.key === 'front_door' ? 112 : 136"
        text-anchor="middle"
      >
        <template v-if="switching === part.key">切替中…</template>
        <template v-else-if="hasError(part.key)">⚠ 取得できません</template>
        <template v-else>{{ stateText(stateOf(part.key)) }}</template>
      </text>
      <text
        v-if="part.key === 'ceiling_light'"
        class="rd-note"
        :x="part.width / 2"
        y="158"
        text-anchor="middle"
      >
        未実装
      </text>
    </g>

    <!-- 玄関ドアの電池残量（表示のみ。操作できない） -->
    <g
      class="rd-battery"
      :class="{ 'is-error': devices.front_door.status !== 'ok' }"
      data-part="battery"
      role="img"
      :aria-label="battery.label"
      :transform="`translate(${BATTERY.x} ${BATTERY.y})`"
    >
      <rect class="rd-battery-body" x="0" y="0" :width="BATTERY_GAUGE_WIDTH" height="36" rx="6" />
      <rect class="rd-battery-tip" :x="BATTERY_GAUGE_WIDTH" y="11" width="7" height="14" rx="2" />
      <rect
        class="rd-battery-fill"
        data-testid="battery-fill"
        x="3"
        y="3"
        :width="Math.max(0, battery.fill - 6)"
        height="30"
        rx="4"
      />
      <text class="rd-state" x="45" y="64" text-anchor="middle">{{ battery.text }}</text>
      <text class="rd-note" x="45" y="86" text-anchor="middle">電池残量</text>
    </g>
  </svg>
</template>

<style>
.rd {
  width: 100%;
  height: 100%;
  max-height: 100%;
  display: block;
  user-select: none;
}

.rd-wall {
  fill: var(--color-surface);
  stroke: var(--color-text-muted);
  stroke-width: 4;
}

.rd-door-gap {
  fill: var(--color-bg);
}

.rd-bed rect {
  fill: none;
  stroke: var(--color-border);
  stroke-width: 3;
}

.rd-hit {
  fill: transparent;
  stroke: transparent;
  stroke-width: 3;
}

.rd-part.is-operable:not(.is-blocked):not(.is-error) {
  cursor: pointer;
}

.rd-part.is-operable:not(.is-blocked):not(.is-error):hover .rd-hit {
  fill: color-mix(in srgb, var(--color-primary) 10%, transparent);
}

/* フォーカス表示（キーボード操作） */
.rd-part:focus-visible {
  outline: none;
}

.rd-part:focus-visible .rd-hit {
  stroke: var(--color-primary);
}

/* OFF / 開錠中: 輪郭のみ */
.rd-shape,
.rd-line-circle {
  fill: var(--color-surface);
  stroke: var(--color-text-muted);
  stroke-width: 4;
  stroke-linejoin: round;
}

.rd-line,
.rd-shackle,
.rd-rays line,
.rd-waves path {
  fill: none;
  stroke: var(--color-text-muted);
  stroke-width: 4;
  stroke-linecap: round;
}

/* ON / 施錠中: 塗りつぶし＋光線・音波（色だけに頼らない） */
.rd-part.is-on .rd-shape {
  fill: var(--color-primary);
  stroke: var(--color-text);
}

.rd-part.is-on .rd-line-circle {
  fill: none;
  stroke: var(--color-text);
}

.rd-part.is-on .rd-line,
.rd-part.is-on .rd-shackle {
  stroke: var(--color-text);
}

.rd-rays line,
.rd-waves path {
  stroke: var(--color-primary);
}

.rd-label {
  fill: var(--color-text);
  font-size: 22px;
}

.rd-state {
  fill: var(--color-text);
  font-size: 24px;
  font-weight: 700;
}

.rd-note {
  fill: var(--color-text-muted);
  font-size: 20px;
}

/* 「⚠ 取得できません」はパーツの幅（150）に収める */
.rd-state-error {
  font-size: 18px;
}

/* 取得できなかった機器: 破線の輪郭、薄く */
.rd-part.is-error .rd-shape,
.rd-part.is-error .rd-line-circle,
.rd-part.is-error .rd-line,
.rd-part.is-error .rd-shackle {
  stroke-dasharray: 8 6;
}

.rd-part.is-error .rd-icon,
.rd-part.is-error .rd-label {
  opacity: 0.5;
}

.rd-part.is-error .rd-state {
  fill: var(--color-danger);
}

.rd-part.is-switching .rd-icon {
  opacity: 0.6;
}

.rd-part.is-blocked {
  opacity: 0.7;
}

/* 電池残量 */
.rd-battery-body,
.rd-battery-tip {
  fill: var(--color-surface);
  stroke: var(--color-text-muted);
  stroke-width: 4;
}

.rd-battery-fill {
  fill: var(--color-primary);
}

.rd-battery.is-error .rd-battery-body,
.rd-battery.is-error .rd-battery-tip {
  stroke-dasharray: 8 6;
}
</style>
