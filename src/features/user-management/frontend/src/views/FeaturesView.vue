<script setup lang="ts">
import { onMounted, ref } from "vue";
import { createFeature, deleteFeature, getFeatures, updateFeature, type FeatureItem } from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const items = ref<FeatureItem[]>([]);
const loading = ref(true);
const error = ref("");
const success = ref("");
const mode = ref<"list" | "create" | "edit">("list");
const selected = ref<FeatureItem | null>(null);
const featureId = ref("");
const title = ref("");
const url = ref("");
const icon = ref("");
const preview = ref("");
const confirmId = ref<string | null>(null);

onMounted(() => {
  void reload();
});

async function reload(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    items.value = await getFeatures();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}

function handle(err: unknown): void {
  if (err instanceof Error && err.message === "unauth") {
    emit("unauth");
    return;
  }
  if (err instanceof Error && err.message === "forbidden") {
    emit("forbidden");
    return;
  }
  error.value = "取得できませんでした";
}

function startCreate(): void {
  mode.value = "create";
  selected.value = null;
  featureId.value = "";
  title.value = "";
  url.value = "";
  icon.value = "";
  preview.value = "";
}

function startEdit(item: FeatureItem): void {
  mode.value = "edit";
  selected.value = item;
  featureId.value = item.id;
  title.value = item.title;
  url.value = item.url;
  icon.value = "";
  preview.value = item.icon;
}

function cancel(): void {
  mode.value = "list";
  selected.value = null;
}

function onFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    icon.value = String(reader.result);
    preview.value = icon.value;
  };
  reader.readAsDataURL(file);
}

async function save(): Promise<void> {
  error.value = "";
  success.value = "";
  if (title.value.trim() === "" || url.value.trim() === "") {
    return;
  }
  if (mode.value === "create" && (featureId.value.trim() === "" || icon.value === "")) {
    return;
  }
  loading.value = true;
  try {
    if (mode.value === "create") {
      const result = await createFeature(featureId.value, title.value, url.value, icon.value);
      if (result === "invalid" || result === "conflict") {
        error.value = result === "invalid" ? "入力が不正です" : "保存できませんでした";
        return;
      }
    } else if (selected.value) {
      const result = await updateFeature(selected.value.id, title.value, url.value, icon.value);
      if (result === "invalid" || result === "missing") {
        error.value = result === "invalid" ? "入力が不正です" : "対象がありません";
        return;
      }
    }
    success.value = "保存しました";
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
    cancel();
    items.value = await getFeatures();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}

async function confirmDelete(): Promise<void> {
  if (confirmId.value === null) {
    return;
  }
  loading.value = true;
  try {
    const result = await deleteFeature(confirmId.value);
    confirmId.value = null;
    if (result !== "ok") {
      error.value = "削除できませんでした";
      return;
    }
    success.value = "削除しました";
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
    cancel();
    items.value = await getFeatures();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <p v-if="error" class="banner-error">{{ error }}</p>
  <p v-if="success" class="banner-ok">{{ success }}</p>
  <p v-if="loading" class="loading">読み込み中…</p>
  <div v-else class="split" :class="mode === 'list' ? 'mobile-list' : 'mobile-form'">
    <section class="panel list-panel">
      <div class="actions">
        <button class="btn-primary" type="button" :disabled="loading" @click="startCreate">新規</button>
      </div>
      <div class="list">
        <p v-if="items.length === 0" class="empty">データがありません</p>
        <table v-else>
          <thead>
            <tr>
              <th>アイコン</th>
              <th>識別子</th>
              <th>タイトル</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id" :class="{ selected: selected?.id === item.id }">
              <td>
                <button class="row" type="button" @click="startEdit(item)">
                  <img v-if="item.icon" class="thumb" :src="item.icon" alt="" />
                </button>
              </td>
              <td>
                <button class="row" type="button" @click="startEdit(item)">{{ item.id }}</button>
              </td>
              <td>
                <button class="row" type="button" @click="startEdit(item)">{{ item.title }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="mode !== 'list'" class="panel form-panel">
      <form class="form" @submit.prevent="save">
        <input
          v-model="featureId"
          type="text"
          placeholder="識別子"
          aria-label="識別子"
          :disabled="loading || mode === 'edit'"
          required
        />
        <input v-model="title" type="text" placeholder="タイトル" aria-label="タイトル" :disabled="loading" required />
        <input v-model="url" type="text" placeholder="遷移先" aria-label="遷移先" :disabled="loading" required />
        <input type="file" accept="image/*" aria-label="アイコン" :disabled="loading" @change="onFile" />
        <img v-if="preview" class="thumb" :src="preview" alt="" />
        <div class="actions">
          <button class="btn-primary" type="submit" :disabled="loading">保存</button>
          <button class="btn-secondary" type="button" :disabled="loading" @click="cancel">キャンセル</button>
          <button
            v-if="mode === 'edit' && selected && !selected.is_protected"
            class="btn-text danger"
            type="button"
            :disabled="loading"
            @click="confirmId = selected.id"
          >
            削除
          </button>
        </div>
      </form>
    </section>
  </div>
  <div v-if="confirmId !== null" class="modal-back">
    <div class="modal">
      <p>削除しますか？</p>
      <div class="actions">
        <button class="btn-primary" type="button" @click="confirmDelete">削除</button>
        <button class="btn-secondary" type="button" @click="confirmId = null">キャンセル</button>
      </div>
    </div>
  </div>
</template>
