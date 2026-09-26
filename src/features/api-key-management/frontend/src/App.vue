<script setup lang="ts">
import { onMounted, provide, ref } from "vue";
import { fetchSettings, setLoginUrl, type Settings } from "./api/client";
import AppShell from "./components/AppShell.vue";

const settings = ref<Settings | null>(null);
provide("settings", settings);

onMounted(async () => {
  try {
    const loaded = await fetchSettings();
    setLoginUrl(loaded.login_url);
    settings.value = loaded;
  } catch {
    settings.value = null;
  }
});
</script>

<template>
  <AppShell :settings="settings">
    <RouterView />
  </AppShell>
</template>
