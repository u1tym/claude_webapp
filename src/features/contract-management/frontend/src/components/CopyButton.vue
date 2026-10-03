<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { copyText } from "../clipboard";

const props = defineProps<{
  /** コピーする値。関数のときは、押された時点で呼ぶ（パスワードの値を、操作時にだけ取得するため） */
  value: string | (() => string | Promise<string>);
  /** 何をコピーするか（読み上げ用。例: 「ユーザ名をコピー」） */
  label: string;
}>();

const emit = defineEmits<{
  /** 値の取得・コピーに失敗した（AuthError を含む）。画面が処理する */
  error: [error: unknown];
}>();

const copied = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;

async function copy(): Promise<void> {
  try {
    const text = typeof props.value === "function" ? await props.value() : props.value;
    await copyText(text);
    copied.value = true;
    clearTimeout(timer);
    // コピー直後は「コピー済」に変わり、数秒で戻る
    timer = setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch (error) {
    emit("error", error);
  }
}

onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
  <button class="btn-text btn-compact" type="button" :aria-label="label" @click="copy">
    {{ copied ? "コピー済" : "コピー" }}
  </button>
</template>
