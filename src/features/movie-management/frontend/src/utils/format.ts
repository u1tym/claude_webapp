/** ミリ秒を m:ss（1 時間以上は h:mm:ss）にする。 */
export function formatMs(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const ss = String(s).padStart(2, "0");
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${ss}`;
  }
  return `${m}:${ss}`;
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const pad = (n: number): string => String(n).padStart(2, "0");
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function statusLabel(status: string): string {
  switch (status) {
    case "uploading":
      return "登録中";
    case "error":
      return "エラー";
    default:
      return "再生可能";
  }
}

/** 0〜100 の進捗（再生位置 / 動画の長さ）。 */
export function progressPercent(positionMs: number | null, durationMs: number): number {
  if (positionMs === null || durationMs <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, (positionMs / durationMs) * 100));
}
