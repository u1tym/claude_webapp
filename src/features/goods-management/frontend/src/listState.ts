import { reactive } from "vue";
import type { Artist, GoodsListItem, Media } from "./api";

// SCR-001（商品一覧）の絞り込み状態。モジュール単位の単一インスタンスとして保持し、
// SCR-002（商品登録・編集）へ遷移して戻ってきても、選択済みの条件が失われないようにする。
export const listState = reactive({
  selectedPersonId: null as number | null,
  selectedArtistId: null as number | "all" | null,
  selectedMediaId: null as number | "all" | null,
  relatedArtists: [] as Artist[],
  relatedMediaList: [] as Media[],
  goodsList: [] as GoodsListItem[],
  titleFilter: "",
});
