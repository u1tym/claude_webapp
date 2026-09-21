// api-design.md の共通のオブジェクトに対応する型。

export interface Settings {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
}

export interface Ingredient {
  id: number;
  name: string;
  kana: string;
  is_system: boolean;
}

export interface Measurement {
  id: number;
  name_bef: string;
  name_aft: string;
  ness_amount: boolean;
  is_system: boolean;
}

export interface RecipeSummary {
  id: number;
  name: string;
  kana: string;
}

export interface RecipeItemBody {
  ingredient_id: number;
  measurement_id: number;
  amount: string;
}

export interface RecipeStepBody {
  description: string;
  items: RecipeItemBody[];
}

export interface RecipeBody {
  name: string;
  kana: string;
  steps: RecipeStepBody[];
}

export interface RecipeItem {
  item_no: number;
  ingredient: Ingredient;
  measurement: Measurement;
  amount: string;
}

export interface RecipeStep {
  step_no: number;
  description: string;
  items: RecipeItem[];
}

export interface RecipeDetail {
  id: number;
  name: string;
  kana: string;
  steps: RecipeStep[];
  created_at: string;
  updated_at: string;
}

export interface MeasurementBody {
  name_bef: string;
  name_aft: string;
  ness_amount: boolean;
}

/** フォーム上の材料の行。未選択は null（保存のときに取り除く）。 */
export interface FormItem {
  key: number;
  ingredientId: number | null;
  measurementId: number | null;
  amount: string;
}

export interface FormStep {
  key: number;
  description: string;
  items: FormItem[];
}

export interface FormState {
  name: string;
  kana: string;
  steps: FormStep[];
}
