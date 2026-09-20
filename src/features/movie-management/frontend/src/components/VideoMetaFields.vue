<script setup lang="ts">
import type { Genre, Series, VideoMetaForm } from "../types";

// 動画の登録・編集で共通の入力欄（タイトル・説明・作品・話数・作品内順序・ジャンル）。
const meta = defineModel<VideoMetaForm>({ required: true });

defineProps<{
  seriesList: Series[];
  genres: Genre[];
  loadingMasters: boolean;
  disabled: boolean;
  allowNewSeries: boolean;
}>();

function toggleGenre(id: number): void {
  const ids = meta.value.genreIds;
  meta.value.genreIds = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

function onEpisodeInput(event: Event): void {
  const raw = (event.target as HTMLInputElement).value;
  meta.value.episodeNumber = raw === "" ? null : Number(raw);
}
</script>

<template>
  <div class="field">
    <label for="meta-title">タイトル（必須）</label>
    <input id="meta-title" v-model="meta.title" type="text" maxlength="500" :disabled="disabled" />
  </div>

  <div class="field">
    <label for="meta-desc">説明</label>
    <textarea id="meta-desc" v-model="meta.description" :disabled="disabled"></textarea>
  </div>

  <div class="field-row">
    <div class="field">
      <label for="meta-series">作品</label>
      <p v-if="loadingMasters" class="caption">読み込み中…</p>
      <select v-else id="meta-series" v-model="meta.seriesId" :disabled="disabled">
        <option :value="null">なし（単発）</option>
        <option v-for="series in seriesList" :key="series.id" :value="series.id">{{ series.title }}</option>
      </select>
    </div>
    <div v-if="allowNewSeries" class="field">
      <label for="meta-new-series">新しい作品のタイトル</label>
      <input
        id="meta-new-series"
        v-model="meta.newSeriesTitle"
        type="text"
        maxlength="500"
        placeholder="入力すると、新しい作品を作って属させます"
        :disabled="disabled"
      />
    </div>
  </div>

  <div class="field-row">
    <div class="field">
      <label for="meta-episode">話数</label>
      <input
        id="meta-episode"
        :value="meta.episodeNumber ?? ''"
        type="number"
        min="1"
        step="1"
        :disabled="disabled"
        @input="onEpisodeInput"
      />
    </div>
    <div class="field">
      <label for="meta-episode-title">話タイトル</label>
      <input id="meta-episode-title" v-model="meta.episodeTitle" type="text" maxlength="500" :disabled="disabled" />
    </div>
    <div class="field">
      <label for="meta-order">作品内順序</label>
      <input id="meta-order" v-model.number="meta.sortOrder" type="number" min="0" step="1" :disabled="disabled" />
    </div>
  </div>

  <div class="field">
    <span class="label">ジャンル</span>
    <p v-if="loadingMasters" class="caption">読み込み中…</p>
    <p v-else-if="genres.length === 0" class="caption">データがありません</p>
    <div v-else class="chips">
      <button
        v-for="genre in genres"
        :key="genre.id"
        class="chip"
        :class="{ 'is-on': meta.genreIds.includes(genre.id) }"
        type="button"
        :aria-pressed="meta.genreIds.includes(genre.id)"
        :disabled="disabled"
        @click="toggleGenre(genre.id)"
      >
        {{ genre.name }}
      </button>
    </div>
  </div>
</template>
