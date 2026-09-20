<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError, errorMessage, getVideo, thumbnailUrl } from "../api";
import Icon from "../components/Icon.vue";
import PlayerStage from "../components/PlayerStage.vue";
import { videoBackend } from "../composables/playerBackends";
import { usePlayer, type PlayItem } from "../composables/usePlayer";
import type { VideoDetail } from "../types";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();

const detail = ref<VideoDetail | null>(null);
const error = ref("");
const notFound = ref(false);

const videoId = (): number => Number(props.id);

// 次の動画へ進んだときは、URL も次の動画にそろえる（履歴には積まない）
function onItemChange(next: PlayItem): void {
  if (next.videoId !== videoId()) {
    void router.replace(`/videos/${next.videoId}`);
  }
}

const player = usePlayer(videoBackend(videoId), onItemChange);

const heading = computed(() => player.item.value?.title ?? detail.value?.title ?? "動画");
const subtitle = computed(() => {
  const d = detail.value;
  if (!d || (player.item.value && player.item.value.videoId !== d.id)) {
    return "";
  }
  const parts: string[] = [];
  if (d.series_title) parts.push(d.series_title);
  if (d.episode_number !== null) parts.push(`第${d.episode_number}話`);
  if (d.episode_title) parts.push(d.episode_title);
  return parts.join(" ");
});
const resumeMs = computed(() => {
  const d = detail.value;
  return d && d.position_ms !== null && d.position_ms > 0 && !d.completed ? d.position_ms : null;
});

async function loadDetail(id: number): Promise<void> {
  try {
    detail.value = await getVideo(id);
    notFound.value = false;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound.value = true;
    } else {
      error.value = errorMessage(e);
    }
  }
}

function start(resume: boolean): void {
  void player.begin(resume);
}

onMounted(async () => {
  await loadDetail(videoId());
  if (route.query.start === "resume" && !notFound.value) {
    start(true);
  }
});

// 別の動画の URL へ移ったとき（次の動画への自動遷移による URL の更新は除く）
watch(
  () => props.id,
  async (id) => {
    if (player.item.value?.videoId === Number(id)) {
      await loadDetail(Number(id));
      return;
    }
    error.value = "";
    await loadDetail(Number(id));
    start(true);
  },
);
</script>

<template>
  <section class="page player-page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" @click="router.push('/')">
        <Icon name="back" />
      </button>
      <div class="player-info">
        <h2>{{ heading }}</h2>
        <p v-if="subtitle" class="caption">{{ subtitle }}</p>
      </div>
    </div>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="notFound" class="centered">動画が見つかりません</p>
      <PlayerStage
        v-else
        :player="player"
        :poster-url="detail?.has_thumbnail ? thumbnailUrl(detail.id) : null"
        :resume-ms="resumeMs"
        @start="start"
      />
    </div>
  </section>
</template>
