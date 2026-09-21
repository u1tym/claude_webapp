<script setup lang="ts">
import { computed } from "vue";
import { parseActionPlan, pointTimeText } from "../utils/actionPlan";

// 行動予定の表示。地点（時刻・場所）と、地点の間の経由メモ（補足は改行を保つ）を、順に並べる。
const props = defineProps<{ data: string }>();

const plan = computed(() => parseActionPlan(props.data));
</script>

<template>
  <div v-if="plan" class="action-view">
    <template v-for="(point, index) in plan.points" :key="index">
      <div class="action-point">
        <span class="action-time">{{ pointTimeText(point) }}</span>
        <span class="action-place">{{ point.place }}</span>
      </div>
      <div v-if="index < plan.points.length - 1 && (plan.legs[index]?.memo || plan.legs[index]?.note)" class="action-leg">
        <span v-if="plan.legs[index].memo" class="action-memo">{{ plan.legs[index].memo }}</span>
        <span v-if="plan.legs[index].note" class="action-note">{{ plan.legs[index].note }}</span>
      </div>
    </template>
  </div>
  <p v-else class="muted">行動予定を表示できません</p>
</template>
