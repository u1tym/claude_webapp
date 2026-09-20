<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  AuthError,
  createArtist,
  createMedia,
  createPerson,
  deleteArtist,
  deleteMedia,
  deletePerson,
  getArtistDetail,
  getArtists,
  getGoodsList,
  getMediaList,
  getPersons,
  getRelatedArtists,
  getRelatedMedia,
  renameMedia,
  renamePerson,
  updateArtist,
  type Artist,
  type ArtistDetail,
  type GoodsListItem,
  type Media,
  type Person,
} from "../api";
import Icon from "../components/Icon.vue";

const router = useRouter();
const onAuthError = inject<(error: unknown) => void>("onAuthError");

function handleError(err: unknown): void {
  if (err instanceof AuthError) {
    onAuthError?.(err);
    return;
  }
  errorMessage.value = "読み込みに失敗しました";
}

let successTimer: ReturnType<typeof setTimeout> | null = null;
function showSuccess(message: string): void {
  if (successTimer) clearTimeout(successTimer);
  successMessage.value = message;
  successTimer = window.setTimeout(() => {
    successMessage.value = "";
  }, 3000);
}

const loading = ref(true);
const errorMessage = ref("");
const successMessage = ref("");

const persons = ref<Person[]>([]);
const selectedPersonId = ref<number | null>(null);

const relatedArtists = ref<Artist[]>([]);
const selectedArtistId = ref<number | "all" | null>(null);

const relatedMediaList = ref<Media[]>([]);
const selectedMediaId = ref<number | "all" | null>(null);

const goodsLoading = ref(false);
const goodsList = ref<GoodsListItem[]>([]);
const titleFilter = ref("");

const filteredGoods = computed(() => {
  const term = titleFilter.value.trim().toLowerCase();
  if (!term) return goodsList.value;
  return goodsList.value.filter((g) => g.title.toLowerCase().includes(term));
});

function imageSrc(item: GoodsListItem): string {
  if (!item.thumbnail_image_data || !item.thumbnail_image_type) return "";
  return `data:${item.thumbnail_image_type};base64,${item.thumbnail_image_data}`;
}

function toEdit(item: GoodsListItem): void {
  router.push(`/goods/${item.goods_id}/edit`);
}

function toNew(): void {
  const query: Record<string, string> = {};
  if (typeof selectedArtistId.value === "number") query.artist_id = String(selectedArtistId.value);
  if (typeof selectedMediaId.value === "number") query.media_id = String(selectedMediaId.value);
  router.push({ path: "/goods/new", query });
}

async function loadPersons(): Promise<void> {
  persons.value = await getPersons();
}

watch(selectedPersonId, async (id) => {
  selectedArtistId.value = null;
  selectedMediaId.value = null;
  relatedArtists.value = [];
  relatedMediaList.value = [];
  goodsList.value = [];
  errorMessage.value = "";
  if (id == null) return;
  try {
    const [artistsRes, mediaRes] = await Promise.all([getRelatedArtists(id), getRelatedMedia(id)]);
    if (artistsRes === "missing" || mediaRes === "missing") {
      errorMessage.value = "対象がありません";
      return;
    }
    relatedArtists.value = artistsRes;
    relatedMediaList.value = mediaRes;
  } catch (err) {
    handleError(err);
  }
});

watch(selectedArtistId, () => {
  selectedMediaId.value = null;
  goodsList.value = [];
});

watch(selectedMediaId, async (mediaId) => {
  if (selectedPersonId.value == null || selectedArtistId.value === null || mediaId === null) return;
  await loadGoodsList();
});

async function loadGoodsList(): Promise<void> {
  if (selectedPersonId.value == null) return;
  goodsLoading.value = true;
  errorMessage.value = "";
  try {
    const artistParam = selectedArtistId.value === "all" ? null : (selectedArtistId.value as number | null);
    const mediaParam = selectedMediaId.value === "all" ? null : (selectedMediaId.value as number | null);
    const res = await getGoodsList(selectedPersonId.value, artistParam, mediaParam);
    if (res === "missing") {
      errorMessage.value = "対象がありません";
      goodsList.value = [];
    } else {
      goodsList.value = res;
    }
  } catch (err) {
    handleError(err);
  } finally {
    goodsLoading.value = false;
  }
}

// ---- 人物・アーティスト・媒体の管理パネル ------------------------------------------

const settingsOpen = ref(false);
const activeTab = ref<"person" | "artist" | "media">("person");
const managementLoading = ref(false);
const managementLoaded = ref(false);
const managementError = ref("");
const artistDetails = ref<ArtistDetail[]>([]);
const mediaList = ref<Media[]>([]);

function openSettings(): void {
  settingsOpen.value = true;
  activeTab.value = "person";
  managementError.value = "";
  void loadManagementData();
}

function closeSettings(): void {
  settingsOpen.value = false;
  personFormOpen.value = false;
  artistFormOpen.value = false;
  mediaFormOpen.value = false;
  deleteTarget.value = null;
}

async function loadManagementData(): Promise<void> {
  if (managementLoaded.value) return;
  managementLoading.value = true;
  managementError.value = "";
  try {
    await Promise.all([loadPersons(), loadManagementArtists(), loadManagementMedia()]);
    managementLoaded.value = true;
  } catch (err) {
    handleError(err);
  } finally {
    managementLoading.value = false;
  }
}

async function loadManagementArtists(): Promise<void> {
  const list = await getArtists();
  const details = await Promise.all(list.map((a) => getArtistDetail(a.id)));
  artistDetails.value = details.filter((d): d is ArtistDetail => d !== "missing");
}

async function loadManagementMedia(): Promise<void> {
  mediaList.value = await getMediaList();
}

async function refreshRelatedForSelectedPerson(): Promise<void> {
  if (selectedPersonId.value == null) return;
  const [artistsRes, mediaRes] = await Promise.all([
    getRelatedArtists(selectedPersonId.value),
    getRelatedMedia(selectedPersonId.value),
  ]);
  if (artistsRes !== "missing") relatedArtists.value = artistsRes;
  if (mediaRes !== "missing") relatedMediaList.value = mediaRes;
}

// ---- 人物フォーム ---------------------------------------------------------------

const personFormOpen = ref(false);
const personFormMode = ref<"add" | "rename">("add");
const personFormId = ref<number | null>(null);
const personFormName = ref("");
const personFormError = ref("");
const personFormSaving = ref(false);

function openPersonAdd(): void {
  personFormMode.value = "add";
  personFormId.value = null;
  personFormName.value = "";
  personFormError.value = "";
  personFormOpen.value = true;
}

function openPersonRename(p: Person): void {
  personFormMode.value = "rename";
  personFormId.value = p.id;
  personFormName.value = p.name;
  personFormError.value = "";
  personFormOpen.value = true;
}

async function submitPersonForm(): Promise<void> {
  if (!personFormName.value.trim()) {
    personFormError.value = "名称を入力してください";
    return;
  }
  personFormSaving.value = true;
  personFormError.value = "";
  try {
    const result =
      personFormMode.value === "add"
        ? await createPerson(personFormName.value.trim())
        : await renamePerson(personFormId.value as number, personFormName.value.trim());
    if (result === "invalid") {
      personFormError.value = "名称を入力してください";
      return;
    }
    if (result === "missing") {
      personFormError.value = "対象がありません";
      return;
    }
    await loadPersons();
    showSuccess("保存しました");
    personFormOpen.value = false;
  } catch (err) {
    handleError(err);
  } finally {
    personFormSaving.value = false;
  }
}

// ---- アーティストフォーム ----------------------------------------------------------

const artistFormOpen = ref(false);
const artistFormMode = ref<"add" | "edit">("add");
const artistFormId = ref<number | null>(null);
const artistFormName = ref("");
const artistFormPersonIds = ref<number[]>([]);
const artistFormError = ref("");
const artistFormSaving = ref(false);

function openArtistAdd(): void {
  artistFormMode.value = "add";
  artistFormId.value = null;
  artistFormName.value = "";
  artistFormPersonIds.value = [];
  artistFormError.value = "";
  artistFormOpen.value = true;
}

function openArtistEdit(a: ArtistDetail): void {
  artistFormMode.value = "edit";
  artistFormId.value = a.id;
  artistFormName.value = a.name;
  artistFormPersonIds.value = a.persons.map((p) => p.id);
  artistFormError.value = "";
  artistFormOpen.value = true;
}

async function submitArtistForm(): Promise<void> {
  if (!artistFormName.value.trim()) {
    artistFormError.value = "名称を入力してください";
    return;
  }
  artistFormSaving.value = true;
  artistFormError.value = "";
  try {
    const result =
      artistFormMode.value === "add"
        ? await createArtist(artistFormName.value.trim(), artistFormPersonIds.value)
        : await updateArtist(artistFormId.value as number, artistFormName.value.trim(), artistFormPersonIds.value);
    if (result === "invalid") {
      artistFormError.value = "名称を入力してください";
      return;
    }
    if (result === "missing") {
      artistFormError.value = "選択した人物を確認してください";
      return;
    }
    await loadManagementArtists();
    await refreshRelatedForSelectedPerson();
    showSuccess("保存しました");
    artistFormOpen.value = false;
  } catch (err) {
    handleError(err);
  } finally {
    artistFormSaving.value = false;
  }
}

// ---- 媒体フォーム -----------------------------------------------------------------

const mediaFormOpen = ref(false);
const mediaFormMode = ref<"add" | "rename">("add");
const mediaFormId = ref<number | null>(null);
const mediaFormName = ref("");
const mediaFormError = ref("");
const mediaFormSaving = ref(false);

function openMediaAdd(): void {
  mediaFormMode.value = "add";
  mediaFormId.value = null;
  mediaFormName.value = "";
  mediaFormError.value = "";
  mediaFormOpen.value = true;
}

function openMediaRename(m: Media): void {
  mediaFormMode.value = "rename";
  mediaFormId.value = m.id;
  mediaFormName.value = m.name;
  mediaFormError.value = "";
  mediaFormOpen.value = true;
}

async function submitMediaForm(): Promise<void> {
  if (!mediaFormName.value.trim()) {
    mediaFormError.value = "名称を入力してください";
    return;
  }
  mediaFormSaving.value = true;
  mediaFormError.value = "";
  try {
    const result =
      mediaFormMode.value === "add"
        ? await createMedia(mediaFormName.value.trim())
        : await renameMedia(mediaFormId.value as number, mediaFormName.value.trim());
    if (result === "invalid") {
      mediaFormError.value = "名称を入力してください";
      return;
    }
    if (result === "missing") {
      mediaFormError.value = "対象がありません";
      return;
    }
    await loadManagementMedia();
    showSuccess("保存しました");
    mediaFormOpen.value = false;
  } catch (err) {
    handleError(err);
  } finally {
    mediaFormSaving.value = false;
  }
}

// ---- 削除確認 --------------------------------------------------------------------

const deleteTarget = ref<{ type: "person" | "artist" | "media"; id: number; label: string } | null>(null);
const deleteError = ref("");
const deleting = ref(false);

function confirmDelete(type: "person" | "artist" | "media", id: number, label: string): void {
  deleteTarget.value = { type, id, label };
  deleteError.value = "";
}

function cancelDelete(): void {
  deleteTarget.value = null;
}

async function executeDelete(): Promise<void> {
  if (!deleteTarget.value) return;
  deleting.value = true;
  deleteError.value = "";
  try {
    const { type, id } = deleteTarget.value;
    const result =
      type === "person" ? await deletePerson(id) : type === "artist" ? await deleteArtist(id) : await deleteMedia(id);
    if (result === "referenced") {
      deleteError.value = "他のデータから参照されているため削除できません";
      return;
    }
    if (result === "missing") {
      deleteError.value = "対象がありません";
      return;
    }
    if (type === "person") {
      await loadPersons();
      if (selectedPersonId.value === id) selectedPersonId.value = null;
    } else if (type === "artist") {
      artistDetails.value = artistDetails.value.filter((a) => a.id !== id);
      await refreshRelatedForSelectedPerson();
    } else {
      mediaList.value = mediaList.value.filter((m) => m.id !== id);
      await refreshRelatedForSelectedPerson();
    }
    deleteTarget.value = null;
    showSuccess("削除しました");
  } catch (err) {
    handleError(err);
  } finally {
    deleting.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadPersons();
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="view">
    <p v-if="successMessage" class="msg-success">{{ successMessage }}</p>
    <p v-if="errorMessage" class="msg-error">{{ errorMessage }}</p>

    <div class="toolbar">
      <div class="field">
        <label for="person-select">人物</label>
        <select id="person-select" v-model="selectedPersonId">
          <option :value="null">選択してください</option>
          <option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>
      <div class="field">
        <label for="artist-select">アーティスト</label>
        <select id="artist-select" v-model="selectedArtistId" :disabled="selectedPersonId == null">
          <option :value="null">選択してください</option>
          <option value="all">すべて</option>
          <option v-for="a in relatedArtists" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
      </div>
      <div class="field">
        <label for="media-select">媒体</label>
        <select id="media-select" v-model="selectedMediaId" :disabled="selectedArtistId == null">
          <option :value="null">選択してください</option>
          <option value="all">すべて</option>
          <option v-for="m in relatedMediaList" :key="m.id" :value="m.id">{{ m.name }}</option>
        </select>
      </div>
      <div class="field">
        <label for="title-filter">タイトルで絞り込み</label>
        <input id="title-filter" v-model="titleFilter" type="text" :disabled="goodsList.length === 0" />
      </div>
      <button class="btn-text push-end" type="button" aria-label="設定メニューを開く" @click="openSettings">
        <Icon name="config" />
      </button>
    </div>

    <div v-if="loading" class="loading">読み込み中…</div>
    <template v-else-if="selectedPersonId == null">
      <p class="caption">人物を選ぶと商品を絞り込めます。</p>
    </template>
    <template v-else-if="goodsLoading">
      <div class="loading">読み込み中…</div>
    </template>
    <template v-else-if="selectedMediaId == null">
      <p class="caption">アーティスト・媒体を選ぶと商品一覧が表示されます。</p>
    </template>
    <div v-else class="panel">
      <div v-if="filteredGoods.length === 0" class="empty">
        {{ goodsList.length === 0 ? "データがありません" : "絞り込み条件に一致する商品はありません" }}
      </div>
      <ul v-else class="list plain-list">
        <li v-for="g in filteredGoods" :key="g.goods_id" class="list-item">
          <button class="row" type="button" @click="toEdit(g)">
            <span class="thumb">
              <img v-if="imageSrc(g)" :src="imageSrc(g)" alt="" class="thumb-img" />
              <span v-else class="thumb-placeholder">No image</span>
            </span>
            <span class="detail-value">
              {{ g.title }}
              <span class="caption">{{ g.media_name }} / {{ g.release_date }}</span>
            </span>
            <span class="badge" :class="{ 'is-owned': g.is_owned }">{{ g.is_owned ? "所持" : "未所持" }}</span>
          </button>
        </li>
      </ul>
    </div>

    <button class="btn-primary push-end" type="button" aria-label="新規追加" @click="toNew">
      <Icon name="plus" />
    </button>

    <div v-if="settingsOpen" class="modal-back" @click.self="closeSettings">
      <div class="modal" role="dialog" aria-modal="true">
        <div class="actions">
          <h2 class="section-title" style="flex: 1">管理</h2>
          <button class="btn-text" type="button" aria-label="閉じる" @click="closeSettings">
            <Icon name="close" />
          </button>
        </div>

        <p v-if="managementError" class="msg-error">{{ managementError }}</p>
        <div v-if="managementLoading" class="loading">読み込み中…</div>
        <template v-else>
          <div class="tabs">
            <button
              class="tab-button"
              :class="{ 'is-current': activeTab === 'person' }"
              type="button"
              @click="activeTab = 'person'"
            >
              人物
            </button>
            <button
              class="tab-button"
              :class="{ 'is-current': activeTab === 'artist' }"
              type="button"
              @click="activeTab = 'artist'"
            >
              アーティスト
            </button>
            <button
              class="tab-button"
              :class="{ 'is-current': activeTab === 'media' }"
              type="button"
              @click="activeTab = 'media'"
            >
              媒体
            </button>
          </div>

          <template v-if="activeTab === 'person'">
            <div class="actions actions-end">
              <button class="btn-secondary" type="button" aria-label="人物を追加" @click="openPersonAdd">
                <Icon name="plus" />
              </button>
            </div>
            <ul class="list plain-list">
              <li v-for="p in persons" :key="p.id" class="list-item">
                <span class="row">{{ p.name }}</span>
                <div class="reorder-actions">
                  <button class="btn-text" type="button" aria-label="名称変更" @click="openPersonRename(p)">
                    <Icon name="edit" />
                  </button>
                  <button
                    class="btn-text danger"
                    type="button"
                    aria-label="削除"
                    @click="confirmDelete('person', p.id, p.name)"
                  >
                    <Icon name="delete" />
                  </button>
                </div>
              </li>
            </ul>
          </template>

          <template v-else-if="activeTab === 'artist'">
            <div class="actions actions-end">
              <button class="btn-secondary" type="button" aria-label="アーティストを追加" @click="openArtistAdd">
                <Icon name="plus" />
              </button>
            </div>
            <ul class="list plain-list">
              <li v-for="a in artistDetails" :key="a.id" class="list-item">
                <span class="row">
                  {{ a.name }}
                  <span v-if="a.persons.length > 0" class="caption">
                    所属: {{ a.persons.map((p) => p.name).join("、") }}
                  </span>
                </span>
                <div class="reorder-actions">
                  <button class="btn-text" type="button" aria-label="名称変更" @click="openArtistEdit(a)">
                    <Icon name="edit" />
                  </button>
                  <button
                    class="btn-text danger"
                    type="button"
                    aria-label="削除"
                    @click="confirmDelete('artist', a.id, a.name)"
                  >
                    <Icon name="delete" />
                  </button>
                </div>
              </li>
            </ul>
          </template>

          <template v-else>
            <div class="actions actions-end">
              <button class="btn-secondary" type="button" aria-label="媒体を追加" @click="openMediaAdd">
                <Icon name="plus" />
              </button>
            </div>
            <ul class="list plain-list">
              <li v-for="m in mediaList" :key="m.id" class="list-item">
                <span class="row">{{ m.name }}</span>
                <div class="reorder-actions">
                  <button class="btn-text" type="button" aria-label="名称変更" @click="openMediaRename(m)">
                    <Icon name="edit" />
                  </button>
                  <button
                    class="btn-text danger"
                    type="button"
                    aria-label="削除"
                    @click="confirmDelete('media', m.id, m.name)"
                  >
                    <Icon name="delete" />
                  </button>
                </div>
              </li>
            </ul>
          </template>
        </template>
      </div>
    </div>

    <div v-if="personFormOpen" class="modal-back" @click.self="personFormOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="section-title">{{ personFormMode === "add" ? "人物を追加" : "人物の名称変更" }}</h2>
        <p v-if="personFormError" class="msg-error">{{ personFormError }}</p>
        <div class="form">
          <div class="field">
            <label for="person-name">名称</label>
            <input id="person-name" v-model="personFormName" type="text" />
          </div>
          <div class="actions actions-end">
            <button class="btn-secondary" type="button" aria-label="キャンセル" @click="personFormOpen = false">
              <Icon name="close" />
            </button>
            <button class="btn-primary" type="button" :disabled="personFormSaving" aria-label="保存" @click="submitPersonForm">
              <Icon name="check" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="artistFormOpen" class="modal-back" @click.self="artistFormOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="section-title">{{ artistFormMode === "add" ? "アーティストを追加" : "アーティストの変更" }}</h2>
        <p v-if="artistFormError" class="msg-error">{{ artistFormError }}</p>
        <div class="form">
          <div class="field">
            <label for="artist-name">名称</label>
            <input id="artist-name" v-model="artistFormName" type="text" />
          </div>
          <div class="field">
            <label>所属する人物</label>
            <div class="list plain-list" style="max-height: 180px">
              <label v-for="p in persons" :key="p.id" class="list-item" style="border-bottom: 0; padding-bottom: 0">
                <input v-model="artistFormPersonIds" type="checkbox" :value="p.id" />
                {{ p.name }}
              </label>
            </div>
          </div>
          <div class="actions actions-end">
            <button class="btn-secondary" type="button" aria-label="キャンセル" @click="artistFormOpen = false">
              <Icon name="close" />
            </button>
            <button class="btn-primary" type="button" :disabled="artistFormSaving" aria-label="保存" @click="submitArtistForm">
              <Icon name="check" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="mediaFormOpen" class="modal-back" @click.self="mediaFormOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="section-title">{{ mediaFormMode === "add" ? "媒体を追加" : "媒体の名称変更" }}</h2>
        <p v-if="mediaFormError" class="msg-error">{{ mediaFormError }}</p>
        <div class="form">
          <div class="field">
            <label for="media-name">名称</label>
            <input id="media-name" v-model="mediaFormName" type="text" />
          </div>
          <div class="actions actions-end">
            <button class="btn-secondary" type="button" aria-label="キャンセル" @click="mediaFormOpen = false">
              <Icon name="close" />
            </button>
            <button class="btn-primary" type="button" :disabled="mediaFormSaving" aria-label="保存" @click="submitMediaForm">
              <Icon name="check" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="deleteTarget" class="modal-back" @click.self="cancelDelete">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="section-title">削除の確認</h2>
        <p>「{{ deleteTarget.label }}」を削除しますか。</p>
        <p v-if="deleteError" class="msg-error">{{ deleteError }}</p>
        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" @click="cancelDelete">
            <Icon name="close" />
          </button>
          <button class="btn-primary" type="button" :disabled="deleting" aria-label="削除" @click="executeDelete">
            <Icon name="delete" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space) * 2);
  min-height: 0;
  flex: 1;
}
</style>
