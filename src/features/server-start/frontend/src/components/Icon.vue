<script setup lang="ts">
// Inlined from /icons (source: https://icooon-mono.com/). Kept local to this
// feature per rules/15-ui-style.md (no cross-feature imports of components).
const PATHS: Record<string, string> = {
  back: '<path d="M292.497,168.968c-21.134,0-40.287,0-57.542,0V65.394L0,255.995l234.955,190.61V334.395c7.132,0,14.331,0,21.578,0c95.305,0,227.772-2.396,237.359,100.701C541.847,322.408,501.086,168.968,292.497,168.968z"/>',
  check:
    '<path d="M469.402,35.492C334.09,110.664,197.114,324.5,197.114,324.5L73.509,184.176L0,254.336l178.732,222.172l65.15-2.504C327.414,223.414,512,55.539,512,55.539L469.402,35.492z"/>',
  close:
    '<polygon points="512,89.75 422.256,0.005 256.004,166.256 89.754,0.005 0,89.75 166.255,256 0,422.25 89.754,511.995 256.004,345.745 422.26,511.995 512,422.25 345.744,256"/>',
};

defineProps<{ name: keyof typeof PATHS }>();
</script>

<template>
  <svg class="icon" viewBox="0 0 512 512" fill="currentColor" aria-hidden="true" focusable="false" v-html="PATHS[name]"></svg>
</template>
