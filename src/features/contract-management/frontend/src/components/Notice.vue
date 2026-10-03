<script setup lang="ts">
// 成功・エラーのメッセージ（対象領域の先頭に出す。rules/15-ui-style.md「状態の見た目」）
defineProps<{ kind: "success" | "error"; message: string }>();
</script>

<template>
  <p v-if="message" :class="kind === 'error' ? 'msg-error' : 'msg-success'" :role="kind === 'error' ? 'alert' : 'status'">
    {{ message }}
  </p>
</template>
