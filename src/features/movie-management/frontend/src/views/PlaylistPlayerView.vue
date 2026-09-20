<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError, errorMessage, getLastPlayback, getPlaylist } from "../api";
import Icon from "../components/Icon.vue";
import PlayerStage from "../components/PlayerStage.vue";
import { playlistBackend } from "../composables/playerBackends";
import { usePlayer } from "../composables/usePlayer";
import type { PlaylistDetail } from "../types";

const props = defineProps<{ id: string }>();
const route = useRoute();
const router = useRouter();

const playlist = ref<PlaylistDetail | null>(null);
const resumeMs = ref<number | null>(null);
const error = ref("");
const notFound = ref(false);

const playlistId = Number(props.id);
const player = usePlayer(playlistBackend(playlistId));

const empty = computed(() => playlist.value !== null && playlist.value.items.length === 0);

function start(resume: boolean): void {
  void player.begin(resume);
}

onMounted(async () => {
  try {
    playlist.value = await getPlaylist(playlistId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound.value = true;
    } else {
      error.value = errorMessage(e);
    }
    return;
  }
  // このプレイリストで最後に再生した動画があれば、「続きから再生」を出す
  try {
    const last = await getLastPlayback();
    if (last.playlist && last.playlist.playlist_id === playlistId && last.playlist.position_ms > 0) {
      resumeMs.value = last.playlist.position_ms;
    } else if (last.playlist && last.playlist.playlist_id === playlistId) {
      resumeMs.value = 0;
    }
  } catch {
    resumeMs.value = null;
  }
  if (route.query.start === "resume" && !empty.value) {
    start(true);
  }
});
</script>

<template>
  <section class="page player-page">
    <div class="page-head">
      <button class="btn-text" type="button" aria-label="戻る" @click="router.push('/playlists')">
        <Icon name="back" />
      </button>
      <div class="player-info">
        <h2>{{ playlist?.name ?? "プレイリスト" }}</h2>
        <p v-if="player.item.value" class="caption">{{ player.item.value.title }}</p>
      </div>
    </div>
    <p v-if="error" class="msg-error">{{ error }}</p>

    <div class="page-body">
      <p v-if="notFound" class="centered">プレイリストが見つかりません</p>
      <div v-else-if="empty" class="centered">
        <div class="player-info">
          <p>このプレイリストには動画がありません</p>
          <div class="actions">
            <button class="btn-secondary" type="button" aria-label="編集" @click="router.push(`/playlists/${playlistId}/edit`)">
              <Icon name="edit" />
            </button>
          </div>
        </div>
      </div>
      <PlayerStage
        v-else
        :player="player"
        :poster-url="null"
        :resume-ms="resumeMs"
        :show-prev="true"
        @start="start"
      />
    </div>
  </section>
</template>
