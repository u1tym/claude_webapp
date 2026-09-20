<script setup lang="ts">
import {
  codecLabel,
  detectMp4VideoCodec,
  ffmpegH264Command,
  HEVC_UPLOAD_WARNING,
  type Mp4VideoCodec,
} from "../utils/mp4Codec";
import { MAX_DURATION_MS, readDurationMs } from "../utils/videoFile";

// 動画ファイルの選択。選んだファイルの映像コーデック（H.265 の警告）と再生時間を調べる。
const props = defineProps<{ disabled: boolean; label: string }>();

const emit = defineEmits<{
  change: [file: File | null, durationMs: number | null, codec: Mp4VideoCodec | null];
}>();

import { ref } from "vue";

const codec = ref<Mp4VideoCodec | null>(null);
const problem = ref("");
const checking = ref(false);

async function onChange(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0] ?? null;
  codec.value = null;
  problem.value = "";
  if (!file) {
    emit("change", null, null, null);
    return;
  }
  checking.value = true;
  let detected: Mp4VideoCodec = "unknown";
  let durationMs: number | null = null;
  try {
    detected = await detectMp4VideoCodec(file);
  } catch {
    detected = "unknown";
  }
  codec.value = detected;
  if (detected !== "hevc") {
    try {
      durationMs = await readDurationMs(file);
      if (durationMs > MAX_DURATION_MS) {
        problem.value = "4 時間を超える動画は登録できません";
        durationMs = null;
      }
    } catch (e) {
      problem.value = e instanceof Error ? e.message : "動画の長さを取得できませんでした";
    }
  }
  checking.value = false;
  emit("change", problem.value ? null : file, durationMs, detected);
}
</script>

<template>
  <div class="field">
    <label for="video-file">{{ props.label }}</label>
    <input id="video-file" type="file" accept="video/mp4,video/*" :disabled="props.disabled" @change="onChange" />
    <p v-if="checking" class="caption">ファイルを確認中…</p>
    <p v-if="codec" class="caption">検出した映像コーデック: {{ codecLabel(codec) }}</p>
    <template v-if="codec === 'hevc'">
      <p class="field-error">{{ HEVC_UPLOAD_WARNING }}</p>
      <p class="caption">変換例: <code>{{ ffmpegH264Command() }}</code></p>
    </template>
    <p v-if="problem" class="field-error">{{ problem }}</p>
    <p class="caption">iPhone で再生するには、H.264 (libx264) + AAC の MP4（<code>-movflags +faststart</code> 推奨）にしてください。</p>
  </div>
</template>
