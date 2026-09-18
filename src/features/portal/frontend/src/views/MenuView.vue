<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getMenu, logMenuNavigation, logout, type MenuItem } from "../api";

const router = useRouter();
const items = ref<MenuItem[]>([]);
const loading = ref(true);
const error = ref("");
const logoutBusy = ref(false);

onMounted(async () => {
  loading.value = true;
  error.value = "";
  try {
    items.value = await getMenu();
    console.log(
      "[portal menu] 取得",
      items.value.map((item) => ({ id: item.id, title: item.title, url: item.url })),
    );
  } catch (exc) {
    if (exc instanceof Error && exc.message === "unauth") {
      await router.replace("/login");
      return;
    }
    error.value = "メニューを取得できませんでした";
  } finally {
    loading.value = false;
  }
});

async function openFeature(item: MenuItem): Promise<void> {
  const fromDb = item.url;
  let destination = "";
  let errorMessage = "";
  try {
    const target = new URL(fromDb, window.location.origin);
    target.searchParams.set("a", String(Math.floor(Math.random() * 1_000_000_000)));
    destination = target.href;
  } catch (exc) {
    errorMessage = exc instanceof Error ? exc.message : String(exc);
  }
  console.log("[portal menu] 遷移", {
    id: item.id,
    title: item.title,
    fromDb,
    destination,
    currentPage: window.location.href,
    error: errorMessage || undefined,
  });
  try {
    await logMenuNavigation({
      id: item.id,
      title: item.title,
      from_db: fromDb,
      destination,
      error: errorMessage,
    });
  } catch {
    // 遷移はログ失敗でも続ける
  }
  if (destination) {
    window.location.href = destination;
  }
}

async function onLogout(): Promise<void> {
  logoutBusy.value = true;
  try {
    await logout();
  } finally {
    logoutBusy.value = false;
    await router.push("/login");
  }
}
</script>

<template>
  <div class="menu-page">
    <button
      class="btn-logout"
      type="button"
      :disabled="loading || logoutBusy"
      @click="onLogout"
    >
      ログアウト
    </button>
    <p v-if="error" class="banner-error">{{ error }}</p>
    <div v-if="loading" class="loading">読み込み中…</div>
    <div v-else-if="items.length === 0" class="empty">データがありません</div>
    <div v-else class="cards">
      <button
        v-for="item in items"
        :key="item.id"
        class="feature-card"
        type="button"
        @click="openFeature(item)"
      >
        <img v-if="item.icon" :src="item.icon" alt="" />
        <span>{{ item.title }}</span>
      </button>
    </div>
  </div>
</template>
