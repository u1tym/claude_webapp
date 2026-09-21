// 行動予定の入力の状態・検証・保存用の文字列（api-design.md「行動予定の本文」と同じ規則）。

import type { ActionLeg, ActionPlan, ActionPoint } from "../types";

export interface PointForm {
  place: string;
  /** 2 番目以降の地点の時刻の入力方法。single は単一時刻、split は到着・出発 */
  mode: "single" | "split";
  time: string;
  arrive: string;
  depart: string;
}

export interface ActionForm {
  points: PointForm[];
  /** 隣り合う地点の間の経由メモ。常に points.length - 1 件 */
  legs: ActionLeg[];
}

export const NO_CONTENT_MESSAGE = "地点または経由メモのどれかを入力してください";

function emptyPoint(): PointForm {
  return { place: "", mode: "single", time: "", arrive: "", depart: "" };
}

export function emptyActionForm(): ActionForm {
  return { points: [emptyPoint()], legs: [] };
}

export function addPoint(form: ActionForm): void {
  form.points.push(emptyPoint());
  form.legs.push({ memo: "", note: "" });
}

/** 2 番目以降の地点を取り除く。その地点の手前の経由メモも取り除く。 */
export function removePoint(form: ActionForm, index: number): void {
  if (index < 1 || index >= form.points.length) {
    return;
  }
  form.points.splice(index, 1);
  form.legs.splice(index - 1, 1);
}

/** 保存済みの本文を、表示用に読む。読めないときは null。 */
export function parseActionPlan(data: string): ActionPlan | null {
  try {
    const value = JSON.parse(data) as unknown;
    if (typeof value !== "object" || value === null) {
      return null;
    }
    const obj = value as { points?: unknown; legs?: unknown };
    if (!Array.isArray(obj.points) || obj.points.length === 0) {
      return null;
    }
    const legs = Array.isArray(obj.legs) ? (obj.legs as ActionLeg[]) : [];
    return {
      points: (obj.points as ActionPoint[]).map((p) => ({ ...p, place: p.place ?? "" })),
      legs: legs.map((l) => ({ memo: l.memo ?? "", note: l.note ?? "" })),
    };
  } catch {
    return null;
  }
}

export function formFromData(data: string): ActionForm {
  const plan = parseActionPlan(data);
  if (plan === null) {
    return emptyActionForm();
  }
  const points: PointForm[] = plan.points.map((p, index) => ({
    place: p.place,
    mode: index > 0 && (p.arrive || p.depart) ? "split" : "single",
    time: p.time ?? "",
    arrive: p.arrive ?? "",
    depart: p.depart ?? "",
  }));
  const legs = points.slice(1).map((_, i) => plan.legs[i] ?? { memo: "", note: "" });
  return { points, legs };
}

const trimEnd = (value: string): string => value.replace(/\s+$/u, "");

interface CleanPoint {
  place: string;
  time: string;
  arrive: string;
  depart: string;
}

function isEmptyPoint(point: CleanPoint): boolean {
  return point.place === "" && point.time === "" && point.arrive === "" && point.depart === "";
}

/** 入力を検証し、保存する本文（JSON の文字列）にする。問題があれば error を返す。 */
export function serializeActionForm(form: ActionForm): { data: string } | { error: string } {
  const points: CleanPoint[] = form.points.map((p, index) => {
    const single = index === 0 || p.mode === "single";
    return {
      place: trimEnd(p.place),
      time: single ? trimEnd(p.time) : "",
      arrive: single ? "" : trimEnd(p.arrive),
      depart: single ? "" : trimEnd(p.depart),
    };
  });
  const legs = form.legs.map((l) => ({ memo: trimEnd(l.memo), note: trimEnd(l.note) }));
  // 2 番目以降で、すべて空の地点が末尾に続くときは、取り除く（その地点への経由メモも）
  while (points.length > 1 && isEmptyPoint(points[points.length - 1])) {
    points.pop();
    legs.pop();
  }
  const hasContent = points.some((p) => !isEmptyPoint(p)) || legs.some((l) => l.memo !== "" || l.note !== "");
  if (!hasContent) {
    return { error: NO_CONTENT_MESSAGE };
  }
  const out = {
    points: points.map((p) => ({
      place: p.place,
      ...(p.time ? { time: p.time } : {}),
      ...(p.arrive ? { arrive: p.arrive } : {}),
      ...(p.depart ? { depart: p.depart } : {}),
    })),
    legs,
  };
  return { data: JSON.stringify(out) };
}

/** 表示用: 地点の時刻（単一時刻、または「到着〜出発」）。 */
export function pointTimeText(point: ActionPoint): string {
  if (point.arrive || point.depart) {
    return `${point.arrive ?? ""}〜${point.depart ?? ""}`;
  }
  return point.time ?? "";
}
