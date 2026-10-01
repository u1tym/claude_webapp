<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { AuthError, getSettings, type Settings } from "./api";
import Icon from "./components/Icon.vue";
import { navigateTo } from "./navigation";

const route = useRoute();
const settings = ref<Settings | null>(null);
const loadError = ref("");
const forbidden = ref(false);

const title = computed(() => String(route.meta.title ?? "ROOM"));

function goMenu(): void {
  if (settings.value) {
    navigateTo(settings.value.menu_url);
  }
}

/** 子の画面から受けた認証の失敗を処理する。未ログインはログイン画面へ、権限なしは専用の表示へ。 */
function onAuthError(error: unknown): void {
  if (!(error instanceof AuthError)) {
    return;
  }
  if (error.status === 401 && settings.value) {
    navigateTo(settings.value.login_url);
    return;
  }
  if (error.status === 403) {
    forbidden.value = true;
  }
}

onMounted(async () => {
  try {
    settings.value = await getSettings();
  } catch {
    loadError.value = "サーバエラーです";
  }
});
</script>

<template>
  <div v-if="loadError" class="center-message">
    <p class="msg-error" role="alert">{{ loadError }}</p>
  </div>
  <div v-else-if="!settings" class="center-message">
    <p class="caption">読み込み中…</p>
  </div>
  <div v-else class="shell">
    <header class="header">
      <button class="btn-text btn-icon" type="button" aria-label="戻る" @click="goMenu">
        <Icon name="back" />
      </button>
      <h1 class="header-title">{{ title }}</h1>
      <img v-if="settings.icon_system" class="header-icon" :src="settings.icon_system" alt="" />
    </header>
    <nav class="nav" aria-label="ナビゲーション">
      <RouterLink class="nav-item" to="/">ROOM</RouterLink>
      <RouterLink class="nav-item" to="/schedules">定期実行</RouterLink>
    </nav>
    <main v-if="forbidden" class="content center-message">
      <p>この機能は利用できません</p>
      <button class="btn-secondary btn-icon" type="button" aria-label="戻る" @click="goMenu">
        <Icon name="back" />
      </button>
    </main>
    <main v-else class="content">
      <RouterView @auth-error="onAuthError" />
    </main>
  </div>
</template>
