<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { SKIP_MS, type Player } from "../composables/usePlayer";
import { useControlsAutoHide } from "../composables/useControlsAutoHide";
import { useFullscreen } from "../composables/useFullscreen";
import { formatMs } from "../utils/format";

// 動画と操作部（シークバー・再生／一時停止・10 秒戻る／進む・全画面・前後の動画）。
const props = defineProps<{
  player: Player;
  posterUrl: string | null;
  /** 前回の再生位置（ミリ秒）。あるときは「続きから再生」を出す。 */
  resumeMs: number | null;
  /** プレイリスト再生のとき true（「前の動画」を出す） */
  showPrev?: boolean;
}>();

const emit = defineEmits<{ start: [resume: boolean] }>();

const stage = ref<HTMLElement | null>(null);
const video = ref<HTMLVideoElement | null>(null);

const player = props.player;
const { visible, poke, pin, playingChanged } = useControlsAutoHide(player.playing);
const { isFullscreen, toggle: toggleFullscreen } = useFullscreen();

const durationMs = computed(() => player.item.value?.durationMs ?? 0);
const hasResume = computed(() => props.resumeMs !== null && props.resumeMs > 0);
const canNext = computed(() => player.item.value?.hasNext === true);
const canPrev = computed(() => player.item.value?.hasPrev === true);

watch(player.playing, playingChanged);

onMounted(() => {
  if (video.value) {
    player.attach(video.value);
  }
  player.stageEl.value = stage.value;
});

function onStageClick(): void {
  if (player.phase.value !== "ready") {
    return;
  }
  if (!visible.value) {
    poke(); // 隠れているときは、まず操作部を出す
    return;
  }
  player.togglePlay();
  poke();
}

function onKeydown(event: KeyboardEvent): void {
  poke();
  if (event.target !== stage.value || player.phase.value !== "ready") {
    return;
  }
  if (event.key === " " || event.key === "k") {
    event.preventDefault();
    player.togglePlay();
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    player.skip(-SKIP_MS);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    player.skip(SKIP_MS);
  }
}

function onSeek(event: Event): void {
  player.seekTo(Number((event.target as HTMLInputElement).value));
}
</script>

<template>
  <div
    ref="stage"
    class="stage"
    tabindex="0"
    aria-label="動画プレイヤー"
    @pointermove="poke"
    @keydown="onKeydown"
  >
    <video ref="video" playsinline preload="metadata" @click="onStageClick"></video>
    <img v-if="player.phase.value === 'idle' && posterUrl" class="poster" :src="posterUrl" alt="" />

    <div v-if="player.phase.value === 'idle'" class="stage-overlay">
      <div class="actions">
        <template v-if="hasResume">
          <button class="btn-primary" type="button" @click="emit('start', true)">
            続きから再生（{{ formatMs(resumeMs ?? 0) }}）
          </button>
          <button class="btn-secondary" type="button" @click="emit('start', false)">最初から再生</button>
        </template>
        <button v-else class="btn-primary" type="button" @click="emit('start', true)">再生</button>
      </div>
    </div>

    <div v-else-if="player.phase.value === 'loading'" class="stage-overlay">
      <p class="stage-message">読み込み中…</p>
    </div>

    <div v-else-if="player.phase.value === 'error'" class="stage-overlay">
      <p class="stage-message error" role="alert">{{ player.error.value }}</p>
      <div class="actions">
        <button v-if="showPrev" class="btn-text" type="button" :disabled="!canPrev" @click="player.prev()">
          前の動画
        </button>
        <button v-if="canNext || showPrev" class="btn-text" type="button" :disabled="!canNext" @click="player.next()">
          次の動画
        </button>
      </div>
    </div>

    <div v-else-if="player.phase.value === 'finished'" class="stage-overlay">
      <p class="stage-message">再生が終わりました</p>
      <div class="actions">
        <button v-if="showPrev && canPrev" class="btn-text" type="button" @click="player.prev()">前の動画</button>
        <button class="btn-primary" type="button" @click="player.restart()">最初から再生</button>
      </div>
    </div>

    <span v-if="player.buffering.value && player.phase.value === 'ready'" class="buffering">読み込み中…</span>

    <div
      v-if="player.phase.value === 'ready'"
      class="controls"
      :class="{ hidden: !visible }"
      @pointerdown="pin(true)"
      @pointerup="pin(false)"
      @pointercancel="pin(false)"
      @focusin="pin(true)"
      @focusout="pin(false)"
    >
      <div class="seek">
        <span>{{ formatMs(player.currentMs.value) }}</span>
        <input
          type="range"
          min="0"
          :max="durationMs"
          step="250"
          :value="player.currentMs.value"
          aria-label="再生位置"
          @input="onSeek"
        />
        <span>{{ formatMs(durationMs) }}</span>
      </div>
      <div class="controls-row">
        <button v-if="showPrev" class="btn-text" type="button" :disabled="!canPrev" @click="player.prev()">
          前の動画
        </button>
        <button class="btn-text" type="button" @click="player.togglePlay()">
          {{ player.playing.value ? "一時停止" : "再生" }}
        </button>
        <button class="btn-text" type="button" @click="player.skip(-SKIP_MS)">10秒戻る</button>
        <button class="btn-text" type="button" @click="player.skip(SKIP_MS)">10秒進む</button>
        <button class="btn-text" type="button" :disabled="!canNext" @click="player.next()">次の動画</button>
        <button
          class="btn-text push-end"
          type="button"
          :aria-pressed="isFullscreen"
          @click="toggleFullscreen(stage, video)"
        >
          全画面
        </button>
      </div>
    </div>
  </div>
</template>
