<script setup lang="ts">
import { computed } from "vue";
import { thumbnailUrl } from "../api";
import type { VideoSummary } from "../types";
import { formatMs, progressPercent, statusLabel } from "../utils/format";
import Icon from "./Icon.vue";

const props = defineProps<{ video: VideoSummary }>();
const emit = defineEmits<{ play: []; edit: [] }>();

const percent = computed(() => progressPercent(props.video.position_ms, props.video.duration_ms));
const episode = computed(() => {
  const parts: string[] = [];
  if (props.video.episode_number !== null) {
    parts.push(`第${props.video.episode_number}話`);
  }
  if (props.video.episode_title) {
    parts.push(props.video.episode_title);
  }
  return parts.join(" ");
});
</script>

<template>
  <article class="card">
    <button class="card-main" type="button" :aria-label="`${video.title}を再生`" @click="emit('play')">
      <div class="thumb">
        <img v-if="video.has_thumbnail" :src="thumbnailUrl(video.id)" alt="" loading="lazy" />
        <span v-else>画像なし</span>
        <span v-if="video.status !== 'ready'" class="badge danger">{{ statusLabel(video.status) }}</span>
        <span v-else-if="video.completed" class="badge primary">視聴済み</span>
      </div>
      <div v-if="percent > 0 && !video.completed" class="progress" aria-hidden="true">
        <span :style="{ width: `${percent}%` }"></span>
      </div>
      <div class="card-body">
        <span class="card-title">{{ video.title }}</span>
        <span v-if="video.series_title || episode" class="caption">
          {{ [video.series_title, episode].filter(Boolean).join(" / ") }}
        </span>
        <span class="caption">
          {{ formatMs(video.duration_ms) }}
          <template v-if="video.position_ms !== null && video.position_ms > 0 && !video.completed">
            ・{{ formatMs(video.position_ms) }} まで視聴
          </template>
        </span>
        <span v-if="video.genres.length" class="chips">
          <span v-for="genre in video.genres" :key="genre.id" class="badge">{{ genre.name }}</span>
        </span>
      </div>
    </button>
    <button class="btn-text card-edit" type="button" aria-label="編集" @click="emit('edit')">
      <Icon name="edit" />
    </button>
  </article>
</template>
