<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { createCategory, deleteCategory, listCategories, updateCategory } from "../api/categories";
import { ApiError, AuthError } from "../api/client";
import type { Category } from "../api/types";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import Icon from "../components/Icon.vue";
import Notice from "../components/Notice.vue";

const emit = defineEmits<{ "auth-error": [error: unknown] }>();

const NAME_MAX = 100;

const categories = ref<Category[]>([]);
const loading = ref(true);
const errorMessage = ref("");
const successMessage = ref("");

// 追加欄
const newName = ref("");
const newFinancial = ref(false);
const newError = ref("");

// 編集中の行
const editingId = ref<number | null>(null);
const editName = ref("");
const editFinancial = ref(false);
const editError = ref("");

// 削除の確認
const deleting = ref<Category | null>(null);

let successTimer: ReturnType<typeof setTimeout> | undefined;

function showSuccess(message: string): void {
  successMessage.value = message;
  clearTimeout(successTimer);
  // 成功メッセージは、数秒で消える
  successTimer = setTimeout(() => {
    successMessage.value = "";
  }, 3000);
}

function handleError(error: unknown, fallback: string): string | null {
  if (error instanceof AuthError) {
    emit("auth-error", error);
    return null;
  }
  return fallback;
}

function validateName(name: string): string {
  const text = name.trim();
  if (text === "") {
    return "名称を入力してください";
  }
  if (text.length > NAME_MAX) {
    return `名称は ${NAME_MAX} 文字以内で入力してください`;
  }
  return "";
}

async function load(): Promise<void> {
  loading.value = true;
  try {
    categories.value = await listCategories();
    errorMessage.value = "";
  } catch (error) {
    const message = handleError(error, "読み込みに失敗しました");
    if (message !== null) {
      errorMessage.value = message;
    }
  } finally {
    loading.value = false;
  }
}

async function add(): Promise<void> {
  newError.value = validateName(newName.value);
  if (newError.value) {
    return;
  }
  errorMessage.value = "";
  try {
    await createCategory({ name: newName.value.trim(), is_financial: newFinancial.value });
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      newError.value = "同じ名称の区分があります";
      return;
    }
    const message = handleError(error, "追加に失敗しました");
    if (message !== null) {
      errorMessage.value = message;
    }
    return;
  }
  newName.value = "";
  newFinancial.value = false;
  newError.value = "";
  showSuccess("追加しました");
  await load();
}

function startEdit(category: Category): void {
  editingId.value = category.id;
  editName.value = category.name;
  editFinancial.value = category.is_financial;
  editError.value = "";
}

function cancelEdit(): void {
  editingId.value = null;
  editError.value = "";
}

async function saveEdit(category: Category): Promise<void> {
  editError.value = validateName(editName.value);
  if (editError.value) {
    return;
  }
  errorMessage.value = "";
  const name = editName.value.trim();
  try {
    await updateCategory(category.id, { name, is_financial: editFinancial.value });
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const unflagging = category.is_financial && !editFinancial.value;
      if (unflagging && name === category.name) {
        errorMessage.value = "支払方法として使われているため、金融機関の指定を外せません";
      } else if (unflagging) {
        errorMessage.value = "保存できませんでした。名称が重複しているか、支払方法として使われているため金融機関の指定を外せません";
      } else {
        editError.value = "同じ名称の区分があります";
      }
      return;
    }
    const message = handleError(error, "更新に失敗しました");
    if (message !== null) {
      errorMessage.value = message;
    }
    return;
  }
  editingId.value = null;
  showSuccess("更新しました");
  await load();
}

async function confirmDelete(): Promise<void> {
  const target = deleting.value;
  deleting.value = null;
  if (target === null) {
    return;
  }
  errorMessage.value = "";
  try {
    await deleteCategory(target.id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      errorMessage.value = "使用中のため削除できません";
      return;
    }
    const message = handleError(error, "削除に失敗しました");
    if (message !== null) {
      errorMessage.value = message;
    }
    return;
  }
  showSuccess("削除しました");
  await load();
}

onMounted(load);
onBeforeUnmount(() => clearTimeout(successTimer));
</script>

<template>
  <section class="page categories-page">
    <form class="toolbar category-add" @submit.prevent="add">
      <div class="field-group">
        <input
          v-model="newName"
          class="search-input"
          type="text"
          placeholder="区分名"
          aria-label="区分名"
          maxlength="200"
          autocomplete="off"
        />
        <p v-if="newError" class="field-error" role="alert">{{ newError }}</p>
      </div>
      <label class="check-label">
        <input v-model="newFinancial" type="checkbox" />
        金融機関
      </label>
      <button class="btn-primary btn-icon" type="submit" aria-label="新規" title="新規">
        <Icon name="new" />
      </button>
    </form>

    <Notice kind="success" :message="successMessage" />
    <Notice kind="error" :message="errorMessage" />

    <div v-if="loading" class="center-message list-state">
      <p class="caption">読み込み中…</p>
    </div>
    <div v-else class="list" role="table" aria-label="区分の一覧">
      <ul class="list-body">
        <li v-for="category in categories" :key="category.id" class="list-row category-row" role="row">
          <template v-if="editingId === category.id">
            <div class="field-group category-edit">
              <input
                v-model="editName"
                class="search-input"
                type="text"
                aria-label="区分名の編集"
                maxlength="200"
                autocomplete="off"
                @keydown.enter.prevent="saveEdit(category)"
              />
              <p v-if="editError" class="field-error" role="alert">{{ editError }}</p>
            </div>
            <label class="check-label">
              <input v-model="editFinancial" type="checkbox" />
              金融機関
            </label>
            <div class="row-actions">
              <button class="btn-primary btn-icon" type="button" aria-label="保存" title="保存" @click="saveEdit(category)">
                <Icon name="check" />
              </button>
              <button class="btn-secondary btn-icon" type="button" aria-label="キャンセル" title="キャンセル" @click="cancelEdit">
                <Icon name="close" />
              </button>
            </div>
          </template>
          <template v-else>
            <div class="cell category-name" role="cell">
              <span class="cell-title">{{ category.name }}</span>
              <span v-if="category.is_financial" class="badge">金融機関</span>
            </div>
            <div v-if="!category.is_default" class="row-actions">
              <button
                class="btn-secondary btn-icon"
                type="button"
                :aria-label="`${category.name}を編集`"
                title="編集"
                @click="startEdit(category)"
              >
                <Icon name="edit" />
              </button>
              <button
                class="btn-secondary btn-icon"
                type="button"
                :aria-label="`${category.name}を削除`"
                title="削除"
                @click="deleting = category"
              >
                <Icon name="delete" />
              </button>
            </div>
          </template>
        </li>
      </ul>
    </div>

    <ConfirmDialog
      v-if="deleting"
      title="区分の削除"
      :message="`区分「${deleting.name}」を削除しますか？`"
      @confirm="confirmDelete"
      @cancel="deleting = null"
    />
  </section>
</template>
