// 画像の表示倍率と、マーカーの位置の計算。

export const DEFAULT_IMAGE_SCALE = 1;
export const MIN_IMAGE_SCALE = 0.25;
export const MAX_IMAGE_SCALE = 4;

export function clampImageScale(scale: number): number {
  if (!Number.isFinite(scale)) {
    return DEFAULT_IMAGE_SCALE;
  }
  return Math.min(MAX_IMAGE_SCALE, Math.max(MIN_IMAGE_SCALE, scale));
}

export function scaleToPercent(scale: number): number {
  return Math.round(clampImageScale(scale) * 100);
}

/** 入力された倍率（%）を、倍率にする。範囲（25〜400）の外、または数でないときは null。 */
export function percentToScale(percent: number): number | null {
  if (!Number.isFinite(percent) || percent < MIN_IMAGE_SCALE * 100 || percent > MAX_IMAGE_SCALE * 100) {
    return null;
  }
  return percent / 100;
}

/** 画像の枠（画面の幅を 100% とした枠）の中での、マーカーのピンの位置。 */
export function markerPinPosition(marker: { x: number; y: number }, scale: number): { left: string; top: string } {
  // 横: 画像の幅は 100% 基準のため倍率を掛ける。縦: 枠の高さは倍率を含むため、そのまま
  return { left: `${marker.x * clampImageScale(scale) * 100}%`, top: `${marker.y * 100}%` };
}

/** ポインタの位置（画面の座標）から、マーカーの位置（0〜1）を求める。 */
export function pointerToMarkerPosition(
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
  scale: number,
): { x: number; y: number } {
  const clamped = clampImageScale(scale);
  if (rect.width === 0 || rect.height === 0) {
    return { x: 0, y: 0 };
  }
  return {
    x: Math.min(1, Math.max(0, (clientX - rect.left) / rect.width / clamped)),
    y: Math.min(1, Math.max(0, (clientY - rect.top) / rect.height)),
  };
}
