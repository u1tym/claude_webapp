import { completeUpload, uploadChunk } from "./index";

export const CHUNK_BYTES = 4 * 1024 * 1024; // 約 4 MB

/**
 * 動画ファイルを約 4 MB ごとに分け、順番に 1 つずつ送り、最後に完了を通知する。
 * 動画情報（登録中）は、呼び出し側があらかじめ作っておく。
 */
export async function uploadVideoFile(
  videoId: number,
  file: File,
  durationMs: number,
  onProgress?: (uploaded: number, total: number) => void,
): Promise<void> {
  const total = Math.max(1, Math.ceil(file.size / CHUNK_BYTES));
  for (let index = 0; index < total; index += 1) {
    const blob = file.slice(index * CHUNK_BYTES, Math.min((index + 1) * CHUNK_BYTES, file.size));
    // 時間の範囲は、バイト位置に比例した目安（再生自体はバイト位置で行う）
    const start = Math.min(Math.floor((index * durationMs) / total), durationMs - 1);
    const end = index === total - 1 ? durationMs : Math.max(start + 1, Math.floor(((index + 1) * durationMs) / total));
    await uploadChunk(videoId, index, start, end, blob);
    onProgress?.(index + 1, total);
  }
  await completeUpload(videoId, durationMs, total);
}
