<script setup lang="ts">
import { inject, onMounted, ref } from "vue";
import {
  AuthError,
  createPassword,
  deletePassword,
  getPassword,
  getPasswords,
  updatePassword,
  type PasswordEntry,
  type PasswordInput,
  type PasswordSummary,
} from "../api";
import Icon from "../components/Icon.vue";

const onAuthError = inject<(error: unknown) => void>("onAuthError");

const loading = ref(true);
const errorMessage = ref("");
const successMessage = ref("");
const items = ref<PasswordSummary[]>([]);
const keyword = ref("");
let searchTimer: ReturnType<typeof setTimeout> | null = null;
let successTimer: ReturnType<typeof setTimeout> | null = null;

const detailEntry = ref<PasswordEntry | null>(null);
const detailLoading = ref(false);
const showPassword = ref(false);
const copiedField = ref<"userword" | "psword" | null>(null);
let copiedTimer: ReturnType<typeof setTimeout> | null = null;

const showForm = ref(false);
const editingId = ref<number | null>(null);
const formError = ref("");
const submitting = ref(false);
const title = ref("");
const userword = ref("");
const psword = ref("");
const site = ref("");
const memo = ref("");
const formShowPassword = ref(false);
const invalidTitle = ref(false);
const invalidUserword = ref(false);
const invalidPsword = ref(false);

const deleteTarget = ref<{ id: number; title: string } | null>(null);
const deleting = ref(false);
const deleteError = ref("");

function handleError(err: unknown): void {
  if (err instanceof AuthError) {
    onAuthError?.(err);
    return;
  }
  errorMessage.value = "読み込みに失敗しました";
}

function showSuccess(message: string): void {
  if (successTimer) clearTimeout(successTimer);
  successMessage.value = message;
  successTimer = window.setTimeout(() => {
    successMessage.value = "";
  }, 3000);
}

async function loadList(): Promise<void> {
  try {
    items.value = await getPasswords(keyword.value);
  } catch (err) {
    handleError(err);
  }
}

function onSearchInput(): void {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    void loadList();
  }, 300);
}

onMounted(async () => {
  try {
    items.value = await getPasswords();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});

async function openDetail(item: PasswordSummary): Promise<void> {
  errorMessage.value = "";
  detailEntry.value = null;
  showPassword.value = false;
  copiedField.value = null;
  detailLoading.value = true;
  try {
    const result = await getPassword(item.id);
    if (result === "missing") {
      errorMessage.value = "対象が見つかりません";
      await loadList();
      return;
    }
    detailEntry.value = result;
  } catch (err) {
    handleError(err);
  } finally {
    detailLoading.value = false;
  }
}

function closeDetail(): void {
  detailEntry.value = null;
}

async function copyField(value: string, field: "userword" | "psword"): Promise<void> {
  try {
    await navigator.clipboard.writeText(value);
    if (copiedTimer) clearTimeout(copiedTimer);
    copiedField.value = field;
    copiedTimer = window.setTimeout(() => {
      copiedField.value = null;
    }, 2000);
  } catch {
    // Clipboard access can be denied by the browser; leave the value on screen instead.
  }
}

function openCreateForm(): void {
  editingId.value = null;
  formError.value = "";
  title.value = "";
  userword.value = "";
  psword.value = "";
  site.value = "";
  memo.value = "";
  invalidTitle.value = false;
  invalidUserword.value = false;
  invalidPsword.value = false;
  formShowPassword.value = false;
  showForm.value = true;
}

function openEditFormFromDetail(): void {
  const entry = detailEntry.value;
  if (!entry) return;
  editingId.value = entry.id;
  formError.value = "";
  title.value = entry.title;
  userword.value = entry.userword;
  psword.value = entry.psword;
  site.value = entry.site ?? "";
  memo.value = entry.memo ?? "";
  invalidTitle.value = false;
  invalidUserword.value = false;
  invalidPsword.value = false;
  formShowPassword.value = false;
  detailEntry.value = null;
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
}

async function submitForm(): Promise<void> {
  const trimmedTitle = title.value.trim();
  const trimmedUserword = userword.value.trim();
  invalidTitle.value = trimmedTitle === "";
  invalidUserword.value = trimmedUserword === "";
  invalidPsword.value = psword.value === "";
  if (invalidTitle.value || invalidUserword.value || invalidPsword.value) {
    return;
  }
  formError.value = "";
  submitting.value = true;
  const input: PasswordInput = {
    title: trimmedTitle,
    userword: trimmedUserword,
    psword: psword.value,
    site: site.value.trim() === "" ? null : site.value.trim(),
    memo: memo.value.trim() === "" ? null : memo.value.trim(),
  };
  try {
    const result =
      editingId.value === null ? await createPassword(input) : await updatePassword(editingId.value, input);
    if (result === "invalid") {
      formError.value = "入力内容を確認してください";
      return;
    }
    if (result === "missing") {
      formError.value = "対象が見つかりません";
      return;
    }
    if (result === "conflict") {
      formError.value = "同じタイトルが既に登録されています";
      return;
    }
    showForm.value = false;
    showSuccess("保存しました");
    await loadList();
  } catch (err) {
    handleError(err);
  } finally {
    submitting.value = false;
  }
}

function openDeleteConfirmFromDetail(): void {
  const entry = detailEntry.value;
  if (!entry) return;
  deleteTarget.value = { id: entry.id, title: entry.title };
  deleteError.value = "";
  detailEntry.value = null;
}

function closeDeleteConfirm(): void {
  deleteTarget.value = null;
  deleteError.value = "";
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value;
  if (!target) return;
  deleting.value = true;
  deleteError.value = "";
  try {
    const result = await deletePassword(target.id);
    if (result !== "ok") {
      deleteError.value = "削除できませんでした";
      return;
    }
    deleteTarget.value = null;
    showSuccess("削除しました");
    await loadList();
  } catch (err) {
    handleError(err);
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <div v-if="loading" class="loading">読み込み中…</div>
  <template v-else>
    <p v-if="errorMessage" class="banner-error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="banner-ok">{{ successMessage }}</p>
    <div class="toolbar">
      <div class="field">
        <label for="search">検索</label>
        <input id="search" v-model="keyword" type="search" placeholder="検索" @input="onSearchInput" />
      </div>
      <button class="btn-primary push-end" type="button" aria-label="新規登録" @click="openCreateForm">
        <Icon name="plus" />
      </button>
    </div>

    <div class="panel list">
      <p v-if="items.length === 0 && keyword.trim() === ''" class="empty">データがありません</p>
      <p v-else-if="items.length === 0" class="empty">該当するデータがありません</p>
      <table v-else>
        <thead>
          <tr>
            <th>タイトル</th>
            <th>ユーザ名</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td class="cell-primary">
              <button class="row" type="button" @click="openDetail(item)">{{ item.title }}</button>
            </td>
            <td>
              <button class="row" type="button" @click="openDetail(item)">{{ item.userword }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="detailEntry || detailLoading" class="modal-back">
      <div class="modal">
        <h2 class="section-title">{{ detailEntry?.title ?? "読み込み中" }}</h2>
        <p v-if="detailLoading" class="loading">読み込み中…</p>
        <dl v-else-if="detailEntry" class="detail-list">
          <div class="detail-row">
            <span class="detail-label">ユーザ名</span>
            <div class="detail-value-row">
              <span class="detail-value">{{ detailEntry.userword }}</span>
              <button
                class="btn-text"
                :class="{ copied: copiedField === 'userword' }"
                type="button"
                @click="copyField(detailEntry.userword, 'userword')"
              >
                {{ copiedField === "userword" ? "コピー済" : "コピー" }}
              </button>
            </div>
          </div>
          <div class="detail-row">
            <span class="detail-label">パスワード</span>
            <div class="detail-value-row">
              <span class="detail-value pw-mask">{{ showPassword ? detailEntry.psword : "••••••••" }}</span>
              <button class="btn-text" type="button" @click="showPassword = !showPassword">
                {{ showPassword ? "隠す" : "表示" }}
              </button>
              <button
                class="btn-text"
                :class="{ copied: copiedField === 'psword' }"
                type="button"
                @click="copyField(detailEntry.psword, 'psword')"
              >
                {{ copiedField === "psword" ? "コピー済" : "コピー" }}
              </button>
            </div>
          </div>
          <div v-if="detailEntry.site" class="detail-row">
            <span class="detail-label">サイト</span>
            <a class="detail-link" :href="detailEntry.site" target="_blank" rel="noopener noreferrer">{{
              detailEntry.site
            }}</a>
          </div>
          <div v-if="detailEntry.memo" class="detail-row">
            <span class="detail-label">メモ</span>
            <span class="detail-value">{{ detailEntry.memo }}</span>
          </div>
        </dl>
        <div class="actions actions-end">
          <button
            class="btn-secondary"
            type="button"
            aria-label="編集"
            :disabled="detailLoading"
            @click="openEditFormFromDetail"
          >
            <Icon name="edit" />
          </button>
          <button
            class="btn-text danger"
            type="button"
            aria-label="削除"
            :disabled="detailLoading"
            @click="openDeleteConfirmFromDetail"
          >
            <Icon name="delete" />
          </button>
          <button class="btn-text" type="button" aria-label="閉じる" @click="closeDetail">
            <Icon name="close" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="showForm" class="modal-back">
      <div class="modal">
        <h2 class="section-title">{{ editingId === null ? "パスワードエントリの登録" : "パスワードエントリの編集" }}</h2>
        <form class="form" @submit.prevent="submitForm">
          <p v-if="formError" class="banner-error">{{ formError }}</p>
          <div class="field">
            <label for="form-title">タイトル</label>
            <input
              id="form-title"
              v-model="title"
              type="text"
              :class="{ invalid: invalidTitle }"
              placeholder="タイトルを入力"
            />
            <span v-if="invalidTitle" class="field-error">タイトルは必須です</span>
          </div>
          <div class="field">
            <label for="form-userword">ユーザ名</label>
            <input
              id="form-userword"
              v-model="userword"
              type="text"
              :class="{ invalid: invalidUserword }"
              placeholder="ユーザ名を入力"
            />
            <span v-if="invalidUserword" class="field-error">ユーザ名は必須です</span>
          </div>
          <div class="field">
            <label for="form-psword">パスワード</label>
            <textarea
              id="form-psword"
              v-model="psword"
              :class="{ invalid: invalidPsword, 'pw-mask': !formShowPassword }"
              rows="3"
              placeholder="パスワードを入力（複数行可）"
              autocomplete="new-password"
              spellcheck="false"
            ></textarea>
            <button class="btn-text push-end" type="button" @click="formShowPassword = !formShowPassword">
              {{ formShowPassword ? "隠す" : "表示" }}
            </button>
            <span v-if="invalidPsword" class="field-error">パスワードは必須です</span>
          </div>
          <div class="field">
            <label for="form-site">サイトURL</label>
            <input id="form-site" v-model="site" type="text" placeholder="https://example.com" />
          </div>
          <div class="field">
            <label for="form-memo">メモ</label>
            <textarea id="form-memo" v-model="memo" rows="3" placeholder="メモを入力"></textarea>
          </div>
          <div class="actions">
            <button class="btn-primary" type="submit" aria-label="保存" :disabled="submitting">
              <Icon name="check" />
            </button>
            <button class="btn-secondary" type="button" aria-label="キャンセル" @click="closeForm">
              <Icon name="close" />
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="deleteTarget" class="modal-back">
      <div class="modal">
        <h2 class="section-title">削除の確認</h2>
        <p>「{{ deleteTarget.title }}」を削除しますか？</p>
        <p v-if="deleteError" class="banner-error">{{ deleteError }}</p>
        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="deleting" @click="closeDeleteConfirm">
            <Icon name="close" />
          </button>
          <button class="btn-text danger" type="button" aria-label="削除" :disabled="deleting" @click="confirmDelete">
            <Icon name="delete" />
          </button>
        </div>
      </div>
    </div>
  </template>
</template>
