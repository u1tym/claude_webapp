<script setup lang="ts">
import { computed, ref } from "vue";
import { deletePart, errorMessage, partContentUrl, revisionContentUrl, undeletePart, updatePart } from "../api";
import type { Part } from "../types";
import { formatByteSize } from "../utils/file";
import { buildUpdateBody, contentVersion, draftFromPart, groupOf, type PartDraft } from "../utils/partDraft";
import ChecklistEditor from "./ChecklistEditor.vue";
import Icon from "./Icon.vue";
import PartContent from "./PartContent.vue";
import PartForm from "./PartForm.vue";

// パーツのダイアログ。カードを押すと開く。表示と操作（編集・削除・削除解除・ダウンロード・過去世代）、編集の入力。
// 背景を押しても閉じない。保存・削除などが成功したら done を出す（親が、ファイルを取得し直して、閉じる）。
const props = defineProps<{
  part: Part;
  /** ファイルが削除済みでない（追加・編集・削除・削除解除の操作ができる） */
  editable: boolean;
  /** チェックリストの表示を取得し直すための値 */
  refresh: number;
}>();

const emit = defineEmits<{ close: []; done: []; "checklist-changed": [] }>();

const mode = ref<"view" | "edit">("view");
const draft = ref<PartDraft>(draftFromPart(props.part));
const busy = ref(false);
const error = ref("");
const checklistTouched = ref(false);

const isBinary = computed(() => groupOf(props.part.type) === "binary");
const isChecklist = computed(() => props.part.type === "checklist");

function startEdit(): void {
  draft.value = draftFromPart(props.part);
  error.value = "";
  mode.value = "edit";
}

function cancelEdit(): void {
  error.value = "";
  mode.value = "view";
}

async function save(): Promise<void> {
  const built = buildUpdateBody(props.part, draft.value);
  if ("error" in built) {
    error.value = built.error;
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await updatePart(props.part.id, built.body);
    emit("done");
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}

async function remove(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    await deletePart(props.part.id);
    emit("done");
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}

async function restore(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    await undeletePart(props.part.id);
    emit("done");
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}

function close(): void {
  if (checklistTouched.value) {
    emit("done");
  } else {
    emit("close");
  }
}

function onChecklistChanged(): void {
  checklistTouched.value = true;
  emit("checklist-changed");
}
</script>

<template>
  <div class="modal-back">
    <div class="modal part-dialog" role="dialog" aria-modal="true" aria-label="パーツ">
      <div class="dialog-head">
        <h3>
          パーツ
          <span v-if="part.is_deleted" class="badge danger">削除済み</span>
        </h3>
        <button class="btn-secondary" type="button" aria-label="閉じる" :disabled="busy" @click="close">
          <Icon name="close" />
        </button>
      </div>
      <p v-if="error" class="msg-error" role="alert">{{ error }}</p>

      <div class="dialog-body">
        <template v-if="mode === 'view'">
          <PartContent :part="part" detailed :refresh="refresh" />

          <div v-if="isBinary && part.revisions.length > 0" class="revision-list">
            <h4>過去の世代</h4>
            <ul>
              <li v-for="rev in part.revisions" :key="rev.id">
                <span class="revision-label">
                  #{{ rev.revision_number }} {{ rev.filename }}（{{ rev.type }}・{{ formatByteSize(rev.byte_size) }}）
                  <span class="muted">{{ rev.created_at.replace("T", " ").slice(0, 16) }}</span>
                </span>
                <a class="btn-secondary link-button" :href="revisionContentUrl(rev.id)">ダウンロード</a>
              </li>
            </ul>
          </div>
        </template>

        <template v-else>
          <PartForm v-model="draft" :part-id="part.id" :version="contentVersion(part)" :type-locked="isChecklist" :allow-checklist="false" :busy="busy" @error="(m: string) => (error = m)" />
          <ChecklistEditor v-if="isChecklist && part.checklist_id !== null" :checklist-id="part.checklist_id" @changed="onChecklistChanged" />
        </template>
      </div>

      <div class="actions actions-end">
        <template v-if="mode === 'view'">
          <a v-if="isBinary" class="btn-secondary link-button" :href="partContentUrl(part.id, true, contentVersion(part))">ダウンロード</a>
          <button v-if="editable && part.is_deleted" class="btn-secondary" type="button" :disabled="busy" @click="restore">削除解除</button>
          <button v-if="editable && !part.is_deleted" class="btn-secondary danger" type="button" aria-label="削除" :disabled="busy" @click="remove">
            <Icon name="delete" />
          </button>
          <button v-if="editable && !part.is_deleted" class="btn-primary" type="button" aria-label="編集" :disabled="busy" @click="startEdit">
            <Icon name="edit" />
          </button>
        </template>
        <template v-else-if="isChecklist">
          <button class="btn-secondary" type="button" aria-label="閉じる" @click="close"><Icon name="close" /></button>
        </template>
        <template v-else>
          <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="busy" @click="cancelEdit">
            <Icon name="close" />
          </button>
          <button class="btn-primary" type="button" aria-label="保存" :disabled="busy" @click="save">
            <Icon name="check" />
          </button>
        </template>
      </div>
    </div>
  </div>
</template>
