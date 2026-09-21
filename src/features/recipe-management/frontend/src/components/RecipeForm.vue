<script setup lang="ts">
import { computed, ref } from "vue";
import type { FormItem, FormState, Ingredient, Measurement, RecipeBody } from "../types";
import { emptyLabel, firstOfPrefix, prefixOptions, suffixOptions } from "../utils/measure";
import { newItem, newStep, toBody, validateForm } from "../utils/recipeForm";
import Icon from "./Icon.vue";
import IngredientDialog from "./IngredientDialog.vue";
import MeasurementDialog from "./MeasurementDialog.vue";

// 登録と編集で共通の入力フォーム。本体だけスクロールし、操作（保存・キャンセル）は下部に固定する。
const props = defineProps<{
  ingredients: Ingredient[];
  measurements: Measurement[];
  saving: boolean;
  /** 保存の失敗など、親が示すエラー（フォームの先頭に表示する） */
  error: string;
  /** 追加ダイアログで追加した後に、材料・分量名称の選択肢を取得し直す */
  reloadOptions: () => Promise<unknown>;
}>();

const emit = defineEmits<{ submit: [body: RecipeBody]; cancel: [] }>();

const form = defineModel<FormState>({ required: true });

const formError = ref("");
const ingredientTarget = ref<FormItem | null>(null);
const measurementTarget = ref<FormItem | null>(null);

const prefixes = computed(() => prefixOptions(props.measurements));
const shownError = computed(() => formError.value || props.error);

function measurementOf(item: FormItem): Measurement | undefined {
  return props.measurements.find((m) => m.id === item.measurementId);
}

function isNumberless(item: FormItem): boolean {
  const m = measurementOf(item);
  return m !== undefined && !m.ness_amount;
}

/** 分量名称を選んだとき。数量なしの分量名称では、数量を空にする。 */
function setMeasurement(item: FormItem, measurement: Measurement | undefined): void {
  item.measurementId = measurement ? measurement.id : null;
  if (measurement && !measurement.ness_amount) {
    item.amount = "";
  }
}

function onPrefixChange(item: FormItem, event: Event): void {
  const prefix = (event.target as HTMLSelectElement).value;
  setMeasurement(item, firstOfPrefix(props.measurements, prefix));
}

function onSuffixChange(item: FormItem, event: Event): void {
  const id = Number((event.target as HTMLSelectElement).value);
  setMeasurement(item, props.measurements.find((m) => m.id === id));
}

function prefixOf(item: FormItem): string {
  return measurementOf(item)?.name_bef ?? "";
}

function addStep(): void {
  form.value.steps.push(newStep(props.measurements));
}

function removeStep(index: number): void {
  if (form.value.steps.length > 1) {
    form.value.steps.splice(index, 1);
  }
}

function addItem(stepIndex: number): void {
  form.value.steps[stepIndex].items.push(newItem(props.measurements));
}

function removeItem(stepIndex: number, itemIndex: number): void {
  form.value.steps[stepIndex].items.splice(itemIndex, 1);
}

async function onIngredientSaved(ingredient: Ingredient): Promise<void> {
  const target = ingredientTarget.value;
  await props.reloadOptions();
  if (target) {
    target.ingredientId = ingredient.id;
  }
  ingredientTarget.value = null;
}

async function onMeasurementSaved(measurement: Measurement): Promise<void> {
  const target = measurementTarget.value;
  await props.reloadOptions();
  if (target) {
    target.measurementId = measurement.id;
    target.amount = measurement.ness_amount ? "1" : "";
  }
  measurementTarget.value = null;
}

function submit(): void {
  formError.value = validateForm(form.value, props.measurements);
  if (formError.value) {
    return;
  }
  emit("submit", toBody(form.value, props.measurements));
}
</script>

<template>
  <form class="recipe-form" novalidate @submit.prevent="submit">
    <p v-if="shownError" class="msg-error" role="alert">{{ shownError }}</p>

    <div class="page-body form-scroll">
      <fieldset class="form-panel" :disabled="saving">
        <h3>メニュー</h3>
        <div class="field">
          <label for="recipe-name">メニュー名</label>
          <input id="recipe-name" v-model="form.name" type="text" />
        </div>
        <div class="field">
          <label for="recipe-kana">かな</label>
          <input id="recipe-kana" v-model="form.kana" type="text" />
        </div>
      </fieldset>

      <fieldset v-for="(step, si) in form.steps" :key="step.key" class="form-panel" :disabled="saving">
        <div class="panel-head">
          <h3>手順 {{ si + 1 }}</h3>
          <button
            class="btn-text danger"
            type="button"
            aria-label="手順の削除"
            :disabled="form.steps.length <= 1"
            @click="removeStep(si)"
          >
            <Icon name="delete" />
          </button>
        </div>

        <div v-for="(item, ii) in step.items" :key="item.key" class="item-row">
          <div class="panel-head">
            <span class="label">材料 {{ ii + 1 }}</span>
            <button class="btn-text danger" type="button" aria-label="材料の行の削除" @click="removeItem(si, ii)">
              <Icon name="delete" />
            </button>
          </div>

          <div class="item-fields">
            <div class="inline">
              <select v-model="item.ingredientId" aria-label="材料">
                <option v-if="ingredients.length === 0" :value="null" disabled>データがありません</option>
                <option v-else :value="null">-- 選択してください --</option>
                <option v-for="ing in ingredients" :key="ing.id" :value="ing.id">
                  {{ ing.name }}（{{ ing.kana }}）{{ ing.is_system ? "" : "（独自）" }}
                </option>
              </select>
              <button class="btn-secondary" type="button" aria-label="材料の新規登録" @click="ingredientTarget = item">
                <Icon name="plus" />
              </button>
            </div>

            <div class="inline amount">
              <select :value="prefixOf(item)" aria-label="接頭語" @change="onPrefixChange(item, $event)">
                <option v-if="measurements.length === 0" value="" disabled>データがありません</option>
                <option v-for="prefix in prefixes" :key="prefix" :value="prefix">{{ emptyLabel(prefix) }}</option>
              </select>
              <input
                v-model="item.amount"
                type="text"
                inputmode="decimal"
                class="amount-input"
                aria-label="数量"
                :disabled="isNumberless(item)"
              />
              <select
                :value="item.measurementId ?? ''"
                aria-label="接尾語"
                @change="onSuffixChange(item, $event)"
              >
                <option v-if="measurements.length === 0" value="" disabled>データがありません</option>
                <option v-for="m in suffixOptions(measurements, prefixOf(item))" :key="m.id" :value="m.id">
                  {{ emptyLabel(m.name_aft) }}
                </option>
              </select>
              <button class="btn-secondary" type="button" aria-label="分量名称の新規登録" @click="measurementTarget = item">
                <Icon name="plus" />
              </button>
            </div>
          </div>
        </div>

        <div>
          <button class="btn-secondary" type="button" @click="addItem(si)">材料を追加</button>
        </div>

        <div class="field">
          <label :for="`step-desc-${step.key}`">手順説明</label>
          <textarea :id="`step-desc-${step.key}`" v-model="step.description" rows="3"></textarea>
        </div>
      </fieldset>

      <div>
        <button class="btn-secondary" type="button" :disabled="saving" @click="addStep">手順を追加</button>
      </div>
    </div>

    <div class="actions actions-end">
      <button class="btn-secondary" type="button" aria-label="キャンセル" :disabled="saving" @click="emit('cancel')">
        <Icon name="close" />
      </button>
      <button class="btn-primary" type="submit" aria-label="保存" :disabled="saving">
        <Icon name="check" />
      </button>
    </div>

    <!-- ダイアログ自身が form のため、入れ子を避けて body へ出す（submit が外側のフォームへ伝わらないように） -->
    <Teleport to="body">
      <IngredientDialog v-if="ingredientTarget" @saved="onIngredientSaved" @cancel="ingredientTarget = null" />
      <MeasurementDialog v-if="measurementTarget" @saved="onMeasurementSaved" @cancel="measurementTarget = null" />
    </Teleport>
  </form>
</template>
