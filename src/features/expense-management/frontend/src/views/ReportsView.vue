<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  type BudgetPeriod,
  type PaymentMonthReportItem,
  type UsageDateReport,
  getBudgetPeriods,
  getPaymentMonthReport,
  getUsageDateReport,
} from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const loading = ref(true);
const errorMessage = ref("");
const mode = ref<"usage-date" | "payment-month">("usage-date");

const periods = ref<BudgetPeriod[]>([]);
const selectedPeriodId = ref<number | null>(null);
const usageReport = ref<UsageDateReport | null>(null);

function currentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const yearMonth = ref(currentYearMonth());
const paymentMonthItems = ref<PaymentMonthReportItem[]>([]);

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
  usageReport.value = await getUsageDateReport(selectedPeriodId.value);
}

async function loadPaymentMonthReport(): Promise<void> {
  paymentMonthItems.value = await getPaymentMonthReport(yearMonth.value);
}

watch(selectedPeriodId, () => {
  if (mode.value === "usage-date") {
    loadUsageReport().catch(handleError);
  }
});

watch(yearMonth, () => {
  if (mode.value === "payment-month") {
    loadPaymentMonthReport().catch(handleError);
  }
});

watch(mode, () => {
  if (mode.value === "usage-date") {
    loadUsageReport().catch(handleError);
  } else {
    loadPaymentMonthReport().catch(handleError);
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
          <option value="payment-month">支払発生月基準</option>
        </select>
      </div>
      <div v-if="mode === 'usage-date'" class="field">
        <label for="period-select">予算期間</label>
        <select id="period-select" v-model.number="selectedPeriodId">
          <option v-for="p in periods" :key="p.id" :value="p.id">
            {{ p.title }}（{{ p.start_date }} 〜 {{ p.end_date }}）
          </option>
        </select>
      </div>
      <div v-else class="field">
        <label for="year-month">年月</label>
        <input id="year-month" v-model="yearMonth" type="month" />
      </div>
    </div>

    <div class="panel list">
      <template v-if="mode === 'usage-date'">
        <p v-if="periods.length === 0" class="empty">データがありません</p>
        <p v-else-if="!usageReport || usageReport.items.length === 0" class="empty">
          データがありません
        </p>
        <table v-else>
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
              <td>{{ item.name }}</td>
              <td>{{ item.budget_amount }}</td>
              <td>{{ item.actual_amount }}</td>
              <td>{{ item.difference }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <template v-else>
        <p v-if="paymentMonthItems.length === 0" class="empty">データがありません</p>
        <table v-else>
          <thead>
            <tr>
              <th>予算項目</th>
              <th>支出合計</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in paymentMonthItems" :key="item.budget_item_id">
              <td>{{ item.name }}</td>
              <td>{{ item.actual_amount }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>
  </template>
</template>
