// パーツの追加・編集の入力（下書き）の状態と、送信する内容の組み立て・検証（api-design.md と同じ規則）。

import type { Marker, Part, PartCreateBody, PartType, PartUpdateBody } from "../types";
import { emptyActionForm, formFromData, serializeActionForm, type ActionForm } from "./actionPlan";
import type { PickedFile } from "./file";
import { cloneMarkers } from "./imageMarkers";
import { percentToScale, scaleToPercent } from "./imageScale";

export const TYPE_OPTIONS: { value: PartType; label: string }[] = [
  { value: "text", label: "テキスト" },
  { value: "md", label: "Markdown" },
  { value: "tex", label: "TeX" },
  { value: "url", label: "URL" },
  { value: "action", label: "行動予定" },
  { value: "checklist", label: "チェックリスト" },
  { value: "jpeg", label: "JPEG" },
  { value: "png", label: "PNG" },
  { value: "binary", label: "バイナリ" },
];

export const SCALE_MESSAGE = "表示倍率は 25〜400 の間で入力してください";

/** 入力の形が同じ種別の組。組の中の種別の変更は、本文を引き継ぐ。 */
export type Group = "text" | "action" | "checklist" | "binary";

export function groupOf(type: PartType): Group {
  if (type === "text" || type === "md" || type === "tex" || type === "url") {
    return "text";
  }
  if (type === "jpeg" || type === "png" || type === "binary") {
    return "binary";
  }
  return type;
}

export const isImageType = (type: PartType): boolean => type === "jpeg" || type === "png";

export interface PartDraft {
  type: PartType;
  text: string;
  action: ActionForm;
  /** 選んだ（差し替える）ファイル */
  picked: PickedFile | null;
  /** 編集のとき、現在のファイル名・大きさ */
  existingFilename: string;
  existingSize: number;
  title: string;
  /** 表示倍率（%）の入力 */
  scalePercent: string;
  markers: Marker[];
}

export function emptyDraft(type: PartType = "text"): PartDraft {
  return {
    type,
    text: "",
    action: emptyActionForm(),
    picked: null,
    existingFilename: "",
    existingSize: 0,
    title: "",
    scalePercent: "100",
    markers: [],
  };
}

export function draftFromPart(part: Part): PartDraft {
  const draft = emptyDraft(part.type);
  const group = groupOf(part.type);
  if (group === "text") {
    draft.text = part.data;
  } else if (group === "action") {
    draft.action = formFromData(part.data);
  } else if (group === "binary") {
    draft.existingFilename = part.filename;
    draft.existingSize = part.byte_size;
    if (isImageType(part.type)) {
      draft.title = part.title;
      draft.scalePercent = String(scaleToPercent(part.image_scale));
      draft.markers = cloneMarkers(part.markers);
    }
  }
  return draft;
}

/** 種別を選び直す。入力の形が違う組へ変えたときは、本文を空にする（同じ組の中では引き継ぐ）。 */
export function changeDraftType(draft: PartDraft, next: PartType): void {
  const before = groupOf(draft.type);
  draft.type = next;
  if (before === groupOf(next)) {
    if (!isImageType(next)) {
      draft.title = "";
      draft.markers = [];
    }
    return;
  }
  draft.text = "";
  draft.action = emptyActionForm();
  draft.picked = null;
  draft.existingFilename = "";
  draft.existingSize = 0;
  draft.title = "";
  draft.scalePercent = "100";
  draft.markers = [];
}

function parseScale(input: string | number): number | null {
  // type="number" の入力欄は、Vue が数値にして渡すことがある
  const text = String(input).trim();
  if (text === "") {
    return null;
  }
  return percentToScale(Number(text));
}

const FILE_REQUIRED = (type: PartType): string =>
  isImageType(type) ? "画像のファイルを選択してください" : "ファイルを選択してください";

type Built<T> = { body: T } | { error: string };

export function buildCreateBody(draft: PartDraft): Built<PartCreateBody> {
  const group = groupOf(draft.type);
  if (group === "text") {
    return { body: { type: draft.type, data: draft.text } };
  }
  if (group === "action") {
    const result = serializeActionForm(draft.action);
    return "error" in result ? { error: result.error } : { body: { type: draft.type, data: result.data } };
  }
  if (group === "checklist") {
    return { body: { type: draft.type } };
  }
  if (draft.picked === null) {
    return { error: FILE_REQUIRED(draft.type) };
  }
  const body: PartCreateBody = { type: draft.type, data: draft.picked.data, filename: draft.picked.filename };
  if (isImageType(draft.type)) {
    const scale = parseScale(draft.scalePercent);
    if (scale === null) {
      return { error: SCALE_MESSAGE };
    }
    body.title = draft.title;
    body.markers = draft.markers;
    body.image_scale = scale;
  }
  return { body };
}

export function buildUpdateBody(part: Part, draft: PartDraft): Built<PartUpdateBody> {
  const body: PartUpdateBody = {};
  const group = groupOf(draft.type);
  const groupChanged = group !== groupOf(part.type);
  if (draft.type !== part.type) {
    body.type = draft.type;
  }
  if (group === "text") {
    if (groupChanged || draft.text !== part.data) {
      body.data = draft.text;
    }
    return { body };
  }
  if (group === "action") {
    const result = serializeActionForm(draft.action);
    if ("error" in result) {
      return { error: result.error };
    }
    body.data = result.data;
    return { body };
  }
  if (group === "checklist") {
    return { body };
  }
  if (draft.picked !== null) {
    body.data = draft.picked.data;
    body.filename = draft.picked.filename;
  } else if (groupChanged) {
    return { error: FILE_REQUIRED(draft.type) };
  }
  if (isImageType(draft.type)) {
    const scale = parseScale(draft.scalePercent);
    if (scale === null) {
      return { error: SCALE_MESSAGE };
    }
    body.title = draft.title;
    body.markers = draft.markers;
    body.image_scale = scale;
  }
  return { body };
}

/**
 * 画像・バイナリの中身の取得先に付ける版。中身を差し替えると、差し替え前の内容が過去世代になり、
 * 最新の世代番号が増える。取得先が変わるので、ブラウザが古い画像を使い続けない。
 */
export function contentVersion(part: Part): number {
  return part.revisions.length > 0 ? part.revisions[0].revision_number : 0;
}
