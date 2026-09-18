<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  type ExclusionItem,
  type PaymentMethod,
  type PaymentMethodInput,
  createPaymentMethod,
  deletePaymentMethod,
  getPaymentMethods,
  updatePaymentMethod,
} from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const EXCLUSION_LABELS: Record<string, string> = {
  sunday: "日曜日",
  monday: "月曜日",
  tuesday: "火曜日",
  wednesday: "水曜日",
  thursday: "木曜日",
  friday: "金曜日",
  saturday: "土曜日",
  nonexistent_day: "当月に存在しない日",
  holiday: "祝日",
};
const EXCLUSION_KINDS = Object.keys(EXCLUSION_LABELS);

const loading = ref(true);
const errorMessage = ref("");
const methods = ref<PaymentMethod[]>([]);

const showForm = ref(false);
const editingId = ref<number | null>(null);
const formError = ref("");
const name = ref("");
const closingDay = ref(0);
const closingDayShiftDirection = ref<"earlier" | "later">("earlier");
const closingDayExclusions = ref<ExclusionItem[]>([]);
const paymentMonthOffset = ref(0);
const paymentDay = ref(1);
const paymentDayShiftDirection = ref<"earlier" | "later">("earlier");
const paymentDayExclusions = ref<ExclusionItem[]>([]);
const displayOrder = ref(1);
const newClosingExclusion = ref(EXCLUSION_KINDS[0]!);
const newPaymentExclusion = ref(EXCLUSION_KINDS[0]!);

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

async function loadMethods(): Promise<void> {
  methods.value = await getPaymentMethods();
}

onMounted(async () => {
  try {
    await loadMethods();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});

function exclusionLabel(kind: string): string {
  return EXCLUSION_LABELS[kind] ?? kind;
}

function openCreateForm(): void {
  editingId.value = null;
  formError.value = "";
  name.value = "";
  closingDay.value = 0;
  closingDayShiftDirection.value = "earlier";
  closingDayExclusions.value = [];
  paymentMonthOffset.value = 0;
  paymentDay.value = 1;
  paymentDayShiftDirection.value = "earlier";
  paymentDayExclusions.value = [];
  displayOrder.value = methods.value.length + 1;
  showForm.value = true;
}

function openEditForm(method: PaymentMethod): void {
  editingId.value = method.id;
  formError.value = "";
  name.value = method.name;
  closingDay.value = method.closing_day;
  closingDayShiftDirection.value = (method.closing_day_shift_direction as "earlier" | "later") ?? "earlier";
  closingDayExclusions.value = [...method.closing_day_exclusions];
  paymentMonthOffset.value = method.payment_month_offset;
  paymentDay.value = method.payment_day === 0 ? 1 : method.payment_day;
  paymentDayShiftDirection.value = (method.payment_day_shift_direction as "earlier" | "later") ?? "earlier";
  paymentDayExclusions.value = [...method.payment_day_exclusions];
  displayOrder.value = method.display_order;
  showForm.value = true;
}

function closeForm(): void {
  showForm.value = false;
}

function addClosingExclusion(): void {
  if (closingDayExclusions.value.some((e) => e.exclusion_kind === newClosingExclusion.value)) return;
  closingDayExclusions.value.push({ exclusion_kind: newClosingExclusion.value });
}

function removeClosingExclusion(kind: string): void {
  closingDayExclusions.value = closingDayExclusions.value.filter((e) => e.exclusion_kind !== kind);
}

function addPaymentExclusion(): void {
  if (paymentDayExclusions.value.some((e) => e.exclusion_kind === newPaymentExclusion.value)) return;
  paymentDayExclusions.value.push({ exclusion_kind: newPaymentExclusion.value });
}

function removePaymentExclusion(kind: string): void {
  paymentDayExclusions.value = paymentDayExclusions.value.filter((e) => e.exclusion_kind !== kind);
}

async function submitForm(): Promise<void> {
  const input: PaymentMethodInput = {
    name: name.value,
    closing_day: closingDay.value,
    display_order: displayOrder.value,
  };
  if (closingDay.value > 0) {
    input.closing_day_shift_direction = closingDayShiftDirection.value;
    input.closing_day_exclusions = closingDayExclusions.value;
    input.payment_month_offset = paymentMonthOffset.value;
    input.payment_day = paymentDay.value;
    input.payment_day_shift_direction = paymentDayShiftDirection.value;
    input.payment_day_exclusions = paymentDayExclusions.value;
  }
  try {
    const result =
      editingId.value === null
        ? await createPaymentMethod(input)
        : await updatePaymentMethod(editingId.value, input);
    if (result === "invalid") {
      formError.value = "入力内容を確認してください";
      return;
    }
    if (result === "missing") {
      formError.value = "対象の支出方法が見つかりません";
      return;
    }
    showForm.value = false;
    await loadMethods();
  } catch (err) {
    handleError(err);
  }
}

async function removeMethod(method: PaymentMethod): Promise<void> {
  if (!window.confirm("この支出方法を削除しますか？")) return;
  try {
    await deletePaymentMethod(method.id);
    await loadMethods();
  } catch (err) {
    handleError(err);
  }
}
</script>

<template>
  <div v-if="loading" class="loading">読み込み中…</div>
  <template v-else>
    <p v-if="errorMessage" class="banner-error">{{ errorMessage }}</p>
    <div class="toolbar">
      <button class="btn-primary" type="button" @click="openCreateForm">新規登録</button>
    </div>

    <div class="panel list">
      <p v-if="methods.length === 0" class="empty">データがありません</p>
      <table v-else>
        <thead>
          <tr>
            <th>名称</th>
            <th>締め日</th>
            <th>支払月オフセット</th>
            <th>支払日</th>
            <th>表示順</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="method in methods" :key="method.id">
            <td class="cell-primary"><span class="cell-label">名称</span>{{ method.name }}</td>
            <td><span class="cell-label">締め日</span>{{ method.closing_day }}</td>
            <td><span class="cell-label">支払月オフセット</span>{{ method.payment_month_offset }}</td>
            <td><span class="cell-label">支払日</span>{{ method.payment_day }}</td>
            <td><span class="cell-label">表示順</span>{{ method.display_order }}</td>
            <td class="actions">
              <button class="btn-text" type="button" @click="openEditForm(method)">編集</button>
              <button class="btn-text danger" type="button" @click="removeMethod(method)">削除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showForm" class="modal-back">
      <div class="modal modal-wide">
        <h2 class="section-title">{{ editingId === null ? "支出方法の登録" : "支出方法の編集" }}</h2>
        <form class="form" @submit.prevent="submitForm">
          <p v-if="formError" class="banner-error">{{ formError }}</p>
          <div class="field-row">
            <div class="field">
              <label for="pm-name">名称</label>
              <input id="pm-name" v-model="name" type="text" required />
            </div>
            <div class="field field-narrow">
              <label for="pm-order">表示順</label>
              <input id="pm-order" v-model.number="displayOrder" type="number" min="0" required />
            </div>
          </div>

          <div class="field field-narrow">
            <label for="pm-closing-day">締め日（0〜31。0は即時支払）</label>
            <input id="pm-closing-day" v-model.number="closingDay" type="number" min="0" max="31" required />
          </div>

          <template v-if="closingDay > 0">
            <div class="field-row">
              <div class="field">
                <label>締め日用の除外条件</label>
                <div class="tag-list">
                  <span v-for="e in closingDayExclusions" :key="e.exclusion_kind" class="tag">
                    {{ exclusionLabel(e.exclusion_kind) }}
                    <button type="button" @click="removeClosingExclusion(e.exclusion_kind)">×</button>
                  </span>
                </div>
                <div class="toolbar">
                  <select v-model="newClosingExclusion">
                    <option v-for="kind in EXCLUSION_KINDS" :key="kind" :value="kind">
                      {{ exclusionLabel(kind) }}
                    </option>
                  </select>
                  <button class="btn-secondary" type="button" @click="addClosingExclusion">追加</button>
                </div>
              </div>
              <div class="field field-narrow">
                <label for="pm-closing-shift">締め日用ずらし方向</label>
                <select id="pm-closing-shift" v-model="closingDayShiftDirection">
                  <option value="earlier">過去</option>
                  <option value="later">未来</option>
                </select>
              </div>
            </div>

            <div class="field-row">
              <div class="field field-narrow">
                <label for="pm-offset">支払月オフセット</label>
                <input id="pm-offset" v-model.number="paymentMonthOffset" type="number" min="0" required />
              </div>
              <div class="field field-narrow">
                <label for="pm-payment-day">支払日（1〜31）</label>
                <input id="pm-payment-day" v-model.number="paymentDay" type="number" min="1" max="31" required />
              </div>
            </div>

            <div class="field-row">
              <div class="field">
                <label>支払日用の除外条件</label>
                <div class="tag-list">
                  <span v-for="e in paymentDayExclusions" :key="e.exclusion_kind" class="tag">
                    {{ exclusionLabel(e.exclusion_kind) }}
                    <button type="button" @click="removePaymentExclusion(e.exclusion_kind)">×</button>
                  </span>
                </div>
                <div class="toolbar">
                  <select v-model="newPaymentExclusion">
                    <option v-for="kind in EXCLUSION_KINDS" :key="kind" :value="kind">
                      {{ exclusionLabel(kind) }}
                    </option>
                  </select>
                  <button class="btn-secondary" type="button" @click="addPaymentExclusion">追加</button>
                </div>
              </div>
              <div class="field field-narrow">
                <label for="pm-payment-shift">支払日用ずらし方向</label>
                <select id="pm-payment-shift" v-model="paymentDayShiftDirection">
                  <option value="earlier">過去</option>
                  <option value="later">未来</option>
                </select>
              </div>
            </div>
          </template>

          <div class="actions">
            <button class="btn-primary" type="submit">保存</button>
            <button class="btn-secondary" type="button" @click="closeForm">キャンセル</button>
          </div>
        </form>
      </div>
    </div>
  </template>
</template>
