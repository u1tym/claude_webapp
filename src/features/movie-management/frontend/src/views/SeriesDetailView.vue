<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ApiError, errorMessage, getSeries } from "../api";
import Icon from "../components/Icon.vue";
import type { SeriesDetail } from "../types";
import { formatMs, statusLabel } from "../utils/format";

const props = defineProps<{ id: string }>();
const router = useRouter();

const series = ref<SeriesDetail | null>(null);
const loading = ref(true);
const error = ref("");
const notFound = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    series.value = await getSeries(Number(props.id));
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

onMounted(load);
</script>

<template>
  <section class="page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" @click="router.push('/series')">
        <Icon name="back" />
      </button>
      <h2>{{ series?.title ?? "作品" }}</h2>
    </div>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="loading" class="centered">読み込み中…</p>
      <p v-else-if="notFound" class="centered">作品が見つかりません</p>
      <template v-else-if="series">
        <p v-if="series.description" class="caption">{{ series.description }}</p>
        <p v-if="series.videos.length === 0" class="centered">データがありません</p>
        <ul v-else class="rows">
          <li v-for="video in series.videos" :key="video.id" class="row">
            <button
              class="row-button"
              type="button"
              :disabled="video.status !== 'ready'"
              @click="router.push(`/videos/${video.id}`)"
            >
              <span class="row-title">
                <template v-if="video.episode_number !== null">第{{ video.episode_number }}話 </template>
                {{ video.episode_title || video.title }}
              </span>
              <span class="row-meta">
                <span>{{ formatMs(video.duration_ms) }}</span>
                <span v-if="video.status !== 'ready'" class="badge danger">{{ statusLabel(video.status) }}</span>
              </span>
            </button>
          </li>
        </ul>
      </template>
    </div>
  </section>
</template>
