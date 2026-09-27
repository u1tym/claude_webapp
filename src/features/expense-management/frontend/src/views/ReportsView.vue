<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { formatAmount } from "../format";
import {
  type BudgetPeriod,
  type PaymentDateReportItem,
  type UsageDateReport,
  getBudgetPeriods,
  getPaymentDateReport,
  getUsageDateReport,
} from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const loading = ref(true);
const errorMessage = ref("");
const mode = ref<"usage-date" | "payment-date">("usage-date");

const periods = ref<BudgetPeriod[]>([]);
const selectedPeriodId = ref<number | null>(null);
const includeCredit = ref(false);
const usageReport = ref<UsageDateReport | null>(null);

function currentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const yearMonth = ref(currentYearMonth());
const paymentDateItems = ref<PaymentDateReportItem[]>([]);

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

async function loadUsageReport(): Promise<void> {
  if (selectedPeriodId.value === null) {
    usageReport.value = null;
    return;
  }
  usageReport.value = await getUsageDateReport(selectedPeriodId.value, includeCredit.value);
}

async function loadPaymentDateReport(): Promise<void> {
  paymentDateItems.value = await getPaymentDateReport(yearMonth.value);
}

watch([selectedPeriodId, includeCredit], () => {
  if (mode.value === "usage-date") {
    loadUsageReport().catch(handleError);
  }
});

watch(yearMonth, () => {
  if (mode.value === "payment-date") {
    loadPaymentDateReport().catch(handleError);
  }
});

watch(mode, () => {
  if (mode.value === "usage-date") {
    loadUsageReport().catch(handleError);
  } else {
    loadPaymentDateReport().catch(handleError);
  }
});

onMounted(async () => {
  try {
    periods.value = await getBudgetPeriods();
    if (periods.value.length > 0) {
      selectedPeriodId.value = periods.value[0]!.id;
    }
    await loadUsageReport();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div v-if="loading" class="loading">読み込み中…</div>
  <template v-else>
    <p v-if="errorMessage" class="banner-error">{{ errorMessage }}</p>
    <div class="toolbar">
      <div class="field">
        <label for="mode-select">集計基準</label>
        <select id="mode-select" v-model="mode">
          <option value="usage-date">利用日基準</option>
          <option value="payment-date">支払日毎</option>
        </select>
      </div>
      <template v-if="mode === 'usage-date'">
        <div class="field">
          <label for="period-select">予算期間</label>
          <select id="period-select" v-model.number="selectedPeriodId">
            <option v-for="p in periods" :key="p.id" :value="p.id">
              {{ p.title }}（{{ p.start_date }} 〜 {{ p.end_date }}）
            </option>
          </select>
        </div>
        <div class="field">
          <label>集計対象</label>
          <div class="checkbox-row">
            <label class="checkbox-label">
              <input v-model="includeCredit" type="radio" name="credit-scope" :value="true" />
              売掛を含めて、売掛支払を含めない
            </label>
            <label class="checkbox-label">
              <input v-model="includeCredit" type="radio" name="credit-scope" :value="false" />
              売掛を含めずに、売掛支払を含めない
            </label>
          </div>
        </div>
      </template>
      <div v-else class="field">
        <label for="year-month">年月</label>
        <input id="year-month" v-model="yearMonth" type="month" />
      </div>
    </div>

    <div class="panel">
      <template v-if="mode === 'usage-date'">
        <p v-if="periods.length === 0" class="empty">データがありません</p>
        <p v-else-if="!usageReport || usageReport.items.length === 0" class="empty">
          データがありません
        </p>
        <div v-else class="list">
          <table>
            <thead>
              <tr>
                <th>予算項目</th>
                <th>予算金額</th>
                <th>支出合計</th>
                <th>差額</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in usageReport.items" :key="item.budget_item_id">
                <td class="cell-primary"><span class="cell-label">予算項目</span>{{ item.name }}</td>
                <td class="cell-amount"><span class="cell-label">予算金額</span>{{ formatAmount(item.budget_amount) }}</td>
                <td class="cell-amount"><span class="cell-label">支出合計</span>{{ formatAmount(item.actual_amount) }}</td>
                <td class="cell-amount"><span class="cell-label">差額</span>{{ formatAmount(item.difference) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <template v-else>
        <p v-if="paymentDateItems.length === 0" class="empty">データがありません</p>
        <div v-else class="list">
          <table>
            <thead>
              <tr>
                <th>支払日</th>
                <th>通常</th>
                <th>売掛</th>
                <th>売掛支払</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paymentDateItems" :key="item.payment_date">
                <td class="cell-primary"><span class="cell-label">支払日</span>{{ item.payment_date }}</td>
                <td class="cell-amount"><span class="cell-label">通常</span>{{ formatAmount(item.normal_amount) }}</td>
                <td class="cell-amount"><span class="cell-label">売掛</span>{{ formatAmount(item.credit_amount) }}</td>
                <td class="cell-amount">
                  <span class="cell-label">売掛支払</span>{{ formatAmount(item.credit_payment_amount) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </template>
</template>
