<script setup lang="ts">
import { computed, ref } from "vue";
import type { Marker, MarkerKind } from "../types";
import { cloneMarkers, markerLabel, MAX_MARKERS, newMarkerId, nextMarkerNumber } from "../utils/imageMarkers";
import { clampImageScale, pointerToMarkerPosition } from "../utils/imageScale";
import Icon from "./Icon.vue";

// 画像（倍率どおりの大きさ）と、その上のマーカー（ピン）、下の凡例。editable のとき、マーカーを置く・動かす・文字を変える・消す。
const props = withDefaults(
  defineProps<{
    src: string;
    title?: string;
    filename?: string;
    showFilename?: boolean;
    markers: Marker[];
    imageScale?: number;
    editable?: boolean;
  }>(),
  { title: "", filename: "", showFilename: false, imageScale: 1, editable: false },
);

const emit = defineEmits<{ "update:markers": [markers: Marker[]] }>();

const placementKind = ref<MarkerKind>("house");
const selectedId = ref<string | null>(null);
const notice = ref("");
const imgRef = ref<HTMLImageElement | null>(null);
const dragId = ref<string | null>(null);

const frameStyle = computed(() => ({ width: `${Math.round(clampImageScale(props.imageScale) * 100)}%` }));
const alt = computed(() => props.title || props.filename || "画像");

function position(event: { clientX: number; clientY: number }): { x: number; y: number } | null {
  const img = imgRef.value;
  if (!img) {
    return null;
  }
  // ピンは、画像の枠（倍率を含む大きさ）の中の割合で置くため、倍率は 1 として、画像の寸法から求める
  return pointerToMarkerPosition(event.clientX, event.clientY, img.getBoundingClientRect(), 1);
}

function place(event: MouseEvent): void {
  if (!props.editable) {
    return;
  }
  notice.value = "";
  if (props.markers.length >= MAX_MARKERS) {
    notice.value = `マーカーは ${MAX_MARKERS} 個までです`;
    return;
  }
  const pos = position(event);
  if (!pos) {
    return;
  }
  const marker: Marker =
    placementKind.value === "house"
      ? { id: newMarkerId(), kind: "house", x: pos.x, y: pos.y, text: "" }
      : { id: newMarkerId(), kind: "number", number: nextMarkerNumber(props.markers), x: pos.x, y: pos.y, text: "" };
  emit("update:markers", [...cloneMarkers(props.markers), marker]);
  selectedId.value = marker.id;
}

function startDrag(event: PointerEvent, marker: Marker): void {
  if (!props.editable) {
    return;
  }
  selectedId.value = marker.id;
  dragId.value = marker.id;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function drag(event: PointerEvent): void {
  if (dragId.value === null) {
    return;
  }
  const pos = position(event);
  if (!pos) {
    return;
  }
  emit(
    "update:markers",
    props.markers.map((m) => (m.id === dragId.value ? { ...m, x: pos.x, y: pos.y } : { ...m })),
  );
}

function endDrag(): void {
  dragId.value = null;
}

function setText(id: string, text: string): void {
  emit(
    "update:markers",
    props.markers.map((m) => (m.id === id ? { ...m, text } : { ...m })),
  );
}

function remove(id: string): void {
  notice.value = "";
  if (selectedId.value === id) {
    selectedId.value = null;
  }
  emit(
    "update:markers",
    props.markers.filter((m) => m.id !== id).map((m) => ({ ...m })),
  );
}
</script>

<template>
  <div class="image-part">
    <p v-if="title" class="image-title">{{ title }}</p>
    <p v-if="showFilename && filename" class="caption">{{ filename }}</p>

    <div v-if="editable" class="marker-toolbar">
      <span class="label">配置するマーカー</span>
      <button class="chip" :class="{ 'is-on': placementKind === 'house' }" type="button" @click="placementKind = 'house'">家</button>
      <button class="chip" :class="{ 'is-on': placementKind === 'number' }" type="button" @click="placementKind = 'number'">番号</button>
      <span class="caption">画像を押すと、マーカーを置きます</span>
    </div>
    <p v-if="notice" class="msg-error" role="alert">{{ notice }}</p>

    <div class="image-scroll">
      <div class="image-frame" :style="frameStyle">
        <img
          ref="imgRef"
          class="part-image"
          :class="{ placeable: editable }"
          :src="src"
          :alt="alt"
          draggable="false"
          @click="place"
        />
        <button
          v-for="marker in markers"
          :key="marker.id"
          type="button"
          class="marker-pin"
          :class="[marker.kind, { selected: editable && selectedId === marker.id }]"
          :style="{ left: `${marker.x * 100}%`, top: `${marker.y * 100}%` }"
          :aria-label="marker.text || markerLabel(marker)"
          @click.stop="selectedId = marker.id"
          @pointerdown.stop="startDrag($event, marker)"
          @pointermove="drag"
          @pointerup="endDrag"
          @pointercancel="endDrag"
        >
          {{ markerLabel(marker) }}
        </button>
      </div>
    </div>

    <ul v-if="markers.length > 0" class="marker-legend">
      <li v-for="marker in markers" :key="marker.id">
        <span class="marker-pin static" :class="marker.kind">{{ markerLabel(marker) }}</span>
        <template v-if="editable">
          <input
            :value="marker.text"
            type="text"
            class="marker-text"
            aria-label="マーカーの説明"
            placeholder="説明を入力"
            @input="setText(marker.id, ($event.target as HTMLInputElement).value)"
          />
          <button class="btn-text danger" type="button" aria-label="マーカーの削除" @click="remove(marker.id)">
            <Icon name="delete" />
          </button>
        </template>
        <span v-else class="marker-legend-text">{{ marker.text || "（説明なし）" }}</span>
      </li>
    </ul>
  </div>
</template>
