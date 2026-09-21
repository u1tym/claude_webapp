<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import type { PrintFile } from "../types";
import PartContent from "./PartContent.vue";

// PDF 出力（印刷）用のレイアウト。画面には出さず、印刷のときだけ表示する（styles.css の印刷用のスタイル）。
// 画像・チェックリストの読み込みが終わったら、ready を出す。
const props = defineProps<{
  files: PrintFile[];
  /** ファイルごとに改ページする */
  pageBreak: boolean;
}>();

const emit = defineEmits<{ ready: [] }>();

const root = ref<HTMLElement | null>(null);
let pendingChecklists = props.files.reduce(
  (sum, file) => sum + file.parts.filter((p) => p.type === "checklist").length,
  0,
);
let checklistsDone = pendingChecklists === 0;
let mounted = false;
let notified = false;

function waitForImages(container: HTMLElement): Promise<void> {
  const images = Array.from(container.querySelectorAll("img"));
  const waits = images
    .filter((img) => !img.complete)
    .map(
      (img) =>
        new Promise<void>((resolve) => {
          img.addEventListener("load", () => resolve(), { once: true });
          img.addEventListener("error", () => resolve(), { once: true });
        }),
    );
  // 読み込みが終わらないときも、いつまでも待たない
  return Promise.race([Promise.all(waits).then(() => undefined), new Promise<void>((resolve) => setTimeout(resolve, 20000))]);
}

async function checkReady(): Promise<void> {
  if (notified || !mounted || !checklistsDone || !root.value) {
    return;
  }
  notified = true;
  await waitForImages(root.value);
  emit("ready");
}

function onChecklistReady(): void {
  pendingChecklists -= 1;
  if (pendingChecklists <= 0) {
    checklistsDone = true;
    void nextTick(checkReady);
  }
}

onMounted(async () => {
  mounted = true;
  await nextTick();
  void checkReady();
});
</script>

<template>
  <div ref="root" class="print-document">
    <section
      v-for="(file, index) in files"
      :key="file.fileId"
      class="print-file"
      :class="{ 'page-break': pageBreak && index > 0 }"
    >
      <p class="print-folder">{{ file.folderName }}</p>
      <h1 class="print-title">{{ file.title }}</h1>
      <div v-for="part in file.parts" :key="part.id" class="print-part">
        <PartContent :part="part" detailed @ready="onChecklistReady" />
      </div>
    </section>
  </div>
</template>
