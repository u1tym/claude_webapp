<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from "vue";
import {
  AuthError,
  createKnowhow,
  createMajorCategory,
  createMiddleCategory,
  deleteKnowhow,
  deleteMajorCategory,
  deleteMiddleCategory,
  getKnowhow,
  getKnowhows,
  getMajorCategories,
  getMiddleCategories,
  renameMajorCategory,
  renameMiddleCategory,
  searchKnowhows,
  swapKnowhowDisplayOrder,
  updateKnowhow,
  type KnowhowDetail,
  type KnowhowSearchResult,
  type KnowhowSummary,
  type MajorCategory,
  type MiddleCategory,
} from "../api";
import Icon from "../components/Icon.vue";

const onAuthError = inject<(error: unknown) => void>("onAuthError");

const loading = ref(true);
const errorMessage = ref("");
const successMessage = ref("");
let successTimer: ReturnType<typeof setTimeout> | null = null;

const majors = ref<MajorCategory[]>([]);
const middles = ref<MiddleCategory[]>([]);
const knowhows = ref<KnowhowSummary[]>([]);

const selectedMajorId = ref<number | "">("");
const selectedMiddleId = ref<number | "">("");

const keywordQuery = ref("");
const searchMode = ref(false);
const searchResults = ref<KnowhowSearchResult[]>([]);

const reorderMode = ref(false);

const detail = ref<KnowhowDetail | null>(null);
const detailMajorName = ref("");
const detailMiddleName = ref("");

const canReorderOrCreate = computed(() => selectedMiddleId.value !== "" && !searchMode.value);

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

async function loadMajors(): Promise<void> {
  majors.value = await getMajorCategories();
}

async function loadMiddles(majorId: number): Promise<void> {
  const result = await getMiddleCategories(majorId);
  middles.value = result === "missing" ? [] : result;
}

async function loadKnowhows(middleId: number): Promise<void> {
  const result = await getKnowhows(middleId);
  knowhows.value = result === "missing" ? [] : result;
}

watch(selectedMajorId, async (majorId) => {
  selectedMiddleId.value = "";
  middles.value = [];
  knowhows.value = [];
  reorderMode.value = false;
  detail.value = null;
  if (majorId === "") return;
  try {
    await loadMiddles(majorId);
  } catch (err) {
    handleError(err);
  }
});

watch(selectedMiddleId, async (middleId) => {
  knowhows.value = [];
  reorderMode.value = false;
  detail.value = null;
  if (middleId === "") return;
  try {
    await loadKnowhows(middleId);
  } catch (err) {
    handleError(err);
  }
});

onMounted(async () => {
  try {
    await loadMajors();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});

function keywordTerms(): string[] {
  return keywordQuery.value
    .split(/[,、]+/)
    .map((v) => v.trim())
    .filter((v) => v !== "");
}

async function submitSearch(): Promise<void> {
  const terms = keywordTerms();
  if (terms.length === 0) return;
  errorMessage.value = "";
  detail.value = null;
  reorderMode.value = false;
  try {
    searchResults.value = await searchKnowhows(terms);
    searchMode.value = true;
  } catch (err) {
    handleError(err);
  }
}

function clearSearch(): void {
  keywordQuery.value = "";
  searchMode.value = false;
  searchResults.value = [];
}

async function openDetailById(id: number, majorName: string, middleName: string): Promise<void> {
  errorMessage.value = "";
  try {
    const result = await getKnowhow(id);
    if (result === "missing") {
      errorMessage.value = "対象が見つかりません";
      return;
    }
    detail.value = result;
    detailMajorName.value = majorName;
    detailMiddleName.value = middleName;
  } catch (err) {
    handleError(err);
  }
}

function openDetailFromList(item: KnowhowSummary): void {
  const majorName = majors.value.find((m) => m.id === selectedMajorId.value)?.name ?? "";
  const middleName = middles.value.find((m) => m.id === selectedMiddleId.value)?.name ?? "";
  void openDetailById(item.id, majorName, middleName);
}

function openDetailFromSearch(item: KnowhowSearchResult): void {
  void openDetailById(item.knowhow_id, item.major_category_name ?? "未分類", item.middle_category_name ?? "未分類");
}

function closeDetail(): void {
  detail.value = null;
}

function canConfigClick(): boolean {
  return detail.value !== null || canReorderOrCreate.value;
}

function onConfigClick(): void {
  if (detail.value) {
    openKnowhowEditForm();
    return;
  }
  if (!canReorderOrCreate.value) return;
  reorderMode.value = !reorderMode.value;
}

// ---- category create / rename ----------------------------------------

type CategoryFormKind = "major-create" | "major-rename" | "middle-create" | "middle-rename";
const categoryForm = ref<CategoryFormKind | null>(null);
const categoryFormName = ref("");
const categoryFormError = ref("");
const categoryFormSubmitting = ref(false);

function openMajorCreateForm(): void {
  categoryForm.value = "major-create";
  categoryFormName.value = "";
  categoryFormError.value = "";
}

function openMajorRenameForm(): void {
  if (selectedMajorId.value === "") return;
  categoryForm.value = "major-rename";
  categoryFormName.value = majors.value.find((m) => m.id === selectedMajorId.value)?.name ?? "";
  categoryFormError.value = "";
}

function openMiddleCreateForm(): void {
  if (selectedMajorId.value === "") return;
  categoryForm.value = "middle-create";
  categoryFormName.value = "";
  categoryFormError.value = "";
}

function openMiddleRenameForm(): void {
  if (selectedMiddleId.value === "") return;
  categoryForm.value = "middle-rename";
  categoryFormName.value = middles.value.find((m) => m.id === selectedMiddleId.value)?.name ?? "";
  categoryFormError.value = "";
}

function closeCategoryForm(): void {
  categoryForm.value = null;
}

async function submitCategoryForm(): Promise<void> {
  const name = categoryFormName.value.trim();
  if (name === "" || categoryForm.value === null) return;
  categoryFormError.value = "";
  categoryFormSubmitting.value = true;
  try {
    if (categoryForm.value === "major-create") {
      const result = await createMajorCategory(name);
      if (result === "invalid") {
        categoryFormError.value = "入力内容を確認してください";
        return;
      }
      if (result === "conflict") {
        categoryFormError.value = "同じ名称が既に登録されています";
        return;
      }
      await loadMajors();
    } else if (categoryForm.value === "major-rename" && selectedMajorId.value !== "") {
      const result = await renameMajorCategory(selectedMajorId.value, name);
      if (result === "invalid") {
        categoryFormError.value = "入力内容を確認してください";
        return;
      }
      if (result === "missing") {
        categoryFormError.value = "対象が見つかりません";
        return;
      }
      if (result === "conflict") {
        categoryFormError.value = "同じ名称が既に登録されています";
        return;
      }
      await loadMajors();
    } else if (categoryForm.value === "middle-create" && selectedMajorId.value !== "") {
      const result = await createMiddleCategory(selectedMajorId.value, name);
      if (result === "invalid") {
        categoryFormError.value = "入力内容を確認してください";
        return;
      }
      if (result === "missing") {
        categoryFormError.value = "対象が見つかりません";
        return;
      }
      if (result === "conflict") {
        categoryFormError.value = "同じ名称が既に登録されています";
        return;
      }
      await loadMiddles(selectedMajorId.value);
    } else if (categoryForm.value === "middle-rename" && selectedMiddleId.value !== "") {
      const result = await renameMiddleCategory(selectedMiddleId.value, name);
      if (result === "invalid") {
        categoryFormError.value = "入力内容を確認してください";
        return;
      }
      if (result === "missing") {
        categoryFormError.value = "対象が見つかりません";
        return;
      }
      if (result === "conflict") {
        categoryFormError.value = "同じ名称が既に登録されています";
        return;
      }
      if (selectedMajorId.value !== "") await loadMiddles(selectedMajorId.value);
    }
    categoryForm.value = null;
    showSuccess("保存しました");
  } catch (err) {
    handleError(err);
  } finally {
    categoryFormSubmitting.value = false;
  }
}

// ---- category delete ---------------------------------------------------

const categoryDeleteTarget = ref<{ kind: "major" | "middle"; id: number; name: string } | null>(null);
const categoryDeleting = ref(false);
const categoryDeleteError = ref("");

function openMajorDeleteConfirm(): void {
  if (selectedMajorId.value === "") return;
  const name = majors.value.find((m) => m.id === selectedMajorId.value)?.name ?? "";
  categoryDeleteTarget.value = { kind: "major", id: selectedMajorId.value, name };
  categoryDeleteError.value = "";
}

function openMiddleDeleteConfirm(): void {
  if (selectedMiddleId.value === "") return;
  const name = middles.value.find((m) => m.id === selectedMiddleId.value)?.name ?? "";
  categoryDeleteTarget.value = { kind: "middle", id: selectedMiddleId.value, name };
  categoryDeleteError.value = "";
}

function closeCategoryDeleteConfirm(): void {
  categoryDeleteTarget.value = null;
}

async function confirmCategoryDelete(): Promise<void> {
  const target = categoryDeleteTarget.value;
  if (!target) return;
  categoryDeleting.value = true;
  categoryDeleteError.value = "";
  try {
    if (target.kind === "major") {
      const result = await deleteMajorCategory(target.id);
      if (result !== "ok") {
        categoryDeleteError.value = "削除できませんでした";
        return;
      }
      selectedMajorId.value = "";
      selectedMiddleId.value = "";
      middles.value = [];
      knowhows.value = [];
      await loadMajors();
    } else {
      const result = await deleteMiddleCategory(target.id);
      if (result !== "ok") {
        categoryDeleteError.value = "削除できませんでした";
        return;
      }
      selectedMiddleId.value = "";
      knowhows.value = [];
      if (selectedMajorId.value !== "") await loadMiddles(selectedMajorId.value);
    }
    categoryDeleteTarget.value = null;
    showSuccess("削除しました");
  } catch (err) {
    handleError(err);
  } finally {
    categoryDeleting.value = false;
  }
}

// ---- knowhow create / edit ----------------------------------------------

const showKnowhowForm = ref(false);
const editingKnowhowId = ref<number | null>(null);
const knowhowFormError = ref("");
const knowhowFormSubmitting = ref(false);
const formTitle = ref("");
const formKeywords = ref("");
const formContent = ref("");
const formMiddleCategoryId = ref<number | "">("");

function openKnowhowCreateForm(): void {
  if (!canReorderOrCreate.value) return;
  editingKnowhowId.value = null;
  formTitle.value = "";
  formKeywords.value = "";
  formContent.value = "";
  formMiddleCategoryId.value = selectedMiddleId.value;
  knowhowFormError.value = "";
  showKnowhowForm.value = true;
}

function openKnowhowEditForm(): void {
  const d = detail.value;
  if (!d) return;
  editingKnowhowId.value = d.id;
  formTitle.value = d.title;
  formKeywords.value = d.keywords ?? "";
  formContent.value = d.content;
  formMiddleCategoryId.value = d.middle_category_id ?? "";
  knowhowFormError.value = "";
  showKnowhowForm.value = true;
}

function closeKnowhowForm(): void {
  showKnowhowForm.value = false;
}

async function submitKnowhowForm(): Promise<void> {
  const title = formTitle.value.trim();
  const content = formContent.value.trim();
  if (title === "" || content === "") {
    knowhowFormError.value = "タイトルと本文を入力してください";
    return;
  }
  knowhowFormError.value = "";
  knowhowFormSubmitting.value = true;
  const input = {
    title,
    keywords: formKeywords.value.trim() === "" ? null : formKeywords.value.trim(),
    content,
    middle_category_id: formMiddleCategoryId.value === "" ? null : formMiddleCategoryId.value,
  };
  try {
    const result =
      editingKnowhowId.value === null
        ? await createKnowhow(input)
        : await updateKnowhow(editingKnowhowId.value, input);
    if (result === "invalid") {
      knowhowFormError.value = "入力内容を確認してください";
      return;
    }
    if (result === "missing") {
      knowhowFormError.value = "対象が見つかりません";
      return;
    }
    showKnowhowForm.value = false;
    showSuccess("保存しました");
    if (editingKnowhowId.value !== null) {
      detail.value = result;
    }
    if (selectedMiddleId.value !== "") {
      await loadKnowhows(selectedMiddleId.value);
    }
  } catch (err) {
    handleError(err);
  } finally {
    knowhowFormSubmitting.value = false;
  }
}

// ---- knowhow reorder / delete --------------------------------------------

async function moveKnowhow(item: KnowhowSummary, direction: "up" | "down"): Promise<void> {
  const idx = knowhows.value.findIndex((k) => k.id === item.id);
  if (idx < 0) return;
  const targetIdx = direction === "up" ? idx - 1 : idx + 1;
  if (targetIdx < 0 || targetIdx >= knowhows.value.length) return;
  const target = knowhows.value[targetIdx];
  try {
    const result = await swapKnowhowDisplayOrder(item.id, target.id);
    if (result !== "ok") {
      errorMessage.value = "並び替えできませんでした";
      return;
    }
    if (selectedMiddleId.value !== "") await loadKnowhows(selectedMiddleId.value);
  } catch (err) {
    handleError(err);
  }
}

const knowhowDeleteTarget = ref<KnowhowSummary | null>(null);
const knowhowDeleting = ref(false);
const knowhowDeleteError = ref("");

function openKnowhowDeleteConfirm(item: KnowhowSummary): void {
  knowhowDeleteTarget.value = item;
  knowhowDeleteError.value = "";
}

function closeKnowhowDeleteConfirm(): void {
  knowhowDeleteTarget.value = null;
}

async function confirmKnowhowDelete(): Promise<void> {
  const target = knowhowDeleteTarget.value;
  if (!target) return;
  knowhowDeleting.value = true;
  knowhowDeleteError.value = "";
  try {
    const result = await deleteKnowhow(target.id);
    if (result !== "ok") {
      knowhowDeleteError.value = "削除できませんでした";
      return;
    }
    knowhowDeleteTarget.value = null;
    showSuccess("削除しました");
    if (selectedMiddleId.value !== "") await loadKnowhows(selectedMiddleId.value);
  } catch (err) {
    handleError(err);
  } finally {
    knowhowDeleting.value = false;
  }
}
</script>

<template>
  <div v-if="loading" class="loading">読み込み中…</div>
  <template v-else>
    <p v-if="errorMessage" class="banner-error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="banner-ok">{{ successMessage }}</p>

    <template v-if="!detail">
      <div class="toolbar">
        <div class="field">
          <label for="keyword">検索</label>
          <input
            id="keyword"
            v-model="keywordQuery"
            type="text"
            placeholder="検索（複数はカンマ区切り）"
            @keyup.enter="submitSearch"
          />
        </div>
        <button class="btn-secondary" type="button" aria-label="検索" @click="submitSearch">検索</button>
        <button class="btn-text" type="button" aria-label="クリア" @click="clearSearch">クリア</button>
      </div>

      <div v-if="!searchMode" class="toolbar">
        <div class="field">
          <label for="major-select">大項目</label>
          <select id="major-select" v-model="selectedMajorId">
            <option value="">大項目を選択</option>
            <option v-for="m in majors" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
        <button class="btn-text" type="button" aria-label="大項目の追加" @click="openMajorCreateForm">
          <Icon name="plus" />
        </button>
        <button
          class="btn-text"
          type="button"
          aria-label="大項目の名称変更"
          :disabled="selectedMajorId === ''"
          @click="openMajorRenameForm"
        >
          <Icon name="edit" />
        </button>
        <button
          class="btn-text danger"
          type="button"
          aria-label="大項目の削除"
          :disabled="selectedMajorId === ''"
          @click="openMajorDeleteConfirm"
        >
          <Icon name="delete" />
        </button>

        <div class="field">
          <label for="middle-select">中項目</label>
          <select id="middle-select" v-model="selectedMiddleId" :disabled="selectedMajorId === ''">
            <option value="">中項目を選択</option>
            <option v-for="m in middles" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
        <button
          class="btn-text"
          type="button"
          aria-label="中項目の追加"
          :disabled="selectedMajorId === ''"
          @click="openMiddleCreateForm"
        >
          <Icon name="plus" />
        </button>
        <button
          class="btn-text"
          type="button"
          aria-label="中項目の名称変更"
          :disabled="selectedMiddleId === ''"
          @click="openMiddleRenameForm"
        >
          <Icon name="edit" />
        </button>
        <button
          class="btn-text danger"
          type="button"
          aria-label="中項目の削除"
          :disabled="selectedMiddleId === ''"
          @click="openMiddleDeleteConfirm"
        >
          <Icon name="delete" />
        </button>
      </div>

      <div class="panel list">
        <p v-if="searchMode && searchResults.length === 0" class="empty">該当するデータがありません</p>
        <p v-else-if="!searchMode && selectedMiddleId === ''" class="empty">
          大項目・中項目を選ぶと、ノウハウの一覧が表示されます
        </p>
        <p v-else-if="!searchMode && knowhows.length === 0" class="empty">データがありません</p>
        <ul v-else-if="searchMode" class="plain-list">
          <li v-for="item in searchResults" :key="item.knowhow_id" class="list-item">
            <button class="row" type="button" @click="openDetailFromSearch(item)">
              {{ item.title }}
              <span class="caption">{{ item.major_category_name ?? "未分類" }} / {{ item.middle_category_name ?? "未分類" }}</span>
            </button>
          </li>
        </ul>
        <ul v-else class="plain-list">
          <li v-for="(item, idx) in knowhows" :key="item.id" class="list-item">
            <button class="row" type="button" @click="openDetailFromList(item)">{{ item.title }}</button>
            <div v-if="reorderMode" class="reorder-actions">
              <button
                class="btn-text"
                type="button"
                aria-label="上へ"
                :disabled="idx === 0"
                @click="moveKnowhow(item, 'up')"
              >
                上へ
              </button>
              <button
                class="btn-text"
                type="button"
                aria-label="下へ"
                :disabled="idx === knowhows.length - 1"
                @click="moveKnowhow(item, 'down')"
              >
                下へ
              </button>
              <button class="btn-text danger" type="button" aria-label="削除" @click="openKnowhowDeleteConfirm(item)">
                <Icon name="delete" />
              </button>
            </div>
          </li>
        </ul>
        <div class="actions">
          <button
            class="btn-primary"
            type="button"
            aria-label="新規登録"
            :disabled="!canReorderOrCreate"
            @click="openKnowhowCreateForm"
          >
            <Icon name="plus" />
          </button>
          <button
            class="btn-secondary"
            type="button"
            aria-label="並び替え"
            :disabled="!canConfigClick()"
            @click="onConfigClick"
          >
            <Icon name="config" />
          </button>
        </div>
      </div>
    </template>

    <div v-else class="panel">
      <button class="btn-text" type="button" aria-label="戻る" @click="closeDetail">
        <Icon name="back" />
      </button>
      <div class="actions actions-end">
        <button class="btn-secondary" type="button" aria-label="編集" @click="onConfigClick">
          <Icon name="config" />
        </button>
      </div>
      <h2 class="section-title">{{ detail.title }}</h2>
      <dl class="detail-list">
        <div class="detail-row">
          <span class="detail-label">大項目</span>
          <span class="detail-value">{{ detailMajorName || "未分類" }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">中項目</span>
          <span class="detail-value">{{ detailMiddleName || "未分類" }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">キーワード</span>
          <span class="detail-value">{{ detail.keywords || "—" }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">本文</span>
          <span class="detail-value">{{ detail.content }}</span>
        </div>
      </dl>
    </div>

    <div v-if="categoryForm" class="modal-back">
      <div class="modal">
        <h2 class="section-title">
          {{
            categoryForm === "major-create"
              ? "大項目の追加"
              : categoryForm === "major-rename"
                ? "大項目の名称変更"
                : categoryForm === "middle-create"
                  ? "中項目の追加"
                  : "中項目の名称変更"
          }}
        </h2>
        <form class="form" @submit.prevent="submitCategoryForm">
          <p v-if="categoryFormError" class="banner-error">{{ categoryFormError }}</p>
          <div class="field">
            <label for="category-name">名称</label>
            <input id="category-name" v-model="categoryFormName" type="text" placeholder="名称を入力" />
          </div>
          <div class="actions">
            <button class="btn-primary" type="submit" aria-label="保存" :disabled="categoryFormSubmitting">
              <Icon name="check" />
            </button>
            <button class="btn-secondary" type="button" aria-label="キャンセル" @click="closeCategoryForm">
              <Icon name="close" />
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="categoryDeleteTarget" class="modal-back">
      <div class="modal">
        <h2 class="section-title">削除の確認</h2>
        <p>
          「{{ categoryDeleteTarget.name }}」を削除しますか？
          <template v-if="categoryDeleteTarget.kind === 'major'">配下の中項目・ノウハウも削除されます。</template>
          <template v-else>配下のノウハウも削除されます。</template>
        </p>
        <p v-if="categoryDeleteError" class="banner-error">{{ categoryDeleteError }}</p>
        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="categoryDeleting" @click="closeCategoryDeleteConfirm">
            <Icon name="close" />
          </button>
          <button class="btn-text danger" type="button" aria-label="削除" :disabled="categoryDeleting" @click="confirmCategoryDelete">
            <Icon name="delete" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="showKnowhowForm" class="modal-back">
      <div class="modal">
        <h2 class="section-title">{{ editingKnowhowId === null ? "ノウハウの登録" : "ノウハウの編集" }}</h2>
        <form class="form" @submit.prevent="submitKnowhowForm">
          <p v-if="knowhowFormError" class="banner-error">{{ knowhowFormError }}</p>
          <div class="field">
            <label for="kh-title">タイトル</label>
            <input id="kh-title" v-model="formTitle" type="text" placeholder="タイトルを入力" />
          </div>
          <div class="field">
            <label for="kh-keywords">キーワード</label>
            <input id="kh-keywords" v-model="formKeywords" type="text" placeholder="キーワードを入力（任意）" />
          </div>
          <div class="field">
            <label for="kh-content">本文</label>
            <textarea id="kh-content" v-model="formContent" rows="6" placeholder="本文を入力"></textarea>
          </div>
          <div class="field">
            <label for="kh-middle">所属する中項目</label>
            <select id="kh-middle" v-model="formMiddleCategoryId">
              <option value="">未分類</option>
              <option v-for="m in middles" :key="m.id" :value="m.id">{{ m.name }}</option>
            </select>
          </div>
          <div class="actions">
            <button class="btn-primary" type="submit" aria-label="保存" :disabled="knowhowFormSubmitting">
              <Icon name="check" />
            </button>
            <button class="btn-secondary" type="button" aria-label="キャンセル" @click="closeKnowhowForm">
              <Icon name="close" />
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="knowhowDeleteTarget" class="modal-back">
      <div class="modal">
        <h2 class="section-title">削除の確認</h2>
        <p>「{{ knowhowDeleteTarget.title }}」を削除しますか？</p>
        <p v-if="knowhowDeleteError" class="banner-error">{{ knowhowDeleteError }}</p>
        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="knowhowDeleting" @click="closeKnowhowDeleteConfirm">
            <Icon name="close" />
          </button>
          <button class="btn-text danger" type="button" aria-label="削除" :disabled="knowhowDeleting" @click="confirmKnowhowDelete">
            <Icon name="delete" />
          </button>
        </div>
      </div>
    </div>
  </template>
</template>
