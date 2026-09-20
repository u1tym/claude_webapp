<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ApiError,
  deletePlaylist,
  errorMessage,
  getPlaylist,
  listVideos,
  replacePlaylistItems,
  thumbnailUrl,
  updatePlaylist,
} from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Icon from "../components/Icon.vue";
import type { VideoSummary } from "../types";
import { formatMs } from "../utils/format";

const props = defineProps<{ id: string }>();
const router = useRouter();
const playlistId = Number(props.id);

// 動画の並び。同じ動画を複数回含められるため、行ごとに一意の key を持つ。
type Row = { key: number; videoId: number; title: string; durationMs: number; hasThumbnail: boolean };
let nextKey = 0;

const name = ref("");
const description = ref("");
const rows = ref<Row[]>([]);
const loading = ref(true);
const notFound = ref(false);
const error = ref("");
const success = ref("");
const saving = ref(false);
const confirmDelete = ref(false);

const addOpen = ref(false);
const searchText = ref("");
const candidates = ref<VideoSummary[]>([]);
const searching = ref(false);
const searchError = ref("");

async function load(): Promise<void> {
  try {
    const detail = await getPlaylist(playlistId);
    name.value = detail.name;
    description.value = detail.description ?? "";
    rows.value = detail.items.map((item) => ({
      key: nextKey++,
      videoId: item.video_id,
      title: item.title,
      durationMs: item.duration_ms,
      hasThumbnail: item.has_thumbnail,
    }));
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

function move(index: number, delta: -1 | 1): void {
  const target = index + delta;
  if (target < 0 || target >= rows.value.length) {
    return;
  }
  const next = [...rows.value];
  [next[index], next[target]] = [next[target]!, next[index]!];
  rows.value = next;
}

function remove(index: number): void {
  rows.value = rows.value.filter((_, i) => i !== index);
}

function add(video: VideoSummary): void {
  rows.value = [
    ...rows.value,
    { key: nextKey++, videoId: video.id, title: video.title, durationMs: video.duration_ms, hasThumbnail: video.has_thumbnail },
  ];
}

async function searchVideos(): Promise<void> {
  searching.value = true;
  searchError.value = "";
  try {
    const result = await listVideos({
      page: 1,
      per_page: 20,
      status: "ready",
      q: searchText.value.trim() || undefined,
      sort: "title",
      order: "asc",
    });
    candidates.value = result.items;
  } catch (e) {
    searchError.value = errorMessage(e);
  } finally {
    searching.value = false;
  }
}

function toggleAdd(): void {
  addOpen.value = !addOpen.value;
  if (addOpen.value && candidates.value.length === 0) {
    void searchVideos();
  }
}

async function save(): Promise<void> {
  error.value = "";
  success.value = "";
  const trimmed = name.value.trim();
  if (!trimmed || trimmed.length > 500) {
    error.value = "名前は 1〜500 文字で入力してください";
    return;
  }
  saving.value = true;
  try {
    await updatePlaylist(playlistId, { name: trimmed, description: description.value.trim() || null });
    await replacePlaylistItems(
      playlistId,
      rows.value.map((row) => row.videoId),
    );
    name.value = trimmed;
    success.value = "保存しました";
    setTimeout(() => (success.value = ""), 3000);
  } catch (e) {
    error.value = errorMessage(e, "保存に失敗しました");
  } finally {
    saving.value = false;
  }
}

async function removePlaylist(): Promise<void> {
  saving.value = true;
  try {
    await deletePlaylist(playlistId);
    await router.push("/playlists");
  } catch (e) {
    confirmDelete.value = false;
    error.value = errorMessage(e, "削除に失敗しました");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await load();
  if (!notFound.value && window.matchMedia("(min-width: 768px)").matches) {
    addOpen.value = true; // PC は並びと追加を同時に表示する
    void searchVideos();
  }
});
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" :disabled="saving" @click="router.push('/playlists')">
        <Icon name="back" />
      </button>
      <h2>プレイリスト編集</h2>
    </div>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="notFound" class="centered">プレイリストが見つかりません</p>
      <form v-else class="edit-layout" @submit.prevent="save">
        <div class="form-panel edit-main">
          <p v-if="error" class="msg-error">{{ error }}</p>
          <p v-if="success" class="msg-success">{{ success }}</p>
          <div class="field">
            <label for="pl-name">名前</label>
            <input id="pl-name" v-model="name" type="text" maxlength="500" :disabled="saving" />
          </div>
          <div class="field">
            <label for="pl-desc">説明</label>
            <textarea id="pl-desc" v-model="description" :disabled="saving"></textarea>
          </div>

          <div class="field">
            <span class="label">動画の並び（{{ rows.length }} 本）</span>
            <p v-if="rows.length === 0" class="caption">データがありません</p>
            <ul v-else class="rows">
              <li v-for="(row, index) in rows" :key="row.key" class="row">
                <div class="thumb thumb-small">
                  <img v-if="row.hasThumbnail" :src="thumbnailUrl(row.videoId)" alt="" loading="lazy" />
                  <span v-else>画像なし</span>
                </div>
                <div class="row-button">
                  <span class="row-title">{{ row.title }}</span>
                  <span class="caption">{{ formatMs(row.durationMs) }}</span>
                </div>
                <div class="row-side">
                  <button class="btn-text" type="button" :disabled="saving || index === 0" @click="move(index, -1)">上へ</button>
                  <button
                    class="btn-text"
                    type="button"
                    :disabled="saving || index === rows.length - 1"
                    @click="move(index, 1)"
                  >
                    下へ
                  </button>
                  <button class="btn-text" type="button" :disabled="saving" @click="remove(index)">外す</button>
                </div>
              </li>
            </ul>
          </div>

          <div class="actions">
            <button class="btn-secondary mobile-only" type="button" :aria-expanded="addOpen" @click="toggleAdd">
              動画を追加
            </button>
            <button class="btn-secondary danger push-end" type="button" aria-label="削除" :disabled="saving" @click="confirmDelete = true">
              <Icon name="delete" />
            </button>
            <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="saving" @click="router.push('/playlists')">
              <Icon name="close" />
            </button>
            <button class="btn-primary" type="submit" aria-label="保存" :disabled="saving">
              <Icon name="check" />
            </button>
          </div>
        </div>

        <div class="form-panel edit-add collapsible" :class="{ open: addOpen }">
          <h3>動画を追加</h3>
          <div class="search" role="search">
            <input
              v-model="searchText"
              type="search"
              placeholder="タイトルで検索"
              aria-label="追加する動画をタイトルで検索"
              @keydown.enter.prevent="searchVideos"
            />
            <button class="btn-secondary" type="button" :disabled="searching" @click="searchVideos">検索</button>
          </div>
          <p v-if="searchError" class="msg-error">{{ searchError }}</p>
          <p v-if="searching" class="caption">読み込み中…</p>
          <p v-else-if="candidates.length === 0" class="caption">データがありません</p>
          <ul v-else class="rows">
            <li v-for="video in candidates" :key="video.id" class="row">
              <div class="thumb thumb-small">
                <img v-if="video.has_thumbnail" :src="thumbnailUrl(video.id)" alt="" loading="lazy" />
                <span v-else>画像なし</span>
              </div>
              <div class="row-button">
                <span class="row-title">{{ video.title }}</span>
                <span class="caption">{{ formatMs(video.duration_ms) }}</span>
              </div>
              <button class="btn-secondary" type="button" :disabled="saving" @click="add(video)">追加</button>
            </li>
          </ul>
        </div>
      </form>
    </div>

    <ConfirmDialog
      v-if="confirmDelete"
      title="プレイリストの削除"
      :message="`「${name}」を削除しますか？含まれる動画は削除されません。`"
      confirm-label="削除"
      :danger="true"
      :busy="saving"
      @confirm="removePlaylist"
      @cancel="confirmDelete = false"
    />
  </section>
</template>

<style scoped>
.edit-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.edit-layout .form-panel {
  max-width: none;
}

@media (max-width: 767px) {
  .edit-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
