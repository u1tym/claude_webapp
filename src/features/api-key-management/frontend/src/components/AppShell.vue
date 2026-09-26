<script setup lang="ts">
import type { Settings } from "../api/client";
import Icon from "./Icon.vue";

defineProps<{ settings: Settings | null }>();
</script>

<template>
  <div class="shell">
    <header class="header">
      <img v-if="settings?.icon_system" class="system-icon" :src="settings.icon_system" alt="" />
      <h1 class="header-title">API キー管理</h1>
      <a
        v-if="settings"
        class="btn btn-text header-back"
        :href="settings.menu_url"
        aria-label="戻る"
      >
        <Icon name="back" />
      </a>
    </header>
    <nav class="nav" aria-label="機能内メニュー">
      <RouterLink to="/" class="nav-item" active-class="nav-item-active">
        <Icon name="config" />
        <span>API キー</span>
      </RouterLink>
    </nav>
    <main class="content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 200px 1fr;
  grid-template-rows: auto 1fr;
  grid-template-areas:
    "header header"
    "nav content";
  height: 100%;
}

.header {
  grid-area: header;
  display: flex;
  align-items: center;
  gap: calc(var(--space) * 2);
  padding: var(--space) calc(var(--space) * 3);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-primary);
}

.system-icon {
  width: 32px;
  height: 32px;
}

.header-title {
  flex: 1;
  margin: 0;
  font-size: var(--font-size-title);
  font-weight: 600;
}

.header-back {
  color: var(--color-text);
}

.nav {
  grid-area: nav;
  display: flex;
  flex-direction: column;
  gap: var(--space);
  padding: calc(var(--space) * 2) var(--space);
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space);
  min-height: var(--tap);
  padding: 0 calc(var(--space) * 2);
  border-radius: var(--radius);
  border-left: 4px solid transparent;
  color: var(--color-text);
  text-decoration: none;
}

.nav-item:focus-visible {
  outline: 2px solid var(--color-primary);
}

.nav-item-active {
  border-left-color: var(--color-primary);
  background: rgba(242, 201, 76, 0.16);
  font-weight: 600;
}

.content {
  grid-area: content;
  min-height: 0;
  overflow: hidden;
  padding: calc(var(--space) * 3);
}

@media (max-width: 767px) {
  .shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
    grid-template-areas:
      "header"
      "content"
      "nav";
  }

  .header {
    padding: var(--space) calc(var(--space) * 2);
  }

  .nav {
    flex-direction: row;
    justify-content: center;
    padding: 0 var(--space);
    border-right: none;
    border-top: 1px solid var(--color-border);
  }

  .nav-item {
    flex-direction: column;
    justify-content: center;
    gap: 0;
    font-size: 12px;
    border-left: none;
    border-top: 3px solid transparent;
    border-radius: 0;
  }

  .nav-item-active {
    border-top-color: var(--color-primary);
    background: transparent;
  }

  .content {
    padding: calc(var(--space) * 2);
  }
}
</style>
