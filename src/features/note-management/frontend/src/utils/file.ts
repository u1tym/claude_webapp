// ファイルの読み込み（Base64）・大きさの表示・上限の確認。

/** 画像・バイナリ 1 件の大きさの上限（バイト）。サーバの既定（PART_MAX_BYTES）と同じ。 */
export const MAX_FILE_BYTES = 10 * 1024 * 1024;

export const MAX_FILE_MESSAGE = "ファイルは 10 MB までです";

export function formatByteSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** File を Base64 の文字列にする（API の data の形式）。 */
export function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("ファイルを読み込めませんでした"));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : "");
    };
    reader.readAsDataURL(file);
  });
}

/** 選んだファイルの読み込み結果。 */
export interface PickedFile {
  filename: string;
  size: number;
  data: string;
}

/** 大きさの上限を超えるときは、読み込まずに error を返す。 */
export async function pickedFromFile(file: File): Promise<PickedFile | { error: string }> {
  if (file.size > MAX_FILE_BYTES) {
    return { error: MAX_FILE_MESSAGE };
  }
  try {
    return { filename: file.name, size: file.size, data: await readFileAsBase64(file) };
  } catch (e) {
    return { error: e instanceof Error ? e.message : "ファイルを読み込めませんでした" };
  }
}
