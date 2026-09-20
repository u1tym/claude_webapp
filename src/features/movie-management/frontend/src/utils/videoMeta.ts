import type { VideoMetaForm } from "../types";

export function emptyMeta(): VideoMetaForm {
  return {
    title: "",
    description: "",
    seriesId: null,
    newSeriesTitle: "",
    episodeNumber: null,
    episodeTitle: "",
    sortOrder: 0,
    genreIds: [],
  };
}

/** 入力の検証。問題があれば、画面に出す一文を返す。 */
export function validateMeta(meta: VideoMetaForm): string | null {
  const title = meta.title.trim();
  if (!title) {
    return "タイトルを入力してください";
  }
  if (title.length > 500) {
    return "タイトルは 500 文字以内で入力してください";
  }
  if (meta.newSeriesTitle.trim().length > 500) {
    return "作品のタイトルは 500 文字以内で入力してください";
  }
  if (meta.episodeTitle.length > 500) {
    return "話タイトルは 500 文字以内で入力してください";
  }
  if (meta.episodeNumber !== null && (!Number.isInteger(meta.episodeNumber) || meta.episodeNumber < 1)) {
    return "話数は 1 以上の整数で入力してください";
  }
  if (!Number.isInteger(meta.sortOrder) || meta.sortOrder < 0) {
    return "作品内順序は 0 以上の整数で入力してください";
  }
  return null;
}

/** 空欄を null にそろえる（number 入力が空のとき Vue は "" を入れることがある）。 */
export function normalizeEpisodeNumber(value: number | string | null): number | null {
  if (value === null || value === "") {
    return null;
  }
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}
