<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { getCandidates, getPlan, savePlan } from "../api/cancellation";
import { ApiError, AuthError } from "../api/client";
import { listContracts } from "../api/contracts";
import type { Contract, ContractRef, PlanCandidate, PlanItem } from "../api/types";
import Icon from "../components/Icon.vue";
import Notice from "../components/Notice.vue";
import { EMPTY, formatLocalDate } from "../format";

const emit = defineEmits<{ "auth-error": [error: unknown] }>();

/** 解約順の 1 行（保存済みの解約順の項目と、これから加える契約を、同じ形で持つ） */
type Row = {
  contract_id: number;
  name: string;
  cancellation_method: string | null;
  depends_on: ContractRef[];
};

const rows = ref<Row[]>([]);
const savedIds = ref<number[]>([]);
const candidates = ref<PlanCandidate[]>([]);
// 契約の詳細（解約方法・依存契約・区分）。解約順に加える契約の行を作るために使う
const lookup = ref<Map<number, Contract>>(new Map());
const candidateFilter = ref("");
const loading = ref(true);
const saving = ref(false);
const errorMessage = ref("");
const successMessage = ref("");
let successTimer: ReturnType<typeof setTimeout> | undefined;

// PDF 出力（印刷用の領域に、保存済みの解約順を組んで、ブラウザの印刷を開く）
const printItems = ref<PlanItem[]>([]);
const printDate = ref("");
const printing = ref(false);

const dirty = computed(() => {
  const ids = rows.value.map((r) => r.contract_id);
  return ids.length !== savedIds.value.length || ids.some((id, i) => id !== savedIds.value[i]);
});

// 依存している契約が、その契約より先に解約順に並んでいるとき、警告にする（編集中の並びで、その都度求める）
const warnings = computed(() => {
  const result: { key: string; text: string }[] = [];
  const position = new Map(rows.value.map((r, i) => [r.contract_id, i]));
  rows.value.forEach((row, index) => {
    for (const dep of row.depends_on) {
      const depIndex = position.get(dep.id);
      if (depIndex !== undefined && depIndex < index) {
        result.push({
          key: `${row.contract_id}-${dep.id}`,
          text: `「${row.name}」は「${dep.name}」に依存しています。「${dep.name}」が先に解約される並びです`,
        });
      }
    }
  });
  return result;
});

// PDF 出力できないときの理由。解約の対象が 0 件、または未保存の変更があるときは出力できない（保存した解約順で出力するため）
const pdfDisabledReason = computed(() => {
  if (dirty.value) {
    return "未保存の変更があるため、PDF 出力できません。先に保存してください";
  }
  if (savedIds.value.length === 0) {
    return "解約の対象がないため、PDF 出力できません";
  }
  return "";
});

const visibleCandidates = computed(() => {
  const word = candidateFilter.value.trim().toLowerCase();
  return candidates.value.filter((c) => word === "" || c.name.toLowerCase().includes(word));
});

function rowFromContract(id: number, name: string): Row {
  const c = lookup.value.get(id);
  return {
    contract_id: id,
    name: c?.name ?? name,
    cancellation_method: c?.cancellation_method ?? null,
    depends_on: c?.depends_on ?? [],
  };
}

function handleError(error: unknown, message: string): void {
  if (error instanceof AuthError) {
    emit("auth-error", error);
    return;
  }
  errorMessage.value = error instanceof ApiError && error.status === 400 ? error.message : message;
}

function showSuccess(message: string): void {
  successMessage.value = message;
  clearTimeout(successTimer);
  successTimer = setTimeout(() => {
    successMessage.value = "";
  }, 3000);
}

async function load(): Promise<void> {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [plan, cands] = await Promise.all([getPlan(), getCandidates()]);
    // 依存契約などの情報は、行の表示のための補助。取得できなくても、解約順の編集はできる
    try {
      lookup.value = new Map((await listContracts()).map((c) => [c.id, c]));
    } catch (error) {
      if (error instanceof AuthError) {
        throw error;
      }
      errorMessage.value = "契約の詳細を読み込めませんでした";
    }
    rows.value = plan.items.map((item) => ({
      contract_id: item.contract_id,
      name: item.name,
      cancellation_method: item.cancellation_method,
      depends_on: item.depends_on,
    }));
    savedIds.value = rows.value.map((r) => r.contract_id);
    candidates.value = cands;
  } catch (error) {
    handleError(error, "読み込みに失敗しました");
  } finally {
    loading.value = false;
  }
}

function add(candidate: PlanCandidate): void {
  rows.value.push(rowFromContract(candidate.id, candidate.name));
  candidates.value = candidates.value.filter((c) => c.id !== candidate.id);
}

function remove(row: Row): void {
  rows.value = rows.value.filter((r) => r.contract_id !== row.contract_id);
  const c = lookup.value.get(row.contract_id);
  candidates.value = [
    ...candidates.value,
    {
      id: row.contract_id,
      name: row.name,
      category_name: c?.category.name ?? EMPTY,
      has_cancellation_method: row.cancellation_method !== null,
    },
  ].sort((a, b) => a.id - b.id);
}

function move(index: number, delta: -1 | 1): void {
  const target = index + delta;
  if (target < 0 || target >= rows.value.length) {
    return;
  }
  const next = [...rows.value];
  const [item] = next.splice(index, 1);
  if (item !== undefined) {
    next.splice(target, 0, item);
  }
  rows.value = next;
}

async function save(): Promise<void> {
  saving.value = true;
  errorMessage.value = "";
  try {
    const plan = await savePlan(rows.value.map((r) => r.contract_id));
    savedIds.value = plan.items.map((i) => i.contract_id);
    // 保存した並び（サーバが返したもの）に、行を揃える。行の内容は、編集中の行を引き継ぐ
    const byId = new Map(rows.value.map((r) => [r.contract_id, r]));
    rows.value = plan.items.map((item) => byId.get(item.contract_id) ?? { ...item });
    showSuccess("保存しました");
  } catch (error) {
    handleError(error, "保存に失敗しました");
  } finally {
    saving.value = false;
  }
}

/** 保存済みの解約順を取得して、印刷用の領域に組み、印刷を開く。パスワード・ユーザ名・登録メールアドレスは、取得も出力もしない。 */
async function exportPdf(): Promise<void> {
  printing.value = true;
  errorMessage.value = "";
  try {
    const plan = await getPlan();
    printItems.value = plan.items;
    printDate.value = formatLocalDate(new Date());
    await nextTick();
    window.print();
  } catch (error) {
    handleError(error, "PDF 出力に失敗しました");
  } finally {
    printing.value = false;
  }
}

onMounted(load);
onBeforeUnmount(() => clearTimeout(successTimer));
</script>

<template>
  <section class="page cancellation-page">
    <div class="toolbar">
      <button class="btn-primary btn-icon" type="button" aria-label="保存" title="保存" :disabled="saving || loading || !dirty" @click="save">
        <Icon name="check" />
      </button>
      <button class="btn-secondary btn-compact" type="button" aria-label="PDF出力" :disabled="loading || printing || pdfDisabledReason !== ''" @click="exportPdf">
        PDF出力
      </button>
      <span v-if="dirty" class="caption" role="status">未保存の変更があります</span>
      <span v-if="!loading && pdfDisabledReason" class="caption" data-testid="pdf-reason">{{ pdfDisabledReason }}</span>
    </div>
    <Notice kind="success" :message="successMessage" />
    <Notice kind="error" :message="errorMessage" />
    <div v-if="warnings.length" class="warning-box" role="status" aria-label="警告">
      <p v-for="w in warnings" :key="w.key" class="warning-item">{{ w.text }}</p>
    </div>

    <div v-if="loading" class="center-message list-state">
      <p class="caption">読み込み中…</p>
    </div>
    <div v-else class="plan-layout">
      <section class="plan-panel" aria-label="解約順の一覧">
        <h2 class="detail-heading">解約順</h2>
        <p v-if="rows.length === 0" class="caption plan-empty">解約の対象がありません</p>
        <ol v-else class="plan-list">
          <li v-for="(row, index) in rows" :key="row.contract_id" class="plan-row">
            <span class="plan-number">{{ index + 1 }}</span>
            <div class="plan-main">
              <span class="cell-title">{{ row.name }}</span>
              <span class="plan-method pre">{{ row.cancellation_method ?? "解約方法: 未入力" }}</span>
              <span v-if="row.depends_on.length" class="caption">依存契約: {{ row.depends_on.map((d) => d.name).join("、") }}</span>
            </div>
            <div class="row-actions">
              <button class="btn-secondary btn-compact" type="button" :aria-label="`${row.name}を上へ`" :disabled="index === 0" @click="move(index, -1)">上へ</button>
              <button class="btn-secondary btn-compact" type="button" :aria-label="`${row.name}を下へ`" :disabled="index === rows.length - 1" @click="move(index, 1)">下へ</button>
              <button class="btn-secondary btn-icon" type="button" :aria-label="`${row.name}を解約順から外す`" title="外す" @click="remove(row)">
                <Icon name="close" />
              </button>
            </div>
          </li>
        </ol>
      </section>

      <section class="plan-panel" aria-label="対象にできる契約">
        <h2 class="detail-heading">対象にできる契約</h2>
        <input v-model="candidateFilter" class="search-input" type="search" placeholder="検索" aria-label="対象にできる契約を絞り込む" autocomplete="off" />
        <p v-if="candidates.length === 0" class="caption plan-empty">データがありません</p>
        <p v-else-if="visibleCandidates.length === 0" class="caption plan-empty">該当するデータがありません</p>
        <ul v-else class="plan-list">
          <li v-for="c in visibleCandidates" :key="c.id" class="plan-row plan-candidate">
            <div class="plan-main">
              <span class="cell-title">{{ c.name }}</span>
              <span class="caption">{{ c.category_name }}／解約方法: {{ c.has_cancellation_method ? "あり" : "未入力" }}</span>
            </div>
            <button class="btn-secondary btn-compact" type="button" :aria-label="`${c.name}を解約順に加える`" @click="add(c)">加える</button>
          </li>
        </ul>
      </section>
    </div>
  </section>

  <!-- 印刷用の領域（画面には出さない）。ブラウザの印刷で「PDF に保存」する -->
  <Teleport to="body">
    <div class="print-area" aria-hidden="true">
      <h1>解約手順</h1>
      <p>出力日: {{ printDate }}</p>
      <ol class="print-list">
        <li v-for="item in printItems" :key="item.contract_id">
          <h2>{{ item.position }}. {{ item.name }}</h2>
          <p class="print-method">{{ item.cancellation_method ?? "未入力" }}</p>
        </li>
      </ol>
    </div>
  </Teleport>
</template>
