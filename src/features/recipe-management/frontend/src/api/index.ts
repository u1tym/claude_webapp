// api-design.md の全エンドポイントに対応する呼び出し。

import { jsonBody, request, requestVoid } from "./client";
import type {
  Ingredient,
  Measurement,
  MeasurementBody,
  RecipeBody,
  RecipeDetail,
  RecipeSummary,
  Settings,
} from "../types";

export * from "./client";

// ---- 設定 ------------------------------------------------------------

export const getSettings = (): Promise<Settings> => request<Settings>("/settings");

// ---- 材料 ------------------------------------------------------------

export const listIngredients = (): Promise<{ items: Ingredient[] }> => request("/ingredients");

export const createIngredient = (name: string, kana: string): Promise<Ingredient> =>
  request("/ingredients", { method: "POST", body: jsonBody({ name, kana }) });

// ---- 分量名称 ----------------------------------------------------------

export const listMeasurements = (): Promise<{ items: Measurement[] }> => request("/measurements");

export const createMeasurement = (body: MeasurementBody): Promise<Measurement> =>
  request("/measurements", { method: "POST", body: jsonBody(body) });

// ---- レシピ ------------------------------------------------------------

export const listRecipes = (): Promise<{ items: RecipeSummary[] }> => request("/recipes");

export const getRecipe = (id: number): Promise<RecipeDetail> => request(`/recipes/${id}`);

export const createRecipe = (body: RecipeBody): Promise<RecipeDetail> =>
  request("/recipes", { method: "POST", body: jsonBody(body) });

export const updateRecipe = (id: number, body: RecipeBody): Promise<RecipeDetail> =>
  request(`/recipes/${id}`, { method: "PUT", body: jsonBody(body) });

export const deleteRecipe = (id: number): Promise<void> => requestVoid(`/recipes/${id}`, { method: "DELETE" });
