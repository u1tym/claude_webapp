<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  createCategory,
  createItem,
  deleteCategory,
  deleteItem,
  errorMessage,
  getChecklist,
  moveItem,
  renameCategory,
  reorderCategories,
  updateChecklistTitle,
  updateItem,
} from "../api";
import type { Checklist, ChecklistCategory } from "../types";
import ConfirmDialog from "./ConfirmDialog.vue";
import Icon from "./Icon.vue";

// チェックリストの編集。操作のたびにサーバへ送り、応答（最新の状態）で表示を置き換える。
// カテゴリと項目は、ドラッグでも、「上へ」「下へ」・移動先の選択欄でも、並び替え・移動できる。
const props = defineProps<{ checklistId: number }>();
const emit = defineEmits<{ changed: []; error: [message: string] }>();

const state = ref<Checklist | null>(null);
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const titleDraft = ref("");
const newCategory = ref("");
const newItem = reactive<Record<string, string>>({});
const categoryDraft = reactive<Record<number, string>>({});
const itemDraft = reactive<Record<number, string>>({});
const confirmCategory = ref<ChecklistCategory | null>(null);

const named = computed(() => state.value?.categories.filter((c) => !c.is_unnamed) ?? []);
const unnamed = computed(() => state.value?.categories.find((c) => c.is_unnamed) ?? null);

function apply(next: Checklist, notify = true): void {
  state.value = next;
  titleDraft.value = next.title;
  for (const category of next.categories) {
    categoryDraft[category.id] = category.name;
    for (const item of category.items) {
      itemDraft[item.id] = item.title;
    }
  }
  if (notify) {
    emit("changed");
  }
}

async function call(action: () => Promise<Checklist>): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    apply(await action());
  } catch (e) {
    error.value = errorMessage(e);
    // 入力欄を、保存済みの状態へ戻す
    if (state.value) {
      apply(state.value, false);
    }
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    apply(await getChecklist(props.checklistId), false);
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
});

// ---- タイトル・カテゴリ ------------------------------------------------------

function saveTitle(): void {
  if (state.value && titleDraft.value.trim() !== state.value.title) {
    void call(() => updateChecklistTitle(props.checklistId, titleDraft.value));
  }
}

function addCategory(): void {
  const name = newCategory.value.trim();
  if (name === "") {
    error.value = "カテゴリ名を入力してください";
    return;
  }
  newCategory.value = "";
  void call(() => createCategory(props.checklistId, name));
}

function saveCategoryName(category: ChecklistCategory): void {
  const name = (categoryDraft[category.id] ?? "").trim();
  if (name === category.name) {
    return;
  }
  if (name === "") {
    error.value = "カテゴリ名を入力してください";
    categoryDraft[category.id] = category.name;
    return;
  }
  void call(() => renameCategory(props.checklistId, category.id, name));
}

function moveCategory(category: ChecklistCategory, delta: -1 | 1): void {
  const ids = named.value.map((c) => c.id);
  const index = ids.indexOf(category.id);
  const target = index + delta;
  if (target < 0 || target >= ids.length) {
    return;
  }
  ids.splice(target, 0, ids.splice(index, 1)[0]);
  void call(() => reorderCategories(props.checklistId, ids));
}

function askDeleteCategory(category: ChecklistCategory): void {
  confirmCategory.value = category;
}

function doDeleteCategory(): void {
  const category = confirmCategory.value;
  confirmCategory.value = null;
  if (category) {
    void call(() => deleteCategory(props.checklistId, category.id));
  }
}

// ---- 項目 -----------------------------------------------------------------

function addItem(categoryId: number | null): void {
  const key = String(categoryId);
  const title = (newItem[key] ?? "").trim();
  newItem[key] = "";
  void call(() => createItem(props.checklistId, categoryId, title));
}

function saveItemTitle(categoryItemId: number, current: string): void {
  const title = (itemDraft[categoryItemId] ?? "").trim();
  if (title !== current) {
    void call(() => updateItem(props.checklistId, categoryItemId, { title }));
  }
}

function toggleItem(itemId: number, event: Event): void {
  void call(() => updateItem(props.checklistId, itemId, { is_checked: (event.target as HTMLInputElement).checked }));
}

function removeItem(itemId: number): void {
  void call(() => deleteItem(props.checklistId, itemId));
}

function moveWithin(category: ChecklistCategory, index: number, delta: -1 | 1): void {
  const item = category.items[index];
  const target = index + delta;
  if (!item || target < 0 || target >= category.items.length) {
    return;
  }
  void call(() => moveItem(props.checklistId, item.id, category.id, target));
}

function moveToCategory(itemId: number, event: Event): void {
  const select = event.target as HTMLSelectElement;
  const value = select.value;
  select.value = "";
  if (value !== "") {
    // 移動先のカテゴリの末尾へ（件数以上の位置は、末尾になる）
    void call(() => moveItem(props.checklistId, itemId, Number(value), 1_000_000));
  }
}

// ---- ドラッグ操作 ------------------------------------------------------------

type Drag = { kind: "category"; id: number } | { kind: "item"; id: number };
const drag = ref<Drag | null>(null);
const dropHint = ref("");

function dragStart(payload: Drag, event: DragEvent): void {
  drag.value = payload;
  event.dataTransfer?.setData("text/plain", String(payload.id));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
  }
}

function dragEnd(): void {
  drag.value = null;
  dropHint.value = "";
}

function dragOver(hint: string, event: DragEvent): void {
  if (drag.value) {
    event.preventDefault();
    dropHint.value = hint;
  }
}

function dropOnCategory(target: ChecklistCategory): void {
  const dragging = drag.value;
  dragEnd();
  if (!dragging) {
    return;
  }
  if (dragging.kind === "category") {
    if (dragging.id === target.id || target.is_unnamed) {
      return;
    }
    const ids = named.value.map((c) => c.id).filter((id) => id !== dragging.id);
    ids.splice(ids.indexOf(target.id), 0, dragging.id);
    void call(() => reorderCategories(props.checklistId, ids));
    return;
  }
  // 項目を、カテゴリの末尾へ
  void call(() => moveItem(props.checklistId, dragging.id, target.id, 1_000_000));
}

function dropOnItem(category: ChecklistCategory, index: number): void {
  const dragging = drag.value;
  dragEnd();
  if (!dragging || dragging.kind !== "item" || dragging.id === category.items[index]?.id) {
    return;
  }
  void call(() => moveItem(props.checklistId, dragging.id, category.id, index));
}
</script>

<template>
  <div class="checklist-editor">
    <p v-if="loading" class="centered">読み込み中…</p>
    <template v-else-if="state">
      <p v-if="error" class="msg-error" role="alert">{{ error }}</p>

      <div class="field">
        <label for="cl-title">タイトル</label>
        <input id="cl-title" v-model="titleDraft" type="text" :disabled="busy" @blur="saveTitle" @keydown.enter.prevent="saveTitle" />
      </div>

      <!-- 無名カテゴリ（見出しなし）。項目の追加は、ここから（カテゴリを指定しない追加は、無名カテゴリに入る） -->
      <section class="cl-category" :class="{ 'is-drop': dropHint === 'unnamed' }" @dragover="unnamed && dragOver('unnamed', $event)" @drop.prevent="unnamed && dropOnCategory(unnamed)">
        <ul v-if="unnamed" class="cl-items">
          <li
            v-for="(item, index) in unnamed.items"
            :key="item.id"
            class="cl-item"
            draggable="true"
            @dragstart="dragStart({ kind: 'item', id: item.id }, $event)"
            @dragend="dragEnd"
            @dragover="dragOver(`i${item.id}`, $event)"
            @drop.prevent.stop="dropOnItem(unnamed, index)"
          >
            <input type="checkbox" :checked="item.is_checked" :disabled="busy" :aria-label="`${item.title || '項目'} のチェック`" @change="toggleItem(item.id, $event)" />
            <input v-model="itemDraft[item.id]" type="text" class="cl-item-title" aria-label="項目のタイトル" :disabled="busy" @blur="saveItemTitle(item.id, item.title)" @keydown.enter.prevent="saveItemTitle(item.id, item.title)" />
            <button class="btn-secondary" type="button" :disabled="busy || index === 0" @click="moveWithin(unnamed, index, -1)">上へ</button>
            <button class="btn-secondary" type="button" :disabled="busy || index === unnamed.items.length - 1" @click="moveWithin(unnamed, index, 1)">下へ</button>
            <select class="cl-move" aria-label="移動先のカテゴリ" :disabled="busy || named.length === 0" @change="moveToCategory(item.id, $event)">
              <option value="">移動先</option>
              <option v-for="c in named" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <button class="btn-text danger" type="button" aria-label="項目の削除" :disabled="busy" @click="removeItem(item.id)"><Icon name="delete" /></button>
          </li>
        </ul>
        <div class="cl-add">
          <input v-model="newItem['null']" type="text" aria-label="項目のタイトル（カテゴリなし）" placeholder="項目のタイトル（カテゴリなし）" :disabled="busy" @keydown.enter.prevent="addItem(null)" />
          <button class="btn-secondary" type="button" :disabled="busy" @click="addItem(null)">項目を追加</button>
        </div>
      </section>

      <section
        v-for="(category, cindex) in named"
        :key="category.id"
        class="cl-category"
        :class="{ 'is-drop': dropHint === `c${category.id}` }"
        @dragover="dragOver(`c${category.id}`, $event)"
        @drop.prevent="dropOnCategory(category)"
      >
        <div class="cl-category-head">
          <span class="drag-handle" draggable="true" role="button" tabindex="-1" aria-label="ドラッグして並び替え" @dragstart="dragStart({ kind: 'category', id: category.id }, $event)" @dragend="dragEnd">⠿</span>
          <input v-model="categoryDraft[category.id]" type="text" class="cl-category-name" aria-label="カテゴリ名" :disabled="busy" @blur="saveCategoryName(category)" @keydown.enter.prevent="saveCategoryName(category)" />
          <button class="btn-secondary" type="button" :disabled="busy || cindex === 0" @click="moveCategory(category, -1)">上へ</button>
          <button class="btn-secondary" type="button" :disabled="busy || cindex === named.length - 1" @click="moveCategory(category, 1)">下へ</button>
          <button class="btn-text danger" type="button" aria-label="カテゴリの削除" :disabled="busy" @click="askDeleteCategory(category)"><Icon name="delete" /></button>
        </div>
        <ul class="cl-items">
          <li
            v-for="(item, index) in category.items"
            :key="item.id"
            class="cl-item"
            draggable="true"
            @dragstart="dragStart({ kind: 'item', id: item.id }, $event)"
            @dragend="dragEnd"
            @dragover="dragOver(`i${item.id}`, $event)"
            @drop.prevent.stop="dropOnItem(category, index)"
          >
            <input type="checkbox" :checked="item.is_checked" :disabled="busy" :aria-label="`${item.title || '項目'} のチェック`" @change="toggleItem(item.id, $event)" />
            <input v-model="itemDraft[item.id]" type="text" class="cl-item-title" aria-label="項目のタイトル" :disabled="busy" @blur="saveItemTitle(item.id, item.title)" @keydown.enter.prevent="saveItemTitle(item.id, item.title)" />
            <button class="btn-secondary" type="button" :disabled="busy || index === 0" @click="moveWithin(category, index, -1)">上へ</button>
            <button class="btn-secondary" type="button" :disabled="busy || index === category.items.length - 1" @click="moveWithin(category, index, 1)">下へ</button>
            <select class="cl-move" aria-label="移動先のカテゴリ" :disabled="busy" @change="moveToCategory(item.id, $event)">
              <option value="">移動先</option>
              <option v-if="unnamed" :value="unnamed.id">（カテゴリなし）</option>
              <option v-for="c in named.filter((n) => n.id !== category.id)" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
            <button class="btn-text danger" type="button" aria-label="項目の削除" :disabled="busy" @click="removeItem(item.id)"><Icon name="delete" /></button>
          </li>
        </ul>
        <div class="cl-add">
          <input v-model="newItem[String(category.id)]" type="text" :aria-label="`${category.name} の項目のタイトル`" placeholder="項目のタイトル" :disabled="busy" @keydown.enter.prevent="addItem(category.id)" />
          <button class="btn-secondary" type="button" :disabled="busy" @click="addItem(category.id)">項目を追加</button>
        </div>
      </section>

      <div class="cl-add cl-add-category">
        <input v-model="newCategory" type="text" aria-label="カテゴリ名" placeholder="カテゴリ名" :disabled="busy" @keydown.enter.prevent="addCategory" />
        <button class="btn-secondary" type="button" :disabled="busy" @click="addCategory">カテゴリを追加</button>
      </div>
    </template>

    <ConfirmDialog
      v-if="confirmCategory"
      title="カテゴリの削除"
      :message="`カテゴリ「${confirmCategory.name}」を削除します。中の項目も削除されます。よろしいですか？`"
      confirm-label="削除"
      danger
      @confirm="doDeleteCategory"
      @cancel="confirmCategory = null"
    />
  </div>
</template>
