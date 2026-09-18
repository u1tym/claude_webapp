<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  type BudgetItem,
  type BudgetPeriod,
  createBudgetItem,
  createBudgetPeriod,
  deleteBudgetItem,
  duplicateBudgetPeriod,
  getBudgetItems,
  getBudgetPeriods,
  updateBudgetItem,
} from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const loading = ref(true);
const errorMessage = ref("");
const periods = ref<BudgetPeriod[]>([]);
const selectedPeriodId = ref<number | null>(null);
const items = ref<BudgetItem[]>([]);
// Compact viewports show either the period list or the selected period's items, never both at once.
const panelMode = ref<"master" | "detail">("master");

const showPeriodForm = ref(false);
const periodFormMode = ref<"create" | "duplicate">("create");
const periodFormError = ref("");
const periodTitle = ref("");
const periodStartDate = ref("");
const periodEndDate = ref("");

const showItemForm = ref(false);
const editingItemId = ref<number | null>(null);
const itemFormError = ref("");
const itemName = ref("");
const itemAmount = ref("");
const itemDisplayOrder = ref(1);

function handleError(err: unknown): void {
  if (err instanceof Error && err.message === "unauth") {
    emit("unauth");
    return;
  }
  if (err instanceof Error && err.message === "forbidden") {
    emit("forbidden");
    return;
  }
  errorMessage.value = "読み込みに失敗しました";
}

async function loadPeriods(): Promise<void> {
  periods.value = await getBudgetPeriods();
  if (periods.value.length > 0 && selectedPeriodId.value === null) {
    selectedPeriodId.value = periods.value[0]!.id;
    panelMode.value = "detail";
  }
}

function selectPeriod(id: number): void {
  selectedPeriodId.value = id;
  panelMode.value = "detail";
}

async function loadItems(): Promise<void> {
  if (selectedPeriodId.value === null) {
    items.value = [];
    return;
  }
  items.value = await getBudgetItems(selectedPeriodId.value);
}

watch(selectedPeriodId, () => {
  loadItems().catch(handleError);
});

onMounted(async () => {
  try {
    await loadPeriods();
    await loadItems();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});

function openCreatePeriodForm(): void {
  periodFormMode.value = "create";
  periodFormError.value = "";
  periodTitle.value = "";
  periodStartDate.value = "";
  periodEndDate.value = "";
  showPeriodForm.value = true;
}

function openDuplicatePeriodForm(): void {
  if (periods.value.length === 0) return;
  periodFormMode.value = "duplicate";
  periodFormError.value = "";
  periodTitle.value = "";
  periodStartDate.value = "";
  periodEndDate.value = "";
  showPeriodForm.value = true;
}

function closePeriodForm(): void {
  showPeriodForm.value = false;
}

async function submitPeriodForm(): Promise<void> {
  try {
    if (periodFormMode.value === "create") {
      const result = await createBudgetPeriod(periodTitle.value, periodStartDate.value, periodEndDate.value);
      if (result === "invalid") {
        periodFormError.value = "タイトルを入力し、終了日は開始日以降にしてください";
        return;
      }
      selectedPeriodId.value = result.id;
      panelMode.value = "detail";
    } else {
      const sourceId = periods.value[0]!.id;
      const result = await duplicateBudgetPeriod(
        sourceId,
        periodTitle.value,
        periodStartDate.value,
        periodEndDate.value,
      );
      if (result === "invalid") {
        periodFormError.value = "タイトルを入力し、終了日は開始日以降にしてください";
        return;
      }
      if (result === "missing") {
        periodFormError.value = "複製元の予算期間が見つかりません";
        return;
      }
      selectedPeriodId.value = result.id;
      panelMode.value = "detail";
    }
    showPeriodForm.value = false;
    await loadPeriods();
    await loadItems();
  } catch (err) {
    handleError(err);
  }
}

function openCreateItemForm(): void {
  if (selectedPeriodId.value === null) return;
  editingItemId.value = null;
  itemFormError.value = "";
  itemName.value = "";
  itemAmount.value = "";
  itemDisplayOrder.value = items.value.length + 1;
  showItemForm.value = true;
}

function openEditItemForm(item: BudgetItem): void {
  editingItemId.value = item.id;
  itemFormError.value = "";
  itemName.value = item.name;
  itemAmount.value = item.amount;
  itemDisplayOrder.value = item.display_order;
  showItemForm.value = true;
}

function closeItemForm(): void {
  showItemForm.value = false;
}

async function submitItemForm(): Promise<void> {
  if (selectedPeriodId.value === null) return;
  try {
    const result =
      editingItemId.value === null
        ? await createBudgetItem(selectedPeriodId.value, itemName.value, itemAmount.value, itemDisplayOrder.value)
        : await updateBudgetItem(editingItemId.value, itemName.value, itemAmount.value, itemDisplayOrder.value);
    if (result === "invalid") {
      itemFormError.value = "入力内容を確認してください";
      return;
    }
    if (result === "missing") {
      itemFormError.value = "対象の予算項目が見つかりません";
      return;
    }
    showItemForm.value = false;
    await loadItems();
  } catch (err) {
    handleError(err);
  }
}

async function removeItem(item: BudgetItem): Promise<void> {
  if (!window.confirm("この予算項目を削除しますか？")) return;
  try {
    await deleteBudgetItem(item.id);
    await loadItems();
  } catch (err) {
    handleError(err);
  }
}
</script>

<template>
  <div v-if="loading" class="loading">読み込み中…</div>
  <template v-else>
    <p v-if="errorMessage" class="banner-error">{{ errorMessage }}</p>
    <div class="split" :class="panelMode === 'master' ? 'mode-master' : 'mode-detail'">
      <div class="panel master-panel">
        <div class="toolbar">
          <h2 class="section-title">予算期間</h2>
          <button class="btn-primary" type="button" @click="openCreatePeriodForm">新規作成</button>
          <button class="btn-secondary" type="button" :disabled="periods.length === 0" @click="openDuplicatePeriodForm">
            直近から複製作成
          </button>
        </div>
        <div class="list">
          <p v-if="periods.length === 0" class="empty">データがありません</p>
          <table v-else>
            <thead>
              <tr>
                <th>予算期間</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in periods"
                :key="p.id"
                :class="{ selected: p.id === selectedPeriodId }"
              >
                <td>
                  <button class="row" type="button" @click="selectPeriod(p.id)">
                    {{ p.title }}（{{ p.start_date }} 〜 {{ p.end_date }}）
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel detail-panel">
        <button type="button" class="btn-text back-to-master" @click="panelMode = 'master'">
          ← 予算期間一覧に戻る
        </button>
        <div class="toolbar">
          <h2 class="section-title">予算項目</h2>
          <button class="btn-primary" type="button" :disabled="selectedPeriodId === null" @click="openCreateItemForm">
            追加
          </button>
        </div>
        <div class="list">
          <p v-if="selectedPeriodId === null" class="empty">予算期間を選択してください</p>
          <p v-else-if="items.length === 0" class="empty">データがありません</p>
          <table v-else>
            <thead>
              <tr>
                <th>項目名</th>
                <th>金額</th>
                <th>表示順</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id">
                <td class="cell-primary"><span class="cell-label">項目名</span>{{ item.name }}</td>
                <td class="cell-amount"><span class="cell-label">金額</span>{{ item.amount }}</td>
                <td><span class="cell-label">表示順</span>{{ item.display_order }}</td>
                <td class="actions">
                  <button class="btn-text" type="button" @click="openEditItemForm(item)">編集</button>
                  <button class="btn-text danger" type="button" @click="removeItem(item)">削除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="showPeriodForm" class="modal-back" @click.self="closePeriodForm">
      <div class="modal">
        <h2 class="section-title">
          {{ periodFormMode === "create" ? "予算期間の新規作成" : "予算期間の複製作成" }}
        </h2>
        <form class="form" @submit.prevent="submitPeriodForm">
          <p v-if="periodFormError" class="banner-error">{{ periodFormError }}</p>
          <div class="field">
            <label for="period-title">タイトル</label>
            <input id="period-title" v-model="periodTitle" type="text" required />
          </div>
          <div class="field">
            <label for="period-start">開始日</label>
            <input id="period-start" v-model="periodStartDate" type="date" required />
          </div>
          <div class="field">
            <label for="period-end">終了日</label>
            <input id="period-end" v-model="periodEndDate" type="date" required />
          </div>
          <div class="actions">
            <button class="btn-primary" type="submit">保存</button>
            <button class="btn-secondary" type="button" @click="closePeriodForm">キャンセル</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showItemForm" class="modal-back" @click.self="closeItemForm">
      <div class="modal">
        <h2 class="section-title">{{ editingItemId === null ? "予算項目の追加" : "予算項目の編集" }}</h2>
        <form class="form" @submit.prevent="submitItemForm">
          <p v-if="itemFormError" class="banner-error">{{ itemFormError }}</p>
          <div class="field">
            <label for="item-name">項目名</label>
            <input id="item-name" v-model="itemName" type="text" required />
          </div>
          <div class="field">
            <label for="item-amount">金額</label>
            <input id="item-amount" v-model="itemAmount" type="text" inputmode="decimal" placeholder="0.00" required />
          </div>
          <div class="field">
            <label for="item-order">表示順</label>
            <input id="item-order" v-model.number="itemDisplayOrder" type="number" min="0" required />
          </div>
          <div class="actions">
            <button class="btn-primary" type="submit">保存</button>
            <button class="btn-secondary" type="button" @click="closeItemForm">キャンセル</button>
          </div>
        </form>
      </div>
    </div>
  </template>
</template>
