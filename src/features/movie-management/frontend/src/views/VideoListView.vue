<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { errorMessage, getLastPlayback, listGenres, listSeries, listVideos } from "../api";
import Icon from "../components/Icon.vue";
import Pagination from "../components/Pagination.vue";
import VideoCard from "../components/VideoCard.vue";
import type { Genre, LastPlayback, ListVideosQuery, Pagination as PaginationInfo, Series, VideoSummary } from "../types";
import { formatMs } from "../utils/format";

const router = useRouter();

const videos = ref<VideoSummary[]>([]);
const pagination = ref<PaginationInfo | null>(null);
const genres = ref<Genre[]>([]);
const seriesList = ref<Series[]>([]);
const last = ref<LastPlayback | null>(null);

const loading = ref(true);
const error = ref("");

const query = ref("");
const appliedQuery = ref("");
const genreId = ref<number | null>(null);
const seriesId = ref<number | null>(null);
const status = ref<NonNullable<ListVideosQuery["status"]>>("ready");
const sort = ref<NonNullable<ListVideosQuery["sort"]>>("created_at");
const order = ref<NonNullable<ListVideosQuery["order"]>>("desc");
const page = ref(1);
const filtersOpen = ref(false);
// スマートフォンでは続きから視聴パネルを既定で閉じる（開閉は保存しない）
const resumeOpen = ref(false);
const hasLast = computed(() => Boolean(last.value?.video || last.value?.playlist));

const filtered = () =>
  appliedQuery.value !== "" || genreId.value !== null || seriesId.value !== null || status.value !== "ready";

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const result = await listVideos({
      page: page.value,
      per_page: 20,
      genre_id: genreId.value ?? undefined,
      series_id: seriesId.value ?? undefined,
      status: status.value,
      q: appliedQuery.value || undefined,
      sort: sort.value,
      order: order.value,
    });
    videos.value = result.items;
    pagination.value = result.pagination;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}

function apply(): void {
  page.value = 1;
  void load();
}

function search(): void {
  appliedQuery.value = query.value.trim();
  apply();
}

function clearSearch(): void {
  query.value = "";
  search();
}

function changePage(next: number): void {
  page.value = next;
  void load();
}

onMounted(async () => {
  void load();
  // 続きから視聴・絞り込みの候補の取得に失敗しても、一覧は表示する
  getLastPlayback()
    .then((result) => (last.value = result))
    .catch(() => (last.value = null));
  Promise.all([listGenres(), listSeries(1, undefined, 100)])
    .then(([g, s]) => {
      genres.value = g.items;
      seriesList.value = s.items;
    })
    .catch(() => undefined);
});
</script>

<template>
  <section class="page">
    <div class="page-head">
      <h2>動画</h2>
      <button class="btn-primary push-end" type="button" aria-label="新規" @click="router.push('/register')">
        <Icon name="plus" />
      </button>
    </div>

    <div v-if="last && hasLast" class="resume-panel collapsible" :class="{ open: resumeOpen }">
      <div v-if="last.video" class="resume-card">
        <div class="body">
          <span class="caption">続きから視聴（動画）</span>
          <span class="row-title clamp">{{ last.video.title }}</span>
          <span class="caption">{{ formatMs(last.video.position_ms) }} / {{ formatMs(last.video.duration_ms) }}</span>
        </div>
        <button class="btn-primary" type="button" @click="router.push({ path: `/videos/${last.video.video_id}`, query: { start: 'resume' } })">
          続きから再生
        </button>
      </div>
      <div v-if="last.playlist" class="resume-card">
        <div class="body">
          <span class="caption">続きから視聴（プレイリスト {{ last.playlist.playlist_name }}）</span>
          <span class="row-title clamp">{{ last.playlist.video_title }}</span>
          <span class="caption">{{ formatMs(last.playlist.position_ms) }} / {{ formatMs(last.playlist.duration_ms) }}</span>
        </div>
        <button
          class="btn-primary"
          type="button"
          @click="router.push({ path: `/playlists/${last.playlist.playlist_id}/play`, query: { start: 'resume' } })"
        >
          続きから再生
        </button>
      </div>
    </div>

    <div class="page-head">
      <form class="search" role="search" @submit.prevent="search">
        <input v-model="query" type="search" placeholder="タイトルで検索" aria-label="タイトルで検索" />
        <button class="btn-secondary" type="submit">検索</button>
        <button class="btn-text" type="button" aria-label="クリア" :disabled="!query && !appliedQuery" @click="clearSearch">
          <Icon name="close" />
        </button>
      </form>
      <button
        v-if="hasLast"
        class="btn-secondary mobile-only"
        type="button"
        :aria-expanded="resumeOpen"
        @click="resumeOpen = !resumeOpen"
      >
        続きから
      </button>
      <button
        class="btn-secondary mobile-only"
        type="button"
        :aria-expanded="filtersOpen"
        @click="filtersOpen = !filtersOpen"
      >
        絞り込み
      </button>
    </div>
    <div class="filters filters-collapsible" :class="{ open: filtersOpen }">
      <select v-model="genreId" aria-label="ジャンル" @change="apply">
        <option :value="null">ジャンル: すべて</option>
        <option v-for="genre in genres" :key="genre.id" :value="genre.id">{{ genre.name }}</option>
      </select>
      <select v-model="seriesId" aria-label="作品" @change="apply">
        <option :value="null">作品: すべて</option>
        <option v-for="series in seriesList" :key="series.id" :value="series.id">{{ series.title }}</option>
      </select>
      <select v-model="status" aria-label="状態" @change="apply">
        <option value="ready">状態: 再生可能</option>
        <option value="uploading">状態: 登録中</option>
        <option value="error">状態: エラー</option>
        <option value="all">状態: すべて</option>
      </select>
      <select v-model="sort" aria-label="並び項目" @change="apply">
        <option value="created_at">並び: 登録日時</option>
        <option value="title">並び: タイトル</option>
        <option value="last_played_at">並び: 最終再生日時</option>
      </select>
      <select v-model="order" aria-label="並び方向" @change="apply">
        <option value="desc">降順</option>
        <option value="asc">昇順</option>
      </select>
    </div>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="videos.length === 0" class="centered">
        {{ filtered() ? "該当するデータがありません" : "データがありません" }}
      </p>
      <div v-else class="card-grid">
        <VideoCard
          v-for="video in videos"
          :key="video.id"
          :video="video"
          @play="router.push(`/videos/${video.id}`)"
          @edit="router.push(`/videos/${video.id}/edit`)"
        />
      </div>
    </div>
    <div class="page-foot">
      <Pagination :pagination="pagination" :disabled="loading" @change="changePage" />
    </div>
  </section>
</template>
