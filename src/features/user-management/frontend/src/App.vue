<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { getSettings, type Settings } from "./api";

const route = useRoute();
const settings = ref<Settings | null>(null);
const forbidden = ref(false);
const loading = ref(true);

const title = computed(() => {
  const value = route.meta.title;
  return typeof value === "string" ? value : "ユーザ管理";
});

onMounted(async () => {
  try {
    settings.value = await getSettings();
  } catch {
    settings.value = null;
  } finally {
    loading.value = false;
  }
});

function goMenu(): void {
  if (settings.value) {
    window.location.href = settings.value.menu_url;
  }
}

function onForbidden(): void {
  forbidden.value = true;
}

function onUnauth(): void {
  if (settings.value) {
    window.location.href = settings.value.login_url;
  }
}
</script>

<template>
  <div class="shell">
    <header class="header">
      <button class="btn-text" type="button" @click="goMenu">
        <img v-if="settings" class="header-icon" :src="settings.icon_back" alt="" />
        戻る
      </button>
      <h1 class="header-title">{{ title }}</h1>
      <img v-if="settings" class="header-icon" :src="settings.icon_system" alt="" />
    </header>
    <nav class="nav">
      <router-link to="/users">ユーザ</router-link>
      <router-link to="/features">機能</router-link>
      <router-link to="/assignments">割当</router-link>
    </nav>
    <main class="content">
      <p v-if="loading" class="loading">読み込み中…</p>
      <p v-else-if="forbidden" class="forbidden">この機能を使えません</p>
      <router-view v-else @forbidden="onForbidden" @unauth="onUnauth" />
    </main>
  </div>
</template>
