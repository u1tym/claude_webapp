<script setup lang="ts">
import { computed, inject, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  addGoodsImage,
  AuthError,
  createGoods,
  deleteGoods,
  deleteGoodsImage,
  getArtists,
  getGoods,
  getMediaList,
  updateGoods,
  type Artist,
  type GoodsImage,
  type Media,
} from "../api";
import Icon from "../components/Icon.vue";

const route = useRoute();
const router = useRouter();
const onAuthError = inject<(error: unknown) => void>("onAuthError");

const isNew = computed(() => route.params.id === undefined);
const goodsId = computed(() => Number(route.params.id));

function handleError(err: unknown): void {
  if (err instanceof AuthError) {
    onAuthError?.(err);
    return;
  }
  error.value = "読み込みに失敗しました";
}

const loading = ref(true);
const saving = ref(false);
const error = ref("");
const mediaOptions = ref<Media[]>([]);
const artistOptions = ref<Artist[]>([]);

const mediaId = ref<number | null>(null);
const artistId = ref<number | null>(null);
const title = ref("");
const releaseDate = ref("");
const memo = ref("");
const isOwned = ref(false);
const codeNumber = ref("");

const existingImages = ref<GoodsImage[]>([]);
const removedImageIds = ref<number[]>([]);
const newImages = ref<{ image_type: string; image_data: string }[]>([]);
const imageInput = ref<HTMLInputElement | null>(null);

const visibleExistingImages = computed(() =>
  existingImages.value.filter((img) => !removedImageIds.value.includes(img.id)),
);

function imageSrc(image: { image_type: string; image_data: string }): string {
  return `data:${image.image_type};base64,${image.image_data}`;
}

function removeExistingImage(id: number): void {
  removedImageIds.value.push(id);
}

function removeNewImage(index: number): void {
  newImages.value.splice(index, 1);
}

function triggerImageInput(): void {
  imageInput.value?.click();
}

function onImageSelected(e: Event): void {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (file.type !== "image/png" && file.type !== "image/jpeg") {
    error.value = "画像はPNGまたはJPEGのみ選択できます";
    input.value = "";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const result = reader.result as string;
    const base64 = result.includes(",") ? result.split(",")[1]! : result;
    newImages.value.push({ image_type: file.type, image_data: base64 });
  };
  reader.readAsDataURL(file);
  input.value = "";
}

const deleteConfirmOpen = ref(false);
const deleting = ref(false);

function goBack(): void {
  router.push("/");
}

async function submit(): Promise<void> {
  error.value = "";
  if (!title.value.trim()) {
    error.value = "タイトルを入力してください";
    return;
  }
  if (mediaId.value == null || artistId.value == null) {
    error.value = "媒体とアーティストを選択してください";
    return;
  }
  saving.value = true;
  const payload = {
    media_id: mediaId.value,
    artist_id: artistId.value,
    title: title.value.trim(),
    release_date: releaseDate.value || null,
    memo: memo.value.trim() || null,
    is_owned: isOwned.value,
    code_number: codeNumber.value.trim() || null,
  };
  try {
    let targetId: number;
    if (isNew.value) {
      const created = await createGoods(payload);
      if (created === "invalid" || created === "missing") {
        error.value = "入力を確認してください";
        return;
      }
      targetId = created.id;
    } else {
      const updated = await updateGoods(goodsId.value, payload);
      if (updated === "invalid" || updated === "missing") {
        error.value = "入力を確認してください";
        return;
      }
      targetId = goodsId.value;
      for (const id of removedImageIds.value) {
        await deleteGoodsImage(targetId, id);
      }
    }
    for (const img of newImages.value) {
      const res = await addGoodsImage(targetId, img.image_type, img.image_data);
      if (res === "invalid" || res === "missing") {
        error.value = "画像の保存に失敗しました";
        return;
      }
    }
    router.push("/");
  } catch (err) {
    handleError(err);
  } finally {
    saving.value = false;
  }
}

async function executeDeleteGoods(): Promise<void> {
  deleting.value = true;
  try {
    const res = await deleteGoods(goodsId.value);
    if (res === "missing") {
      error.value = "対象がありません";
      deleteConfirmOpen.value = false;
      return;
    }
    router.push("/");
  } catch (err) {
    handleError(err);
  } finally {
    deleting.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    const [mediaList, artistList] = await Promise.all([getMediaList(), getArtists()]);
    mediaOptions.value = mediaList;
    artistOptions.value = artistList;

    if (!isNew.value) {
      const detail = await getGoods(goodsId.value);
      if (detail === "missing") {
        error.value = "商品が見つかりません";
        return;
      }
      mediaId.value = detail.media_id;
      artistId.value = detail.artist_id;
      title.value = detail.title;
      releaseDate.value = detail.release_date;
      memo.value = detail.memo ?? "";
      isOwned.value = detail.is_owned;
      codeNumber.value = detail.code_number ?? "";
      existingImages.value = detail.images;
    } else {
      const queryArtist = route.query.artist_id;
      const queryMedia = route.query.media_id;
      if (typeof queryArtist === "string") artistId.value = Number(queryArtist);
      if (typeof queryMedia === "string") mediaId.value = Number(queryMedia);
    }
  } catch (err) {
    handleError(err);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="view">
    <div class="actions">
      <button class="btn-text" type="button" aria-label="戻る" @click="goBack">
        <Icon name="back" />
      </button>
      <h1 class="section-title">{{ isNew ? "商品を追加" : "商品を編集" }}</h1>
    </div>

    <div v-if="loading" class="loading">読み込み中…</div>
    <template v-else>
      <p v-if="error" class="msg-error">{{ error }}</p>
      <div class="form">
        <div class="field">
          <label for="media-select">媒体</label>
          <select id="media-select" v-model="mediaId">
            <option :value="null">選択してください</option>
            <option v-for="m in mediaOptions" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="artist-select">アーティスト</label>
          <select id="artist-select" v-model="artistId">
            <option :value="null">選択してください</option>
            <option v-for="a in artistOptions" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="title-input">タイトル</label>
          <input id="title-input" v-model="title" type="text" />
        </div>
        <div class="field">
          <label for="release-date-input">リリース日</label>
          <input id="release-date-input" v-model="releaseDate" type="date" />
        </div>
        <div class="field">
          <label for="owned-input">
            <input id="owned-input" v-model="isOwned" type="checkbox" />
            所持
          </label>
        </div>
        <div class="field">
          <label for="code-number-input">品番</label>
          <input id="code-number-input" v-model="codeNumber" type="text" />
        </div>
        <div class="field">
          <label>画像</label>
          <div class="image-grid">
            <div v-for="img in visibleExistingImages" :key="img.id" class="image-item">
              <img :src="imageSrc(img)" alt="" />
              <button class="btn-text danger" type="button" aria-label="画像を削除" @click="removeExistingImage(img.id)">
                <Icon name="close" />
              </button>
            </div>
            <div v-for="(img, index) in newImages" :key="`new-${index}`" class="image-item">
              <img :src="imageSrc(img)" alt="" />
              <button class="btn-text danger" type="button" aria-label="画像を削除" @click="removeNewImage(index)">
                <Icon name="close" />
              </button>
            </div>
            <button class="image-add" type="button" aria-label="画像を追加" @click="triggerImageInput">
              <Icon name="plus" />
            </button>
          </div>
          <input
            ref="imageInput"
            type="file"
            accept="image/png,image/jpeg"
            style="display: none"
            @change="onImageSelected"
          />
        </div>
        <div class="field">
          <label for="memo-input">メモ</label>
          <textarea id="memo-input" v-model="memo" rows="3"></textarea>
        </div>
        <div class="actions">
          <button
            v-if="!isNew"
            class="btn-text danger"
            type="button"
            aria-label="削除"
            @click="deleteConfirmOpen = true"
          >
            <Icon name="delete" />
          </button>
          <button class="btn-primary push-end" type="button" :disabled="saving" aria-label="保存" @click="submit">
            <Icon name="check" />
          </button>
        </div>
      </div>
    </template>

    <div v-if="deleteConfirmOpen" class="modal-back" @click.self="deleteConfirmOpen = false">
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="section-title">削除の確認</h2>
        <p>「{{ title }}」を削除しますか。</p>
        <div class="actions actions-end">
          <button class="btn-secondary" type="button" aria-label="キャンセル" @click="deleteConfirmOpen = false">
            <Icon name="close" />
          </button>
          <button class="btn-primary" type="button" :disabled="deleting" aria-label="削除" @click="executeDeleteGoods">
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
  overflow: auto;
}
</style>
