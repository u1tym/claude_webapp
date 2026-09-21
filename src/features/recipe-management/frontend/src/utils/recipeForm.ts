// レシピの入力フォームの状態の組み立て・検証・送信内容への変換。

import type {
  FormItem,
  FormState,
  FormStep,
  Measurement,
  RecipeBody,
  RecipeDetail,
} from "../types";

let keySeed = 0;

/** v-for の key 用。行の追加・削除で入力欄の状態が入れ替わらないようにする。 */
function nextKey(): number {
  keySeed += 1;
  return keySeed;
}

/** 追加する行の分量名称は、分量名称の先頭のものを選んだ状態にする。 */
export function newItem(measurements: Measurement[]): FormItem {
  const first = measurements[0];
  return { key: nextKey(), ingredientId: null, measurementId: first ? first.id : null, amount: "" };
}

export function newStep(measurements: Measurement[]): FormStep {
  return { key: nextKey(), description: "", items: [newItem(measurements)] };
}

/** 登録の初期状態。手順が 1 件あり、その中に材料の行が 1 件ある。 */
export function emptyForm(measurements: Measurement[]): FormState {
  return { name: "", kana: "", steps: [newStep(measurements)] };
}

/** 編集の初期状態。現在のレシピの内容が入った状態。 */
export function formFromRecipe(recipe: RecipeDetail): FormState {
  return {
    name: recipe.name,
    kana: recipe.kana,
    steps: recipe.steps.map((step) => ({
      key: nextKey(),
      description: step.description,
      items: step.items.map((item) => ({
        key: nextKey(),
        ingredientId: item.ingredient.id,
        measurementId: item.measurement.id,
        amount: item.amount,
      })),
    })),
  };
}

/**
 * 入力を検証する。問題があれば、何番目の手順・材料かがわかる一文を返す。問題がなければ空文字。
 * 材料が未選択の行は、保存のときに取り除くため、検証の対象にしない。
 */
export function validateForm(form: FormState, measurements: Measurement[]): string {
  if (form.name.trim() === "") {
    return "メニュー名を入力してください";
  }
  if (form.kana.trim() === "") {
    return "かなを入力してください";
  }
  for (const [si, step] of form.steps.entries()) {
    if (step.description.trim() === "") {
      return `手順 ${si + 1}: 説明を入力してください`;
    }
    for (const [ii, item] of step.items.entries()) {
      if (item.ingredientId === null) {
        continue;
      }
      const where = `手順 ${si + 1}・材料 ${ii + 1}`;
      const measurement = measurements.find((m) => m.id === item.measurementId);
      if (!measurement) {
        return `${where}: 分量名称を選択してください`;
      }
      if (measurement.ness_amount && item.amount.trim() === "") {
        return `${where}: 数量を入力してください`;
      }
    }
  }
  return "";
}

/** 送信内容に変換する。材料が未選択の行は取り除く。数量なしの分量名称は数量を空にする。 */
export function toBody(form: FormState, measurements: Measurement[]): RecipeBody {
  return {
    name: form.name.trim(),
    kana: form.kana.trim(),
    steps: form.steps.map((step) => ({
      description: step.description.trim(),
      items: step.items.flatMap((item) => {
        if (item.ingredientId === null || item.measurementId === null) {
          return [];
        }
        const measurement = measurements.find((m) => m.id === item.measurementId);
        return [
          {
            ingredient_id: item.ingredientId,
            measurement_id: item.measurementId,
            amount: measurement && !measurement.ness_amount ? "" : item.amount.trim(),
          },
        ];
      }),
    })),
  };
}
