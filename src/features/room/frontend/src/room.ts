/** 機器のキー（API の `device`）。 */
export type DeviceKey =
  | "ceiling_light"
  | "indirect_light"
  | "indoor_speaker"
  | "bedside_speaker"
  | "front_door";

/** パーツのクリックで切り替えられる機器（電灯は未実装、電池残量は表示のみ）。 */
export type OperableDeviceKey = "indirect_light" | "indoor_speaker" | "bedside_speaker" | "front_door";

export type OnOff = "on" | "off";
export type LockState = "locked" | "unlocked";

/** API の `device_state`。status が error のとき state は null（状態を推測しない）。 */
export type DeviceState = {
  status: "ok" | "error";
  state: OnOff | LockState | null;
  /** 玄関ドアだけが持つ。0〜100。取得できなければ null */
  battery?: number | null;
  /** 電灯だけが持つ。常に false（未実装） */
  implemented?: boolean;
};

export type Devices = Record<DeviceKey, DeviceState>;

export const DEVICE_LABELS: Record<DeviceKey, string> = {
  ceiling_light: "電灯",
  indirect_light: "間接照明",
  indoor_speaker: "屋内スピーカー",
  bedside_speaker: "枕元スピーカー",
  front_door: "玄関ドア",
};

const STATE_TEXT: Record<OnOff | LockState, string> = {
  on: "ON",
  off: "OFF",
  locked: "施錠中",
  unlocked: "開錠中",
};

/** 玄関ドアの操作の文言（確認ダイアログや読み上げで使う）。 */
export const DOOR_ACTION_TEXT: Record<LockState, string> = {
  locked: "施錠",
  unlocked: "開錠",
};

/** 状態の文言。取得できなかった機器は「取得できません」。 */
export function stateText(device: DeviceState): string {
  if (device.status !== "ok" || device.state === null) {
    return "取得できません";
  }
  return STATE_TEXT[device.state];
}

/** 切り替えられる機器か。 */
export function isOperable(key: DeviceKey): key is OperableDeviceKey {
  return key !== "ceiling_light";
}

/** 押したときに目標になる状態。取得できていないときは null。 */
export function nextState(key: OperableDeviceKey, device: DeviceState): OnOff | LockState | null {
  if (device.status !== "ok" || device.state === null) {
    return null;
  }
  if (key === "front_door") {
    return device.state === "locked" ? "unlocked" : "locked";
  }
  return device.state === "on" ? "off" : "on";
}

/** スクリーンリーダー向けの説明。機器名、現在の状態、押したときの結果を示す。 */
export function ariaLabelFor(key: DeviceKey, device: DeviceState): string {
  const name = DEVICE_LABELS[key];
  if (key === "ceiling_light") {
    return `${name} OFF（未実装）`;
  }
  const next = nextState(key as OperableDeviceKey, device);
  if (next === null) {
    return `${name} 取得できません`;
  }
  const current = stateText(device);
  if (key === "front_door") {
    // 玄関ドアは、押すと確認ダイアログを開く（すぐには切り替えない）
    return `${name} ${current}。押すと${DOOR_ACTION_TEXT[next as LockState]}の確認を開きます`;
  }
  return `${name} ${current}。押すと ${STATE_TEXT[next]} にします`;
}

/** 電池残量の文言。取得できなければ「不明」。 */
export function batteryText(battery: number | null | undefined): string {
  return typeof battery === "number" ? `${battery}%` : "不明";
}

/** 取得日時の表示。API は日本標準時のオフセット付きで返すため、文字列のまま「年月日 時分秒」にする。 */
export function formatFetchedAt(iso: string): string {
  return iso.slice(0, 19).replace("T", " ");
}

/** 玄関ドアの確認ダイアログの文面。 */
export function doorConfirmMessage(target: LockState): string {
  return `玄関ドアを${DOOR_ACTION_TEXT[target]}します。よろしいですか?`;
}

/** 開錠のときだけ添える一文。 */
export const DOOR_UNLOCK_NOTE = "開錠すると、玄関のドアが開けられる状態になります。";

/** 切替が成功したときのステータスの一文。 */
export function switchSuccessMessage(key: DeviceKey, target: OnOff | LockState): string {
  if (key === "front_door") {
    return `玄関ドアを${DOOR_ACTION_TEXT[target as LockState]}しました。`;
  }
  return `${DEVICE_LABELS[key]}を ${STATE_TEXT[target]} にしました。`;
}

/** 一括切替のキー（API の `scene`）。 */
export type SceneKey =
  | "indoor_speaker"
  | "bedside_speaker"
  | "ceiling_light"
  | "indirect_light"
  | "out";

/** 一括切替の機器ごとの結果。skipped は電灯（未実装のため指示しない）。 */
export type SceneOutcome = {
  device: DeviceKey;
  target: OnOff;
  outcome: "success" | "failure" | "skipped";
};

/** 一括切替ボタン（表示の順）。ボタンは機能の区別にアイコンが使えないため、文字ラベルを持つ。 */
export const SCENES: { key: SceneKey; label: string }[] = [
  { key: "indoor_speaker", label: "屋内スピーカー選択" },
  { key: "bedside_speaker", label: "枕元スピーカー選択" },
  { key: "ceiling_light", label: "電灯選択" },
  { key: "indirect_light", label: "間接照明選択" },
  { key: "out", label: "お出かけ" },
];

export function sceneLabel(key: SceneKey): string {
  return SCENES.find((scene) => scene.key === key)?.label ?? key;
}

function names(results: SceneOutcome[], outcome: SceneOutcome["outcome"]): string {
  return results
    .filter((r) => r.outcome === outcome)
    .map((r) => DEVICE_LABELS[r.device])
    .join("、");
}

/** 一括切替の結果のステータス。失敗があるときは、成功した機器と失敗した機器の名称を示す。 */
export function sceneStatus(
  scene: SceneKey,
  outcome: "success" | "partial" | "failure",
  results: SceneOutcome[],
): { kind: "success" | "error"; text: string } {
  if (outcome === "partial") {
    return {
      kind: "error",
      text: `一部の機器の切り替えに失敗しました。成功: ${names(results, "success")}／失敗: ${names(results, "failure")}`,
    };
  }
  if (outcome === "failure") {
    return { kind: "error", text: `切り替えに失敗しました。失敗: ${names(results, "failure")}` };
  }
  // 電灯を ON にする指示は、未実装のため行わない。そのことを添える
  const ceilingSkippedOn = results.some(
    (r) => r.device === "ceiling_light" && r.outcome === "skipped" && r.target === "on",
  );
  const note = ceilingSkippedOn ? "（電灯は未実装のため変更していません）" : "";
  return { kind: "success", text: `${sceneLabel(scene)}を実行しました。${note}` };
}

/** 実行条件（API の `condition`）。 */
export type Condition = "daily" | "weekdays" | "holiday";

/** 最終実行の結果。 */
export type RunResult = "success" | "partial" | "failure";

/** API の定期実行 1 件。weekdays は 1〜7（1 = 月曜）。last_run は未実行なら null。 */
export type ScheduleItem = {
  id: number;
  condition: Condition;
  weekdays: number[];
  run_time: string;
  scene: SceneKey;
  is_enabled: boolean;
  last_run: { at: string; result: RunResult; failed_devices: DeviceKey[] } | null;
};

const WEEKDAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"];

/** 実行条件の表示。毎日、選んだ曜日（月曜から順に「月・水・金」）、祝日。 */
export function conditionText(item: Pick<ScheduleItem, "condition" | "weekdays">): string {
  if (item.condition === "daily") {
    return "毎日";
  }
  if (item.condition === "holiday") {
    return "祝日";
  }
  return [...item.weekdays]
    .sort((a, b) => a - b)
    .map((day) => WEEKDAY_NAMES[day - 1] ?? "")
    .join("・");
}

/** 結果の表示。色だけでなく、記号と文言で区別する。 */
export const RUN_RESULT_TEXT: Record<RunResult, string> = {
  success: "✓ 成功",
  partial: "△ 一部失敗",
  failure: "✕ 失敗",
};

/** 最終実行の日時（年月日 時分）。API は日本標準時のオフセット付きで返すため、文字列のまま整える。 */
export function formatLastRunAt(iso: string): string {
  return iso.slice(0, 16).replace("T", " ");
}

/** 一覧の並び: 時刻の昇順、同じ時刻なら一括切替の名称順。 */
export function sortSchedules(items: ScheduleItem[]): ScheduleItem[] {
  return [...items].sort(
    (a, b) =>
      a.run_time.localeCompare(b.run_time) ||
      sceneLabel(a.scene).localeCompare(sceneLabel(b.scene), "ja") ||
      a.id - b.id,
  );
}

/** 定期実行入力フォームの値。condition / scene の空文字は未選択。time は `HH:MM`。 */
export type ScheduleForm = {
  condition: "" | Condition;
  weekdays: number[];
  time: string;
  scene: "" | SceneKey;
  enabled: boolean;
};

/** 曜日のチップ（表示の順。値は ISO 8601 の曜日: 1 = 月曜 … 7 = 日曜）。 */
export const WEEKDAY_CHIPS: { value: number; label: string }[] = WEEKDAY_NAMES.map(
  (label, index) => ({ value: index + 1, label }),
);

/** 実行条件の選択肢。 */
export const CONDITION_OPTIONS: { value: Condition; label: string }[] = [
  { value: "daily", label: "毎日" },
  { value: "weekdays", label: "曜日の指定" },
  { value: "holiday", label: "祝日の指定" },
];

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

/** 送信前の検証。問題があれば、最初の 1 件を一文で返す。問題がなければ null。 */
export function validateScheduleForm(form: ScheduleForm): string | null {
  if (form.condition === "") {
    return "実行条件を選択してください。";
  }
  if (form.condition === "weekdays" && form.weekdays.length === 0) {
    return "曜日を 1 つ以上選択してください。";
  }
  if (!TIME_PATTERN.test(form.time)) {
    return "時刻を HH:MM の形式で入力してください。";
  }
  if (form.scene === "") {
    return "一括切替を選択してください。";
  }
  return null;
}

/** API へ送る本文。曜日は、実行条件が「曜日の指定」のときだけ付ける。 */
export function toScheduleBody(form: ScheduleForm): ScheduleInput {
  return {
    condition: form.condition as Condition,
    weekdays: form.condition === "weekdays" ? [...form.weekdays].sort((a, b) => a - b) : [],
    run_time: form.time,
    scene: form.scene as SceneKey,
    is_enabled: form.enabled,
  };
}

/** 登録・変更の要求本文。 */
export type ScheduleInput = {
  condition: Condition;
  weekdays: number[];
  run_time: string;
  scene: SceneKey;
  is_enabled: boolean;
};

/** 既存の定期実行から、入力フォームの初期値を作る。 */
export function formFromItem(item: ScheduleItem | null): ScheduleForm {
  if (item === null) {
    return { condition: "", weekdays: [], time: "", scene: "", enabled: true };
  }
  return {
    condition: item.condition,
    weekdays: [...item.weekdays],
    time: item.run_time,
    scene: item.scene,
    enabled: item.is_enabled,
  };
}
