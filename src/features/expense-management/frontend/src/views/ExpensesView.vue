<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  type BudgetItem,
  type BudgetPeriod,
  type Expense,
  type PaymentMethod,
  createExpense,
  deleteExpense,
  getBudgetItems,
  getBudgetPeriods,
  getEstimatedPaymentDate,
  getExpenses,
  getPaymentMethods,
  updateExpense,
} from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const loading = ref(true);
const errorMessage = ref("");
const periods = ref<BudgetPeriod[]>([]);
const items = ref<BudgetItem[]>([]);
const methods = ref<PaymentMethod[]>([]);
const expenses = ref<Expense[]>([]);

// "all" lists the last 3 months across every budget period; a number scopes the list to one period.
const selectedFilter = ref<number | "all">("all");
const periodOptions = computed(() => periods.value.slice(0, 10));

const showForm = ref(false);
const editingId = ref<number | null>(null);
const formError = ref("");
const usageDate = ref("");
const formPeriodId = ref<number | null>(null);
const budgetItemId = ref<number | null>(null);
const purpose = ref("");
const amount = ref("");
const paymentMethodId = ref<number | null>(null);
const memo = ref("");
const paymentDate = ref("");

// Only a new record started while "all" is selected lets the user pick which budget period it belongs to.
const showFormPeriodSelect = computed(() => editingId.value === null && selectedFilter.value === "all");

const formItems = computed(() => {
  if (editingId.value !== null) {
    const current = items.value.find((i) => i.id === budgetItemId.value);
    return current ? items.value.filter((i) => i.budget_period_id === current.budget_period_id) : items.value;
  }
  const periodId = selectedFilter.value === "all" ? formPeriodId.value : selectedFilter.value;
  return periodId === null ? [] : items.value.filter((i) => i.budget_period_id === periodId);
});

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function threeMonthsAgo(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().slice(0, 10);
}

// The API requires an end_date; this stands in for "no upper bound" when "all" is selected.
const NO_UPPER_BOUND = "9999-12-31";

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
}

async function loadAllItems(): Promise<void> {
  const lists = await Promise.all(periods.value.map((p) => getBudgetItems(p.id)));
  items.value = lists.flat();
}

async function loadExpenses(): Promise<void> {
  if (selectedFilter.value === "all") {
    expenses.value = await getExpenses(threeMonthsAgo(), NO_UPPER_BOUND);
    return;
  }
  const period = periods.value.find((p) => p.id === selectedFilter.value);
  if (!period) {
    expenses.value = [];
    return;
  }
  expenses.value = await getExpenses(period.start_date, period.end_date);
}

watch(selectedFilter, () => {
  loadExpenses().catch(handleError);
});

watch(formPeriodId, () => {
  if (showForm.value && editingId.value === null) {
    budgetItemId.value = formItems.value[0]?.id ?? null;
  }
});

onMounted(async () => {
  try {
    methods.value = await getPaymentMethods();
    await loadPeriods();
    await loadAllItems();
    await loadExpenses();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});

function itemName(id: number): string {
  return items.value.find((i) => i.id === id)?.name ?? "(不明な予算区分)";
}

function methodName(id: number): string {
  return methods.value.find((m) => m.id === id)?.name ?? "(不明な支出方法)";
}

function openCreateForm(): void {
  editingId.value = null;
  formError.value = "";
  usageDate.value = today();
  formPeriodId.value = selectedFilter.value === "all" ? (periods.value[0]?.id ?? null) : selectedFilter.value;
  budgetItemId.value = formItems.value[0]?.id ?? null;
  purpose.value = "";
  amount.value = "";
  paymentMethodId.value = methods.value[0]?.id ?? null;
  memo.value = "";
  paymentDate.value = today();
  showForm.value = true;
  refreshEstimate().catch(() => undefined);
}

function openEditForm(expense: Expense): void {
  editingId.value = expense.id;
  formError.value = "";
  usageDate.value = expense.usage_date;
  budgetItemId.value = expense.budget_item_id;
  purpose.value = expense.purpose;
  amount.value = expense.amount;
  paymentMethodId.value = expense.payment_method_id;
  memo.value = expense.memo ?? "";
  paymentDate.value = expense.payment_date;
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
}

async function refreshEstimate(): Promise<void> {
  if (paymentMethodId.value === null || usageDate.value === "") return;
  const requestedDate = usageDate.value;
  const requestedMethodId = paymentMethodId.value;
  const result = await getEstimatedPaymentDate(requestedMethodId, requestedDate);
  // Discard a stale response if the inputs changed again while this request was in flight.
  if (result !== "missing" && usageDate.value === requestedDate && paymentMethodId.value === requestedMethodId) {
    paymentDate.value = result;
  }
}

watch([usageDate, paymentMethodId], () => {
  refreshEstimate().catch(() => undefined);
});

async function submitForm(): Promise<void> {
  if (budgetItemId.value === null || paymentMethodId.value === null) {
    formError.value = "予算区分と支出方法を選択してください";
    return;
  }
  const input = {
    usage_date: usageDate.value,
    budget_item_id: budgetItemId.value,
    purpose: purpose.value,
    amount: amount.value,
    payment_method_id: paymentMethodId.value,
    memo: memo.value.trim() === "" ? null : memo.value,
    payment_date: paymentDate.value,
  };
  try {
    const result =
      editingId.value === null
        ? await createExpense(input)
        : await updateExpense(editingId.value, input);
    if (result === "invalid") {
      formError.value = "入力内容を確認してください";
      return;
    }
    if (result === "missing") {
      formError.value = "対象の支出記録が見つかりません";
      return;
    }
    showForm.value = false;
    await loadExpenses();
  } catch (err) {
    handleError(err);
  }
}

async function removeExpense(expense: Expense): Promise<void> {
  if (!window.confirm("この支出記録を削除しますか？")) return;
  try {
    await deleteExpense(expense.id);
    await loadExpenses();
  } catch (err) {
    handleError(err);
  }
}

const sortedExpenses = computed(() =>
  [...expenses.value].sort((a, b) => (a.usage_date < b.usage_date ? 1 : -1)),
);
</script>

<template>
  <div v-if="loading" class="loading">読み込み中…</div>
  <template v-else>
    <p v-if="errorMessage" class="banner-error">{{ errorMessage }}</p>
    <div class="toolbar">
      <div class="field">
        <label for="budget-select">予算</label>
        <select id="budget-select" v-model="selectedFilter">
          <option value="all">すべて</option>
          <option v-for="p in periodOptions" :key="p.id" :value="p.id">
            {{ p.title }}（{{ p.start_date }} 〜 {{ p.end_date }}）
          </option>
        </select>
      </div>
      <button class="btn-primary push-end" type="button" @click="openCreateForm">新規登録</button>
    </div>

    <div class="panel list">
      <p v-if="periods.length === 0" class="empty">データがありません</p>
      <table v-else>
        <thead>
          <tr>
            <th>利用日</th>
            <th>予算区分</th>
            <th>用途</th>
            <th>金額</th>
            <th>支出方法</th>
            <th>支払日</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="expense in sortedExpenses" :key="expense.id">
            <td><span class="cell-label">利用日</span>{{ expense.usage_date }}</td>
            <td><span class="cell-label">予算区分</span>{{ itemName(expense.budget_item_id) }}</td>
            <td class="cell-primary"><span class="cell-label">用途</span>{{ expense.purpose }}</td>
            <td class="cell-amount"><span class="cell-label">金額</span>{{ expense.amount }}</td>
            <td><span class="cell-label">支出方法</span>{{ methodName(expense.payment_method_id) }}</td>
            <td><span class="cell-label">支払日</span>{{ expense.payment_date }}</td>
            <td class="actions">
              <button class="btn-text" type="button" @click="openEditForm(expense)">編集</button>
              <button class="btn-text danger" type="button" @click="removeExpense(expense)">
                削除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="periods.length > 0 && sortedExpenses.length === 0" class="empty">
        データがありません
      </p>
    </div>

    <div v-if="showForm" class="modal-back">
      <div class="modal modal-wide">
        <h2 class="section-title">{{ editingId === null ? "支出記録の登録" : "支出記録の編集" }}</h2>
        <form class="form" @submit.prevent="submitForm">
          <p v-if="formError" class="banner-error">{{ formError }}</p>
          <div class="field">
            <label for="usage-date">利用日</label>
            <input id="usage-date" v-model="usageDate" type="date" required />
          </div>
          <div v-if="showFormPeriodSelect" class="field">
            <label for="form-period">予算期間</label>
            <select id="form-period" v-model.number="formPeriodId" required>
              <option v-for="p in periods" :key="p.id" :value="p.id">
                {{ p.title }}（{{ p.start_date }} 〜 {{ p.end_date }}）
              </option>
            </select>
          </div>
          <div class="field">
            <label for="budget-item">予算区分</label>
            <select id="budget-item" v-model.number="budgetItemId" required>
              <option v-for="item in formItems" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </div>
          <div class="field">
            <label for="purpose">用途</label>
            <input id="purpose" v-model="purpose" type="text" required />
          </div>
          <div class="field">
            <label for="amount">金額</label>
            <input id="amount" v-model="amount" type="text" inputmode="decimal" placeholder="0.00" required />
          </div>
          <div class="field">
            <label for="payment-method">支出方法</label>
            <select id="payment-method" v-model.number="paymentMethodId" required>
              <option v-for="method in methods" :key="method.id" :value="method.id">
                {{ method.name }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="memo">メモ</label>
            <textarea id="memo" v-model="memo"></textarea>
          </div>
          <div class="field">
            <label for="payment-date">支払日</label>
            <input id="payment-date" v-model="paymentDate" type="date" required />
          </div>
          <div class="actions">
            <button class="btn-primary" type="submit">保存</button>
            <button class="btn-secondary" type="button" @click="closeForm">キャンセル</button>
          </div>
        </form>
      </div>
    </div>
  </template>
</template>
