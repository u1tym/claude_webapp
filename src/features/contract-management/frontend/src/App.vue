<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { AuthError, getSettings, type Settings } from "./api/client";
import Icon, { type IconName } from "./components/Icon.vue";
import { navigateTo } from "./navigation";

const route = useRoute();
const settings = ref<Settings | null>(null);
const loadError = ref("");
const forbidden = ref(false);

const title = computed(() => String(route.meta.title ?? "契約管理"));

// ナビ（ui-design.md）: この順に常時表示する。アイコンは icons/ の素材から選んだもの
const navItems: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "アカウント一覧", icon: "login" },
  { to: "/contracts", label: "契約一覧", icon: "points" },
  { to: "/categories", label: "区分", icon: "config" },
  { to: "/cancellation", label: "解約順", icon: "stop" },
];

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
      <RouterLink v-for="item in navItems" :key="item.to" class="nav-item" :to="item.to">
        <Icon :name="item.icon" />
        <span class="nav-label">{{ item.label }}</span>
      </RouterLink>
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
