<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { AuthError } from "../api/client";
import { getContractPassword, listAccounts } from "../api/contracts";
import type { AccountItem } from "../api/types";
import CopyButton from "../components/CopyButton.vue";
import Notice from "../components/Notice.vue";
import PasswordField from "../components/PasswordField.vue";
import { EMPTY, safeHttpUrl } from "../format";

const emit = defineEmits<{ "auth-error": [error: unknown] }>();

const keyword = ref("");
const items = ref<AccountItem[]>([]);
const loading = ref(true);
const errorMessage = ref("");

// 入力のたびに一覧を再取得する（入力が続く間は、間引く）。古い応答は捨てる
const SEARCH_DELAY_MS = 250;
let timer: ReturnType<typeof setTimeout> | undefined;
let requestId = 0;

async function load(): Promise<void> {
  const id = ++requestId;
  loading.value = true;
  errorMessage.value = "";
  try {
    const result = await listAccounts(keyword.value);
    if (id === requestId) {
      items.value = result;
    }
  } catch (error) {
    if (id !== requestId) {
      return;
    }
    handleError(error, "読み込みに失敗しました");
  } finally {
    if (id === requestId) {
      loading.value = false;
    }
  }
}

function handleError(error: unknown, message: string): void {
  if (error instanceof AuthError) {
    emit("auth-error", error);
    return;
  }
  errorMessage.value = message;
}

function fetchPassword(id: number): () => Promise<string | null> {
  return () => getContractPassword(id);
}

function showsPassword(item: AccountItem): boolean {
  // パスワードを使わない契約（ユーザ名だけなど）は、「パスワード未設定」とは示さない
  return item.has_password || item.password_unset;
}

watch(keyword, () => {
  clearTimeout(timer);
  timer = setTimeout(() => void load(), SEARCH_DELAY_MS);
});

onMounted(load);
onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
  <section class="page accounts-page">
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
    <Notice kind="error" :message="errorMessage" />
    <div v-if="loading" class="center-message list-state">
      <p class="caption">読み込み中…</p>
    </div>
    <div v-else-if="items.length === 0" class="center-message list-state">
      <p class="caption">{{ keyword.trim() ? "該当するデータがありません" : "データがありません" }}</p>
    </div>
    <div v-else class="list" role="table" aria-label="アカウント一覧">
      <div class="list-head accounts-grid" role="row">
        <span role="columnheader">名称</span>
        <span role="columnheader">ユーザ名</span>
        <span role="columnheader">パスワード</span>
      </div>
      <ul class="list-body">
        <li v-for="item in items" :key="item.id" class="list-row accounts-grid" role="row">
          <div class="cell cell-main" role="cell">
            <span class="cell-title">{{ item.name }}</span>
            <a
              v-if="safeHttpUrl(item.homepage)"
              class="cell-link"
              :href="safeHttpUrl(item.homepage) ?? undefined"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ item.homepage }}
            </a>
          </div>
          <div class="cell" role="cell" data-label="ユーザ名">
            <template v-if="item.username">
              <span class="cell-text">{{ item.username }}</span>
              <CopyButton
                :value="item.username"
                :label="`${item.name}のユーザ名をコピー`"
                @error="(e) => handleError(e, 'コピーに失敗しました')"
              />
            </template>
            <span v-else class="caption">{{ EMPTY }}</span>
          </div>
          <div class="cell" role="cell" data-label="パスワード">
            <PasswordField
              v-if="showsPassword(item)"
              :has-password="item.has_password"
              :fetch-password="fetchPassword(item.id)"
              @error="(e) => handleError(e, 'パスワードの取得に失敗しました')"
            />
            <span v-else class="caption">{{ EMPTY }}</span>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>
