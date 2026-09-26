<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ApiError, listApiKeys, type ApiKeyItem, type IssuedApiKey } from "../api/client";
import Icon from "../components/Icon.vue";
import IssueDialog from "../components/IssueDialog.vue";
import IssuedKeyDialog from "../components/IssuedKeyDialog.vue";
import RevokeConfirmDialog from "../components/RevokeConfirmDialog.vue";
import { STATUS_LABELS, formatDateTime } from "../format";

type LoadState = "loading" | "ready" | "error" | "forbidden";

const items = ref<ApiKeyItem[]>([]);
const loadState = ref<LoadState>("loading");
const success = ref("");
const issuing = ref(false);
const issued = ref<IssuedApiKey | null>(null);
const revokeTarget = ref<ApiKeyItem | null>(null);
let successTimer: number | undefined;

async function load(): Promise<void> {
  loadState.value = "loading";
  try {
    items.value = await listApiKeys();
    loadState.value = "ready";
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      return;
    }
    loadState.value = e instanceof ApiError && e.status === 403 ? "forbidden" : "error";
  }
}

function showSuccess(text: string): void {
  window.clearTimeout(successTimer);
  success.value = text;
  successTimer = window.setTimeout(() => (success.value = ""), 4000);
}

function onIssued(value: IssuedApiKey): void {
  issuing.value = false;
  issued.value = value;
}

async function onIssuedClosed(): Promise<void> {
  // キー全体は閉じた時点で画面の状態から破棄する
  issued.value = null;
  await load();
}

async function onRevoked(): Promise<void> {
  revokeTarget.value = null;
  await load();
  showSuccess("API キーを失効しました。");
}

onMounted(load);
onBeforeUnmount(() => window.clearTimeout(successTimer));
</script>

<template>
  <section class="page">
    <div class="page-head">
      <div class="page-head-text">
        <h2 class="title">API キー</h2>
        <p class="caption">
          他システムがあなたとして、割り当てられた機能の API を使うためのキーです。キーは第三者に知られないように管理してください。
        </p>
      </div>
      <button
        v-if="loadState !== 'forbidden'"
        type="button"
        class="btn btn-primary"
        aria-label="新規"
        :disabled="loadState === 'loading'"
        @click="issuing = true"
      >
        <Icon name="new" />
      </button>
    </div>

    <p v-if="loadState === 'error'" class="message message-error" role="alert">
      API キーの一覧を取得できませんでした。
    </p>
    <p v-else-if="loadState === 'forbidden'" class="message message-error" role="alert">
      この機能を利用する権限がありません。
    </p>
    <p v-if="success" class="message" role="status">{{ success }}</p>

    <div v-if="loadState !== 'forbidden'" class="list" role="table" aria-label="API キーの一覧">
      <div class="row row-head" role="row">
        <span role="columnheader">名前</span>
        <span role="columnheader">状態</span>
        <span role="columnheader">先頭部分</span>
        <span role="columnheader">有効期限</span>
        <span role="columnheader">最終利用</span>
        <span role="columnheader">発行日時</span>
        <span role="columnheader"><span class="visually-hidden">操作</span></span>
      </div>
      <div class="list-body" role="rowgroup">
        <div v-if="loadState === 'loading'" class="state-center">読み込み中…</div>
        <div v-else-if="loadState === 'ready' && items.length === 0" class="state-center">
          データがありません
        </div>
        <template v-else>
          <div v-for="item in items" :key="item.id" class="row" role="row">
            <span class="cell-name" role="cell">{{ item.name }}</span>
            <span class="cell-status" role="cell">
              <span class="status" :class="`status-${item.status}`">{{ STATUS_LABELS[item.status] }}</span>
              <span v-if="item.revoked_at" class="caption revoked-at">
                失効: {{ formatDateTime(item.revoked_at) }}
              </span>
            </span>
            <span class="cell-prefix mono" role="cell">{{ item.key_prefix }}…</span>
            <span class="cell-expires" role="cell">
              <span class="label-sp">有効期限 </span>{{ item.expires_at ? formatDateTime(item.expires_at) : "無期限" }}
            </span>
            <span class="cell-used caption" role="cell">
              <span class="label-sp">最終利用 </span>{{ item.last_used_at ? formatDateTime(item.last_used_at) : "未使用" }}
            </span>
            <span class="cell-created caption" role="cell">
              <span class="label-sp">発行 </span>{{ formatDateTime(item.created_at) }}
            </span>
            <span class="cell-action" role="cell">
              <button
                v-if="item.status !== 'revoked'"
                type="button"
                class="btn btn-text btn-danger-text"
                aria-label="失効"
                @click="revokeTarget = item"
              >
                <Icon name="stop" />
              </button>
            </span>
          </div>
        </template>
      </div>
    </div>

    <IssueDialog v-if="issuing" @cancel="issuing = false" @issued="onIssued" />
    <IssuedKeyDialog v-if="issued" :name="issued.name" :api-key="issued.key" @close="onIssuedClosed" />
    <RevokeConfirmDialog
      v-if="revokeTarget"
      :target="revokeTarget"
      @cancel="revokeTarget = null"
      @revoked="onRevoked"
    />
  </section>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space) * 2);
  height: 100%;
  max-width: 1200px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  gap: calc(var(--space) * 2);
}

.page-head-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space);
}

.list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}

.list-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.row {
  display: grid;
  grid-template-columns: minmax(160px, 2fr) 120px 150px 150px 150px 150px var(--tap);
  align-items: center;
  gap: calc(var(--space) * 2);
  padding: var(--space) calc(var(--space) * 2);
  border-bottom: 1px solid var(--color-border);
}

.row-head {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text-muted);
}

.cell-name {
  overflow-wrap: anywhere;
}

.cell-status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.revoked-at {
  font-size: 12px;
}

.label-sp {
  display: none;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

@media (max-width: 1023px) and (min-width: 768px) {
  .row {
    grid-template-columns: minmax(120px, 2fr) 100px 130px 130px 130px 130px var(--tap);
    gap: var(--space);
    font-size: 14px;
  }
}

@media (max-width: 767px) {
  .row-head {
    display: none;
  }

  .list {
    background: transparent;
    border: none;
  }

  .list-body {
    display: flex;
    flex-direction: column;
    gap: var(--space);
  }

  .row {
    grid-template-columns: 1fr auto auto;
    grid-template-areas:
      "name status action"
      "prefix prefix prefix"
      "expires expires expires"
      "used used used"
      "created created created";
    gap: 4px var(--space);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
  }

  .cell-name { grid-area: name; font-weight: 600; }
  .cell-status { grid-area: status; }
  .cell-action { grid-area: action; }
  .cell-prefix { grid-area: prefix; }
  .cell-expires { grid-area: expires; font-size: 14px; }
  .cell-used { grid-area: used; }
  .cell-created { grid-area: created; }

  .label-sp {
    display: inline;
    color: var(--color-text-muted);
  }
}
</style>
