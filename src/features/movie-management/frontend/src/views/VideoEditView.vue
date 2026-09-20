<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ApiError,
  deleteVideo,
  errorMessage,
  getVideo,
  listGenres,
  listSeries,
  replaceVideoFile,
  updateVideo,
} from "../api";
import { uploadVideoFile } from "../api/upload";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Icon from "../components/Icon.vue";
import VideoFilePicker from "../components/VideoFilePicker.vue";
import VideoMetaFields from "../components/VideoMetaFields.vue";
import type { Genre, Series, VideoDetail, VideoMetaForm } from "../types";
import { formatMs, statusLabel } from "../utils/format";
import type { Mp4VideoCodec } from "../utils/mp4Codec";
import { emptyMeta, validateMeta } from "../utils/videoMeta";

const props = defineProps<{ id: string }>();
const router = useRouter();
const videoId = Number(props.id);

const detail = ref<VideoDetail | null>(null);
const meta = reactive<VideoMetaForm>(emptyMeta());
const seriesList = ref<Series[]>([]);
const genres = ref<Genre[]>([]);
const loading = ref(true);
const notFound = ref(false);

const error = ref("");
const success = ref("");
const saving = ref(false);

const confirm = ref<"delete" | "replace" | null>(null);
const working = ref(false);

const file = ref<File | null>(null);
const durationMs = ref<number | null>(null);
const codec = ref<Mp4VideoCodec | null>(null);
const replaceProgress = ref("");
const replaceRatio = ref<number | null>(null);
const replaceError = ref("");
const pickerKey = ref(0);

const busy = computed(() => saving.value || working.value);
const canReplace = computed(() => !busy.value && file.value !== null && durationMs.value !== null && codec.value !== "hevc");

function fill(d: VideoDetail): void {
  meta.title = d.title;
  meta.description = d.description ?? "";
  meta.seriesId = d.series_id;
  meta.newSeriesTitle = "";
  meta.episodeNumber = d.episode_number;
  meta.episodeTitle = d.episode_title ?? "";
  meta.sortOrder = d.sort_order;
  meta.genreIds = d.genres.map((g) => g.id);
}

async function load(): Promise<void> {
  try {
    const [d, g, s] = await Promise.all([getVideo(videoId), listGenres(), listSeries(1, undefined, 100)]);
    detail.value = d;
    genres.value = g.items;
    seriesList.value = s.items;
    fill(d);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound.value = true;
    } else {
      error.value = errorMessage(e);
    }
  } finally {
    loading.value = false;
  }
}

async function save(): Promise<void> {
  error.value = "";
  success.value = "";
  const problem = validateMeta(meta);
  if (problem) {
    error.value = problem;
    return;
  }
  saving.value = true;
  try {
    await updateVideo(videoId, {
      title: meta.title.trim(),
      description: meta.description.trim() || null,
      series_id: meta.seriesId,
      episode_number: meta.episodeNumber,
      episode_title: meta.episodeTitle.trim() || null,
      sort_order: meta.sortOrder,
      genre_ids: meta.genreIds,
    });
    await router.push("/");
  } catch (e) {
    error.value = errorMessage(e, "保存に失敗しました");
  } finally {
    saving.value = false;
  }
}

async function remove(): Promise<void> {
  working.value = true;
  error.value = "";
  try {
    await deleteVideo(videoId);
    await router.push("/");
  } catch (e) {
    confirm.value = null;
    error.value = errorMessage(e, "削除に失敗しました");
  } finally {
    working.value = false;
  }
}

function onFile(picked: File | null, duration: number | null, detected: Mp4VideoCodec | null): void {
  file.value = picked;
  durationMs.value = duration;
  codec.value = detected;
}

async function replace(): Promise<void> {
  confirm.value = null;
  if (!file.value || durationMs.value === null) {
    return;
  }
  const video = file.value;
  const duration = durationMs.value;
  working.value = true;
  replaceError.value = "";
  success.value = "";
  replaceProgress.value = "準備中…";
  replaceRatio.value = null;
  try {
    replaceProgress.value = "旧ファイルを削除中…";
    await replaceVideoFile(videoId, duration, video.type || "video/mp4");
    await uploadVideoFile(videoId, video, duration, (uploaded, total) => {
      replaceProgress.value = `アップロード中 ${uploaded}/${total}`;
      replaceRatio.value = uploaded / total;
    });
    file.value = null;
    durationMs.value = null;
    codec.value = null;
    pickerKey.value += 1;
    success.value = "動画ファイルを差し替えました";
    detail.value = await getVideo(videoId);
  } catch (e) {
    replaceError.value =
      errorMessage(e, "差し替えに失敗しました") +
      "。動画は「登録中」のまま残っています。もう一度差し替えるか、削除してください。";
    try {
      detail.value = await getVideo(videoId);
    } catch {
      // 状態の再取得に失敗しても、画面の操作は続けられる
    }
  } finally {
    working.value = false;
    replaceProgress.value = "";
    replaceRatio.value = null;
  }
}

onMounted(load);
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" :disabled="busy" @click="router.push('/')">
        <Icon name="back" />
      </button>
      <h2>動画編集</h2>
    </div>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="notFound" class="centered">動画が見つかりません</p>
      <template v-else-if="detail">
        <form class="form-panel" @submit.prevent="save">
          <p v-if="error" class="msg-error">{{ error }}</p>
          <p v-if="success" class="msg-success">{{ success }}</p>
          <p class="caption">
            長さ {{ formatMs(detail.duration_ms) }}・{{ detail.mime_type }}
            <span v-if="detail.status !== 'ready'" class="badge danger">{{ statusLabel(detail.status) }}</span>
          </p>

          <VideoMetaFields
            v-model="meta"
            :series-list="seriesList"
            :genres="genres"
            :loading-masters="false"
            :disabled="busy"
            :allow-new-series="false"
          />

          <div class="actions actions-end">
            <button class="btn-secondary danger" type="button" aria-label="削除" :disabled="busy" @click="confirm = 'delete'">
              <Icon name="delete" />
            </button>
            <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="router.push('/')">
              <Icon name="close" />
            </button>
            <button class="btn-primary" type="submit" aria-label="保存" :disabled="busy">
              <Icon name="check" />
            </button>
          </div>
        </form>

        <div class="form-panel" style="margin-top: 16px">
          <h3>動画ファイルの差し替え</h3>
          <p class="caption">現在の動画ファイルを削除し、選んだファイルに置き換えます。再生位置もリセットされます。</p>
          <p v-if="replaceError" class="msg-error">{{ replaceError }}</p>
          <div v-if="working && replaceProgress" class="field" role="status">
            <span>{{ replaceProgress }}</span>
            <div v-if="replaceRatio !== null" class="progress big" aria-hidden="true">
              <span :style="{ width: `${replaceRatio * 100}%` }"></span>
            </div>
          </div>
          <VideoFilePicker :key="pickerKey" label="新しい動画ファイル（MP4）" :disabled="busy" @change="onFile" />
          <div class="actions actions-end">
            <button class="btn-secondary" type="button" :disabled="!canReplace" @click="confirm = 'replace'">
              ファイルを差し替え
            </button>
          </div>
        </div>
      </template>
    </div>

    <ConfirmDialog
      v-if="confirm === 'delete' && detail"
      title="動画の削除"
      :message="`「${detail.title}」を削除しますか？動画ファイル・サムネイル・再生状態も削除されます。`"
      confirm-label="削除"
      :danger="true"
      :busy="working"
      @confirm="remove"
      @cancel="confirm = null"
    />
    <ConfirmDialog
      v-if="confirm === 'replace'"
      title="動画ファイルの差し替え"
      message="現在の動画ファイルを削除し、選んだファイルに置き換えます。再生位置もリセットされます。よろしいですか？"
      confirm-label="ファイルを差し替え"
      @confirm="replace"
      @cancel="confirm = null"
    />
  </section>
</template>
