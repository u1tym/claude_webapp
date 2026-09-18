<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  createAssignment,
  deleteAssignment,
  getAssignments,
  getFeatures,
  getUsers,
  type AssignmentItem,
  type FeatureItem,
  type UserItem,
} from "../api";

const emit = defineEmits<{ unauth: []; forbidden: [] }>();

const items = ref<AssignmentItem[]>([]);
const users = ref<UserItem[]>([]);
const features = ref<FeatureItem[]>([]);
const loading = ref(true);
const error = ref("");
const success = ref("");
const mode = ref<"list" | "create">("list");
const userId = ref("");
const featureId = ref("");
const displayOrder = ref("");
const confirmKey = ref<string | null>(null);

onMounted(() => {
  void reload();
});

async function reload(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    items.value = await getAssignments();
    users.value = await getUsers();
    features.value = await getFeatures();
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
  userId.value = "";
  featureId.value = "";
  displayOrder.value = "";
}

function cancel(): void {
  mode.value = "list";
}

function rowKey(item: AssignmentItem): string {
  return `${item.user_id}:${item.feature_id}`;
}

async function save(): Promise<void> {
  error.value = "";
  success.value = "";
  const orderText = String(displayOrder.value ?? "").trim();
  if (userId.value === "" || featureId.value === "" || orderText === "") {
    return;
  }
  const order = Number(orderText);
  if (!Number.isInteger(order)) {
    return;
  }
  loading.value = true;
  try {
    const result = await createAssignment(Number(userId.value), featureId.value, order);
    if (result === "invalid" || result === "missing" || result === "conflict") {
      error.value =
        result === "invalid" ? "入力が不正です" : result === "missing" ? "対象がありません" : "保存できませんでした";
      return;
    }
    success.value = "保存しました";
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
    cancel();
    items.value = await getAssignments();
  } catch (err) {
    handle(err);
  } finally {
    loading.value = false;
  }
}

async function confirmUnassign(): Promise<void> {
  if (confirmKey.value === null) {
    return;
  }
  const [uid, fid] = confirmKey.value.split(":");
  loading.value = true;
  try {
    const result = await deleteAssignment(Number(uid), fid);
    confirmKey.value = null;
    if (result !== "ok") {
      error.value = "削除できませんでした";
      return;
    }
    success.value = "解除しました";
    window.setTimeout(() => {
      success.value = "";
    }, 3000);
    items.value = await getAssignments();
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
              <th>機能</th>
              <th>表示順</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="rowKey(item)">
              <td>{{ item.username }}</td>
              <td>{{ item.feature_title }}</td>
              <td>{{ item.display_order }}</td>
              <td>
                <button
                  v-if="item.can_unassign"
                  class="btn-text danger"
                  type="button"
                  :disabled="loading"
                  @click="confirmKey = rowKey(item)"
                >
                  解除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="mode !== 'list'" class="panel form-panel">
      <form class="form" @submit.prevent="save">
        <select v-model="userId" aria-label="ユーザ" :disabled="loading" required>
          <option value="">ユーザ</option>
          <option v-for="user in users" :key="user.id" :value="String(user.id)">{{ user.username }}</option>
        </select>
        <select v-model="featureId" aria-label="機能" :disabled="loading" required>
          <option value="">機能</option>
          <option v-for="feature in features" :key="feature.id" :value="feature.id">{{ feature.title }}</option>
        </select>
        <input v-model="displayOrder" type="number" placeholder="表示順" aria-label="表示順" :disabled="loading" required />
        <div class="actions">
          <button class="btn-primary" type="submit" :disabled="loading">保存</button>
          <button class="btn-secondary" type="button" :disabled="loading" @click="cancel">キャンセル</button>
        </div>
      </form>
    </section>
  </div>
  <div v-if="confirmKey !== null" class="modal-back">
    <div class="modal">
      <p>解除しますか？</p>
      <div class="actions">
        <button class="btn-primary" type="button" @click="confirmUnassign">解除</button>
        <button class="btn-secondary" type="button" @click="confirmKey = null">キャンセル</button>
      </div>
    </div>
  </div>
</template>
