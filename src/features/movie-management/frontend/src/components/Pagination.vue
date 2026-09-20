<script setup lang="ts">
import type { Pagination } from "../types";

const props = defineProps<{ pagination: Pagination | null; disabled?: boolean }>();
const emit = defineEmits<{ change: [page: number] }>();
</script>

<template>
  <div v-if="props.pagination && props.pagination.total_pages > 1" class="pager">
    <button
      class="btn-secondary"
      type="button"
      :disabled="disabled || props.pagination.page <= 1"
      @click="emit('change', props.pagination.page - 1)"
    >
      前へ
    </button>
    <span>{{ props.pagination.page }} / {{ props.pagination.total_pages }}</span>
    <button
      class="btn-secondary"
      type="button"
      :disabled="disabled || props.pagination.page >= props.pagination.total_pages"
      @click="emit('change', props.pagination.page + 1)"
    >
      次へ
    </button>
  </div>
</template>
