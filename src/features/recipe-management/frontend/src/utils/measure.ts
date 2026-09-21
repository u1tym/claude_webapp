// 分量の表示と、分量名称の選択（接頭語 → 接尾語）の補助。

import type { Measurement } from "../types";

/** 分量の表示。数量ありは「接頭語＋数量＋接尾語」、数量なしは「接頭語＋接尾語」。 */
export function formatAmount(measurement: Measurement, amount: string): string {
  return measurement.ness_amount
    ? `${measurement.name_bef}${amount}${measurement.name_aft}`
    : `${measurement.name_bef}${measurement.name_aft}`;
}

/** 接頭語の選択肢（重複を除く。measurements の並び順のまま）。 */
export function prefixOptions(measurements: Measurement[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const m of measurements) {
    if (!seen.has(m.name_bef)) {
      seen.add(m.name_bef);
      result.push(m.name_bef);
    }
  }
  return result;
}

/** 選んだ接頭語と組になる分量名称（接尾語の選択肢）。 */
export function suffixOptions(measurements: Measurement[], prefix: string): Measurement[] {
  return measurements.filter((m) => m.name_bef === prefix);
}

/** 接頭語を選び直したときに選ぶ分量名称（その接頭語の先頭の組）。 */
export function firstOfPrefix(measurements: Measurement[], prefix: string): Measurement | undefined {
  return suffixOptions(measurements, prefix)[0];
}

/** 空の接頭語・接尾語の表示（選択欄の見出し）。 */
export function emptyLabel(text: string): string {
  return text === "" ? "（空）" : text;
}
