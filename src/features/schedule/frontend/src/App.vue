<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterView } from "vue-router";
import { AuthError, getSettings, type Settings } from "./api";
import iconBack from "./assets/icon-back.png";
import iconEdit from "./assets/icon-edit.png";
import iconNew from "./assets/icon-new.png";
import iconSettings from "./assets/icon-settings.png";
import iconTrash from "./assets/icon-trash.png";
import {
  addCategoryNav,
  categoryNavBusy,
  categoryNavItems,
  categoryNavShowDeleted,
  editCategoryNav,
  openCategoryNavMobile,
  removeCategoryNav,
  toggleCategoryNav,
  toggleCategoryNavDeleted,
} from "./category-nav";
import { openHolidaySettings } from "./holiday-settings";
import { monthLinks, selectMonth } from "./month-nav";

const settings = ref<Settings | null>(null);
const loadError = ref("");
const forbidden = ref(false);

function goMenu(): void {
  if (settings.value) {
    window.location.href = settings.value.menu_url;
  }
}

function onAuthError(error: unknown): void {
  if (error instanceof AuthError && error.status === 401 && settings.value) {
    window.location.href = settings.value.login_url;
    return;
  }
  if (error instanceof AuthError && error.status === 403) {
    forbidden.value = true;
  }
}

onMounted(async () => {
  try {
    settings.value = await getSettings();
  } catch {
    loadError.value = "Server error";
  }
});
</script>

<template>
  <div v-if="loadError" class="forbidden">
    <p class="msg-error">{{ loadError }}</p>
  </div>
  <div v-else-if="forbidden" class="shell">
    <header class="header">
      <button v-if="settings" class="btn-text" type="button" @click="goMenu">
        <img class="header-icon" :src="iconBack" alt="" />
        Back
      </button>
      <h1 class="header-title">Schedule</h1>
      <img v-if="settings?.icon_system" class="header-icon" :src="settings.icon_system" alt="" />
    </header>
    <nav class="nav" aria-label="Navigation">
      <div class="nav-brand">Schedule</div>
    </nav>
    <main class="content forbidden">
      <p>This feature is unavailable</p>
      <button v-if="settings" class="btn-secondary" type="button" @click="goMenu">Back</button>
    </main>
  </div>
  <div v-else-if="settings" class="shell">
    <header class="header">
      <button class="btn-text" type="button" @click="goMenu">
        <img class="header-icon" :src="iconBack" alt="" />
        Back
      </button>
      <h1 class="header-title">Schedule</h1>
      <img v-if="settings.icon_system" class="header-icon" :src="settings.icon_system" alt="" />
      <button class="btn-text btn-icon" type="button" aria-label="Settings" @click="openHolidaySettings">
        <img class="header-icon header-icon-lg" :src="iconSettings" alt="" />
      </button>
    </header>
    <nav class="nav" aria-label="Navigation">
      <div class="nav-top">
        <div class="nav-brand">Schedule</div>
        <button
          class="nav-item mobile-only"
          type="button"
          :disabled="categoryNavBusy"
          @click="openCategoryNavMobile"
        >
          Categories
        </button>
      </div>
      <div class="nav-months pc-only">
        <button
          v-for="item in monthLinks"
          :key="`${item.year}-${item.monthIndex}`"
          class="nav-month"
          :class="{ 'is-current': item.current }"
          type="button"
          @click="selectMonth(item.year, item.monthIndex)"
        >
          {{ item.label }}
        </button>
      </div>
      <section class="nav-categories pc-only">
        <div class="nav-cat-head">
          <h2>Categories</h2>
          <button
            class="btn-text btn-icon"
            type="button"
            aria-label="New"
            :disabled="categoryNavBusy"
            @click="addCategoryNav"
          >
            <img class="header-icon" :src="iconNew" alt="" />
          </button>
        </div>
        <div class="nav-cat-body">
          <p v-if="categoryNavItems.length === 0" class="caption">No data</p>
          <ul class="plain-list">
            <li
              v-for="item in categoryNavItems"
              :key="item.id"
              class="nav-cat-row"
              :class="{ muted: item.hidden }"
              @click="toggleCategoryNav(item.id)"
            >
              <span class="swatch" :style="{ background: item.color }"></span>
              <span class="nav-cat-name">{{ item.name }}{{ item.isDeleted ? " (deleted)" : "" }}</span>
              <span v-if="!item.isDeleted" class="row-actions">
                <button
                  class="btn-text btn-icon-sm"
                  type="button"
                  aria-label="Edit"
                  @click.stop="editCategoryNav(item.id, $event)"
                >
                  <img class="row-icon" :src="iconEdit" alt="" />
                </button>
                <button
                  class="btn-text btn-icon-sm"
                  type="button"
                  aria-label="Delete"
                  @click.stop="removeCategoryNav(item.id)"
                >
                  <img class="row-icon" :src="iconTrash" alt="" />
                </button>
              </span>
            </li>
          </ul>
          <button class="btn-text" type="button" :disabled="categoryNavBusy" @click="toggleCategoryNavDeleted">
            {{ categoryNavShowDeleted ? "Hide deleted" : "Show deleted" }}
          </button>
        </div>
      </section>
    </nav>
    <main class="content">
      <RouterView @auth-error="onAuthError" />
    </main>
  </div>
</template>
