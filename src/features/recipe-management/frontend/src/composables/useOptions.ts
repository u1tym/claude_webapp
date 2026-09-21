// 登録・編集の画面で使う、材料と分量名称の選択肢の取得。

import { ref } from "vue";
import { errorMessage, listIngredients, listMeasurements } from "../api";
import type { Ingredient, Measurement } from "../types";

export function useOptions() {
  const ingredients = ref<Ingredient[]>([]);
  const measurements = ref<Measurement[]>([]);
  const loading = ref(true);
  const error = ref("");

  /** 取得できたら true。失敗したときは error に文言を入れる。 */
  async function reload(): Promise<boolean> {
    try {
      const [ing, mea] = await Promise.all([listIngredients(), listMeasurements()]);
      ingredients.value = ing.items;
      measurements.value = mea.items;
      return true;
    } catch (e) {
      error.value = errorMessage(e);
      return false;
    }
  }

  async function load(): Promise<boolean> {
    loading.value = true;
    error.value = "";
    const ok = await reload();
    loading.value = false;
    return ok;
  }

  return { ingredients, measurements, loading, error, load, reload };
}
