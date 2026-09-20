<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { AuthError, createSeries, createVideo, errorMessage, listGenres, listSeries, putThumbnail } from "../api";
import { uploadVideoFile } from "../api/upload";
import Icon from "../components/Icon.vue";
import VideoFilePicker from "../components/VideoFilePicker.vue";
import VideoMetaFields from "../components/VideoMetaFields.vue";
import type { Genre, Series, VideoMetaForm } from "../types";
import type { Mp4VideoCodec } from "../utils/mp4Codec";
import { generateThumbnail } from "../utils/videoFile";
import { emptyMeta, validateMeta } from "../utils/videoMeta";

const router = useRouter();

const meta = reactive<VideoMetaForm>(emptyMeta());
const seriesList = ref<Series[]>([]);
const genres = ref<Genre[]>([]);
const loadingMasters = ref(true);

const file = ref<File | null>(null);
const durationMs = ref<number | null>(null);
const codec = ref<Mp4VideoCodec | null>(null);
const thumbFile = ref<File | null>(null);

const busy = ref(false);
const progress = ref("");
const progressRatio = ref<number | null>(null);
const error = ref("");

const canSubmit = computed(() => !busy.value && file.value !== null && durationMs.value !== null && codec.value !== "hevc");

function onFile(picked: File | null, duration: number | null, detected: Mp4VideoCodec | null): void {
  file.value = picked;
  durationMs.value = duration;
  codec.value = detected;
}

function onThumb(event: Event): void {
  thumbFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
}

function warnUnload(event: BeforeUnloadEvent): void {
  event.preventDefault();
}

async function submit(): Promise<void> {
  error.value = "";
  const problem = validateMeta(meta);
  if (problem) {
    error.value = problem;
    return;
  }
  if (!file.value || durationMs.value === null) {
    error.value = "動画ファイルを選んでください";
    return;
  }
  const video = file.value;
  const duration = durationMs.value;
  busy.value = true;
  progress.value = "準備中…";
  progressRatio.value = null;
  window.addEventListener("beforeunload", warnUnload);
  let createdId: number | null = null;
  try {
    let seriesId = meta.seriesId;
    if (meta.newSeriesTitle.trim()) {
      seriesId = (await createSeries(meta.newSeriesTitle.trim())).id;
    }
    progress.value = "メタデータ登録中…";
    const created = await createVideo({
      title: meta.title.trim(),
      description: meta.description.trim() || null,
      series_id: seriesId,
      episode_number: meta.episodeNumber,
      episode_title: meta.episodeTitle.trim() || null,
      sort_order: meta.sortOrder,
      duration_ms: duration,
      mime_type: video.type || "video/mp4",
      genre_ids: meta.genreIds,
    });
    createdId = created.id;
    await uploadVideoFile(created.id, video, duration, (uploaded, total) => {
      progress.value = `アップロード中 ${uploaded}/${total}`;
      progressRatio.value = uploaded / total;
    });
    progress.value = "サムネイル登録中…";
    progressRatio.value = null;
    if (thumbFile.value) {
      await putThumbnail(created.id, thumbFile.value);
    } else {
      try {
        const generated = await generateThumbnail(video, duration);
        await putThumbnail(created.id, generated.blob, generated.width, generated.height);
      } catch (e) {
        // 自動生成に失敗しても、動画は登録済みで再生できる。サムネイルなしのまま進む。
        if (e instanceof AuthError) throw e;
      }
    }
    window.removeEventListener("beforeunload", warnUnload);
    await router.push("/");
  } catch (e) {
    error.value = errorMessage(e, "登録に失敗しました");
    if (createdId !== null) {
      error.value += "。登録済みの分は「登録中」の動画として残っています。動画一覧で状態を「登録中」にして、確認・削除できます。";
    }
  } finally {
    window.removeEventListener("beforeunload", warnUnload);
    busy.value = false;
    progress.value = "";
    progressRatio.value = null;
  }
}

onMounted(async () => {
  try {
    const [g, s] = await Promise.all([listGenres(), listSeries(1, undefined, 100)]);
    genres.value = g.items;
    seriesList.value = s.items;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loadingMasters.value = false;
  }
});

onBeforeUnmount(() => window.removeEventListener("beforeunload", warnUnload));
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" :disabled="busy" @click="router.push('/')">
        <Icon name="back" />
      </button>
      <h2>動画登録</h2>
    </div>

    <div class="page-body">
      <form class="form-panel" @submit.prevent="submit">
        <p v-if="error" class="msg-error">{{ error }}</p>
        <div v-if="busy" class="field" role="status">
          <span>{{ progress }}</span>
          <div v-if="progressRatio !== null" class="progress big" aria-hidden="true">
            <span :style="{ width: `${progressRatio * 100}%` }"></span>
          </div>
        </div>

        <VideoFilePicker label="動画ファイル（MP4・必須）" :disabled="busy" @change="onFile" />
        <VideoMetaFields
          v-model="meta"
          :series-list="seriesList"
          :genres="genres"
          :loading-masters="loadingMasters"
          :disabled="busy"
          :allow-new-series="true"
        />
        <div class="field">
          <label for="thumb-file">サムネイル画像</label>
          <input id="thumb-file" type="file" accept="image/*" :disabled="busy" @change="onThumb" />
          <p class="caption">未指定の場合、5 秒地点（5 秒未満の動画は先頭のフレーム）から自動で作ります。</p>
        </div>

        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="router.push('/')">
            <Icon name="close" />
          </button>
          <button class="btn-primary" type="submit" aria-label="保存" :disabled="!canSubmit">
            <Icon name="check" />
          </button>
        </div>
      </form>
    </div>
  </section>
</template>
