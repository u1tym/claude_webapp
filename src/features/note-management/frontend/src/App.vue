<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { AuthError, getSettings, setAuthHandler } from "./api";
import Icon from "./components/Icon.vue";
import type { NavKey } from "./router";
import type { Settings } from "./types";

const NAV_ITEMS: { key: NavKey; label: string; path: string }[] = [
  { key: "notes", label: "ノート", path: "/" },
];

const route = useRoute();
const router = useRouter();

const settings = ref<Settings | null>(null);
const loadError = ref("");
const forbidden = ref(false);

const current = computed<NavKey | undefined>(() => route.meta.nav);

function goMenu(): void {
  if (settings.value) {
    window.location.href = settings.value.menu_url;
  }
}

function onAuthError(error: AuthError): void {
  if (error.status === 401 && settings.value) {
    // 未ログインは、画面を表示せずログイン画面へ進む
    window.location.href = settings.value.login_url;
    return;
  }
  if (error.status === 403) {
    forbidden.value = true;
  }
}

onMounted(async () => {
  setAuthHandler(onAuthError);
  try {
    settings.value = await getSettings();
  } catch {
    loadError.value = "サーバエラーです";
  }
});

onBeforeUnmount(() => setAuthHandler(null));
</script>

<template>
  <div v-if="loadError" class="forbidden">
    <p class="msg-error">{{ loadError }}</p>
  </div>
  <div v-else-if="settings" class="shell">
    <header class="header">
      <button class="btn-text" type="button" aria-label="戻る" @click="goMenu">
        <Icon name="back" />
      </button>
      <h1 class="header-title">ノート</h1>
      <img v-if="settings.icon_system" class="header-icon" :src="settings.icon_system" alt="" />
    </header>
    <nav class="nav" aria-label="ナビ">
      <button
        v-for="item in NAV_ITEMS"
        :key="item.key"
        class="nav-item"
        :class="{ 'is-current': current === item.key }"
        type="button"
        :aria-current="current === item.key ? 'page' : undefined"
        @click="router.push(item.path)"
      >
        {{ item.label }}
      </button>
    </nav>
    <main class="content">
      <div v-if="forbidden" class="forbidden">
        <p>この機能を使えません</p>
        <button class="btn-secondary" type="button" aria-label="戻る" @click="goMenu">
          <Icon name="back" />
        </button>
      </div>
      <RouterView v-else />
    </main>
  </div>
</template>
