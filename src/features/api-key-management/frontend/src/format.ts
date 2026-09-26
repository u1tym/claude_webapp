function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** ISO 8601 の日時を、ブラウザのローカル時刻の `YYYY-MM-DD HH:mm` にする。 */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** `<input type="datetime-local">` の値（ローカル時刻）を、タイムゾーン付き ISO 8601 にする。 */
export function localInputToIso(value: string): string {
  const d = new Date(value);
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const abs = Math.abs(offset);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:00` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  );
}

export const STATUS_LABELS = {
  active: "有効",
  expired: "期限切れ",
  revoked: "失効済み",
} as const;
