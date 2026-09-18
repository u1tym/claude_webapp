<script setup lang="ts">
import { onMounted, ref } from "vue";
import { createUser, deleteUser, getUsers, updateUser, type UserItem } from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const items = ref<UserItem[]>([]);
const loading = ref(true);
const error = ref("");
const success = ref("");
const mode = ref<"list" | "create" | "edit">("list");
const selected = ref<UserItem | null>(null);
const username = ref("");
const email = ref("");
const password = ref("");
const invalidUsername = ref(false);
const invalidEmail = ref(false);
const invalidPassword = ref(false);
const confirmId = ref<number | null>(null);

function emailOk(value: string): boolean {
  const trimmed = value.trim();
  const at = trimmed.indexOf("@");
  return at > 0 && at < trimmed.length - 1;
}

onMounted(() => {
  void reload();
});

async function reload(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    items.value = await getUsers();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}

function handle(err: unknown): void {
  if (err instanceof Error && err.message === "unauth") {
    emit("unauth");
    return;
  }
  if (err instanceof Error && err.message === "forbidden") {
    emit("forbidden");
    return;
  }
  error.value = "取得できませんでした";
}

function startCreate(): void {
  mode.value = "create";
  selected.value = null;
  username.value = "";
  email.value = "";
  password.value = "";
  invalidUsername.value = false;
  invalidEmail.value = false;
  invalidPassword.value = false;
}

function startEdit(item: UserItem): void {
  mode.value = "edit";
  selected.value = item;
  username.value = item.username;
  email.value = item.email;
  password.value = "";
  invalidUsername.value = false;
  invalidEmail.value = false;
  invalidPassword.value = false;
}

function cancel(): void {
  mode.value = "list";
  selected.value = null;
  username.value = "";
  email.value = "";
  password.value = "";
  invalidUsername.value = false;
  invalidEmail.value = false;
  invalidPassword.value = false;
}

async function save(): Promise<void> {
  error.value = "";
  success.value = "";
  const nameBlank = username.value.trim() === "";
  const mailBlank = email.value.trim() === "";
  const mailBad = !emailOk(email.value);
  const passwordBlank = mode.value === "create" && password.value === "";
  invalidUsername.value = nameBlank;
  invalidEmail.value = mailBlank || mailBad;
  invalidPassword.value = passwordBlank;
  if (nameBlank || mailBlank || mailBad || passwordBlank) {
    return;
  }
  loading.value = true;
  try {
    if (mode.value === "create") {
      const result = await createUser(username.value, password.value, email.value);
      if (result === "invalid" || result === "conflict") {
        error.value = result === "invalid" ? "入力が不正です" : "保存できませんでした";
        return;
      }
    } else if (selected.value) {
      const result = await updateUser(selected.value.id, username.value, password.value, email.value);
      if (result === "invalid" || result === "missing" || result === "conflict") {
        error.value = result === "invalid" ? "入力が不正です" : result === "missing" ? "対象がありません" : "保存できませんでした";
        return;
      }
    }
    success.value = "保存しました";
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
    cancel();
    items.value = await getUsers();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}

async function confirmDelete(): Promise<void> {
  if (confirmId.value === null) {
    return;
  }
  loading.value = true;
  try {
    const result = await deleteUser(confirmId.value);
    confirmId.value = null;
    if (result !== "ok") {
      error.value = "削除できませんでした";
      return;
    }
    success.value = "削除しました";
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
    cancel();
    items.value = await getUsers();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <p v-if="error" class="banner-error">{{ error }}</p>
  <p v-if="success" class="banner-ok">{{ success }}</p>
  <p v-if="loading" class="loading">読み込み中…</p>
  <div v-else class="split" :class="mode === 'list' ? 'mobile-list' : 'mobile-form'">
    <section class="panel list-panel">
      <div class="actions">
        <button class="btn-primary" type="button" :disabled="loading" @click="startCreate">新規</button>
      </div>
      <div class="list">
        <p v-if="items.length === 0" class="empty">データがありません</p>
        <table v-else>
          <thead>
            <tr>
              <th>ユーザ名</th>
              <th>メールアドレス</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id" :class="{ selected: selected?.id === item.id }">
              <td>
                <button class="row" type="button" @click="startEdit(item)">{{ item.username }}</button>
              </td>
              <td>
                <button class="row" type="button" @click="startEdit(item)">{{ item.email }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="mode !== 'list'" class="panel form-panel">
      <form class="form" @submit.prevent="save">
        <input
          v-model="username"
          type="text"
          placeholder="ユーザ名"
          aria-label="ユーザ名"
          :class="{ invalid: invalidUsername }"
          :disabled="loading"
          required
        />
        <input
          v-model="email"
          type="text"
          placeholder="メールアドレス"
          aria-label="メールアドレス"
          :class="{ invalid: invalidEmail }"
          :disabled="loading"
          required
        />
        <input
          v-model="password"
          type="password"
          :placeholder="mode === 'create' ? 'パスワード' : '空なら変更しない'"
          aria-label="パスワード"
          :class="{ invalid: invalidPassword }"
          :disabled="loading"
          :required="mode === 'create'"
        />
        <div class="actions">
          <button class="btn-primary" type="submit" :disabled="loading">保存</button>
          <button class="btn-secondary" type="button" :disabled="loading" @click="cancel">キャンセル</button>
          <button
            v-if="mode === 'edit' && selected && !selected.is_self"
            class="btn-text danger"
            type="button"
            :disabled="loading"
            @click="confirmId = selected.id"
          >
            削除
          </button>
        </div>
      </form>
    </section>
  </div>
  <div v-if="confirmId !== null" class="modal-back">
    <div class="modal">
      <p>削除しますか？</p>
      <div class="actions">
        <button class="btn-primary" type="button" @click="confirmDelete">削除</button>
        <button class="btn-secondary" type="button" @click="confirmId = null">キャンセル</button>
      </div>
    </div>
  </div>
</template>
