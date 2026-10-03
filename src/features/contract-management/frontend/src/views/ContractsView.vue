<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { listCategories } from "../api/categories";
import { ApiError, AuthError } from "../api/client";
import { deleteContract, getContract, listContracts } from "../api/contracts";
import type { Category, Contract, ContractFilters, Status } from "../api/types";
import ContractDetail from "../components/ContractDetail.vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import ContractForm from "../components/ContractForm.vue";
import Icon from "../components/Icon.vue";
import Notice from "../components/Notice.vue";
import { EMPTY, STATUSES, formatFee, formatIsoDate, statusLabel } from "../format";

const emit = defineEmits<{ "auth-error": [error: unknown] }>();

// 絞り込み（ui-design.md SCR-002）。既定はすべて「すべて」で、ステータスが解約の契約も表示する
const keyword = ref("");
const categoryId = ref<number | "">("");
const status = ref<Status | "">("");
const hasContract = ref<"" | "true" | "false">("");
const passwordUnset = ref(false);

const categories = ref<Category[]>([]);
const contracts = ref<Contract[]>([]);
const loading = ref(true);
const errorMessage = ref("");
// 詳細表示している契約（一覧で選んだ行）。関連する契約を選ぶと、その契約に切り替わる
const detail = ref<Contract | null>(null);
// 登録・編集フォーム（編集のときは、編集する契約）
const creating = ref(false);
const editing = ref<Contract | null>(null);
// 削除の確認中の契約
const deleting = ref<Contract | null>(null);
const successMessage = ref("");
let successTimer: ReturnType<typeof setTimeout> | undefined;
const selectedId = computed(() => detail.value?.id ?? null);

const SEARCH_DELAY_MS = 250;
let timer: ReturnType<typeof setTimeout> | undefined;
let requestId = 0;

const filtered = computed(
  () =>
    keyword.value.trim() !== "" ||
    categoryId.value !== "" ||
    status.value !== "" ||
    hasContract.value !== "" ||
    passwordUnset.value,
);

function currentFilters(): ContractFilters {
  return {
    keyword: keyword.value,
    category_id: categoryId.value === "" ? null : categoryId.value,
    status: status.value,
    has_contract: hasContract.value === "" ? null : hasContract.value === "true",
    password_unset: passwordUnset.value,
  };
}

function handleError(error: unknown, message: string): void {
  if (error instanceof AuthError) {
    emit("auth-error", error);
    return;
  }
  errorMessage.value = message;
}

async function load(): Promise<void> {
  const id = ++requestId;
  loading.value = true;
  errorMessage.value = "";
  try {
    const result = await listContracts(currentFilters());
    if (id === requestId) {
      contracts.value = result;
    }
  } catch (error) {
    if (id === requestId) {
      handleError(error, "読み込みに失敗しました");
    }
  } finally {
    if (id === requestId) {
      loading.value = false;
    }
  }
}

async function loadCategories(): Promise<void> {
  try {
    categories.value = await listCategories();
  } catch (error) {
    handleError(error, "区分の読み込みに失敗しました");
  }
}

function showSuccess(message: string): void {
  successMessage.value = message;
  clearTimeout(successTimer);
  // 成功メッセージは、数秒で消える
  successTimer = setTimeout(() => {
    successMessage.value = "";
  }, 3000);
}

function startEdit(): void {
  editing.value = detail.value;
  detail.value = null;
}

/** 詳細を閉じて、削除の確認ダイアログを開く。 */
function startDelete(): void {
  deleting.value = detail.value;
  detail.value = null;
}

async function confirmDelete(): Promise<void> {
  const target = deleting.value;
  deleting.value = null;
  if (target === null) {
    return;
  }
  errorMessage.value = "";
  try {
    await deleteContract(target.id);
  } catch (error) {
    if (error instanceof AuthError) {
      emit("auth-error", error);
    } else if (error instanceof ApiError) {
      // 本文の一文（内部理由を含まない。例: 「対象がありません」）をそのまま示す
      errorMessage.value = error.message;
    } else {
      errorMessage.value = "削除に失敗しました";
    }
    return;
  }
  showSuccess("削除しました");
  await load();
}

async function onSaved(_saved: Contract, created: boolean): Promise<void> {
  creating.value = false;
  editing.value = null;
  showSuccess(created ? "登録しました" : "更新しました");
  await load();
}

function select(contract: Contract): void {
  detail.value = contract;
}

/** 関連する契約の詳細に切り替える。絞り込みで一覧に無い契約もあるので、取得し直す。 */
async function openRelated(id: number): Promise<void> {
  try {
    detail.value = await getContract(id);
  } catch (error) {
    detail.value = null;
    handleError(error, "契約の読み込みに失敗しました");
  }
}

// 検索語の入力は、続く間は間引く。区分・ステータスなどの選択は、すぐに再取得する
watch(keyword, () => {
  clearTimeout(timer);
  timer = setTimeout(() => void load(), SEARCH_DELAY_MS);
});
watch([categoryId, status, hasContract, passwordUnset], () => {
  clearTimeout(timer);
  void load();
});

onMounted(() => {
  void loadCategories();
  void load();
});
onBeforeUnmount(() => {
  clearTimeout(timer);
  clearTimeout(successTimer);
});

</script>

<template>
  <section class="page contracts-page">
    <div class="toolbar">
      <input
        v-model="keyword"
        class="search-input"
        type="search"
        placeholder="検索"
        aria-label="検索"
        autocomplete="off"
      />
    </div>
    <div class="toolbar filters">
      <label class="filter">
        <span class="filter-label">区分</span>
        <select v-model="categoryId" class="select" aria-label="区分で絞り込む">
          <option value="">すべて</option>
          <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </label>
      <label class="filter">
        <span class="filter-label">ステータス</span>
        <select v-model="status" class="select" aria-label="ステータスで絞り込む">
          <option value="">すべて</option>
          <option v-for="s in STATUSES" :key="s" :value="s">{{ statusLabel(s) }}</option>
        </select>
      </label>
      <label class="filter">
        <span class="filter-label">契約の有無</span>
        <select v-model="hasContract" class="select" aria-label="契約の有無で絞り込む">
          <option value="">すべて</option>
          <option value="true">契約を伴う</option>
          <option value="false">契約を伴わない</option>
        </select>
      </label>
      <label class="check-label">
        <input v-model="passwordUnset" type="checkbox" />
        パスワード未設定のみ
      </label>
      <button class="btn-primary btn-icon toolbar-end" type="button" aria-label="新規" title="新規" @click="creating = true">
        <Icon name="new" />
      </button>
    </div>
    <Notice kind="success" :message="successMessage" />
    <Notice kind="error" :message="errorMessage" />
    <div v-if="loading" class="center-message list-state">
      <p class="caption">読み込み中…</p>
    </div>
    <div v-else-if="contracts.length === 0" class="center-message list-state">
      <p class="caption">{{ filtered ? "該当するデータがありません" : "データがありません" }}</p>
    </div>
    <div v-else class="list" role="table" aria-label="契約一覧">
      <div class="list-head contracts-grid" role="row">
        <span role="columnheader">名称</span>
        <span role="columnheader">区分</span>
        <span role="columnheader">ステータス</span>
        <span role="columnheader">維持費</span>
        <span role="columnheader">更新日</span>
      </div>
      <ul class="list-body">
        <li v-for="c in contracts" :key="c.id" role="row">
          <button
            class="list-row row-button contracts-grid"
            type="button"
            :aria-label="`${c.name}の詳細を表示`"
            :aria-pressed="selectedId === c.id"
            @click="select(c)"
          >
            <span class="cell cell-main" role="cell">
              <span class="cell-title">{{ c.name }}</span>
              <span v-if="c.password_unset" class="badge badge-warn">パスワード未設定</span>
            </span>
            <span class="cell" role="cell" data-label="区分">{{ c.category.name }}</span>
            <span class="cell" role="cell" data-label="ステータス">{{ statusLabel(c.status) }}</span>
            <span class="cell" role="cell" data-label="維持費">{{ formatFee(c.fee_amount, c.fee_cycle) }}</span>
            <span class="cell" role="cell" data-label="更新日">
              {{ c.renewal_date ? formatIsoDate(c.renewal_date) : EMPTY }}
            </span>
          </button>
        </li>
      </ul>
    </div>

    <ContractDetail
      v-if="detail"
      :key="detail.id"
      :contract="detail"
      @close="detail = null"
      @edit="startEdit"
      @delete="startDelete"
      @open="openRelated"
      @error="(e) => handleError(e, '操作に失敗しました')"
    />

    <ConfirmDialog
      v-if="deleting"
      title="契約の削除"
      :message="`「${deleting.name}」を削除しますか？`"
      @confirm="confirmDelete"
      @cancel="deleting = null"
    />

    <ContractForm
      v-if="creating || editing"
      :key="editing?.id ?? 'new'"
      :contract="editing ?? undefined"
      :categories="categories"
      @saved="onSaved"
      @cancel="creating = false; editing = null"
      @auth-error="(e) => handleError(e, '保存に失敗しました')"
    />
  </section>
</template>
