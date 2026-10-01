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
export type Condition = "daily" | "weekdays";

/** 祝日の扱い（API の `holiday_mode`）。none = 指定した曜日のみ、include = 祝日も実行、exclude = 祝日は実行しない。 */
export type HolidayMode = "none" | "include" | "exclude";

/** 実行日の取り方（API の `day_shift`）。same = 当日、before = の前の日、after = の次の日。 */
export type DayShift = "same" | "before" | "after";

/** 個別切替の機器（API の `device`）。玄関ドアは含めない。 */
export type TimerDeviceKey = "ceiling_light" | "indirect_light" | "indoor_speaker" | "bedside_speaker";

/** 最終実行の結果。 */
export type RunResult = "success" | "partial" | "failure";

/**
 * API の定期実行 1 件。weekdays は 1〜7（1 = 月曜）。last_run は未実行なら null。
 * 実行内容は、一括切替（scene）か、機器の個別切替（device + state）のどちらか一方。
 */
export type ScheduleItem = {
  id: number;
  condition: Condition;
  weekdays: number[];
  holiday_mode: HolidayMode;
  day_shift: DayShift;
  run_time: string;
  scene: SceneKey | null;
  device: TimerDeviceKey | null;
  state: OnOff | null;
  is_enabled: boolean;
  last_run: { at: string; result: RunResult; failed_devices: DeviceKey[] } | null;
};

const WEEKDAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"];

/**
 * 実行条件の表示。毎日、または、選んだ曜日（月曜から順に「月・水・金」）に、祝日の扱いと実行日の取り方を続ける。
 * 祝日も実行 → 曜日の後ろに「・祝日」、祝日は実行しない → 「（祝日を除く）」。
 * の前の日 → 末尾に「の前の日」、の次の日 → 「の次の日」。指定した曜日のみ・当日は何も付けない。
 */
export function conditionText(
  item: Pick<ScheduleItem, "condition" | "weekdays"> &
    Partial<Pick<ScheduleItem, "holiday_mode" | "day_shift">>,
): string {
  if (item.condition === "daily") {
    return "毎日";
  }
  let text = [...item.weekdays]
    .sort((a, b) => a - b)
    .map((day) => WEEKDAY_NAMES[day - 1] ?? "")
    .join("・");
  if (item.holiday_mode === "include") {
    text += "・祝日";
  } else if (item.holiday_mode === "exclude") {
    text += "（祝日を除く）";
  }
  if (item.day_shift === "before") {
    text += "の前の日";
  } else if (item.day_shift === "after") {
    text += "の次の日";
  }
  return text;
}

/**
 * 実行内容の表示。一括切替はその名称、機器の個別切替は「間接照明を ON」のように機器名と状態。
 * 電灯は未実装のため「（未実装）」を添える。
 */
export function actionText(
  item: Pick<ScheduleItem, "scene" | "device" | "state">,
): string {
  if (item.device && item.state) {
    const note = item.device === "ceiling_light" ? "（未実装）" : "";
    return `${DEVICE_LABELS[item.device]}を ${item.state === "on" ? "ON" : "OFF"}${note}`;
  }
  return item.scene ? sceneLabel(item.scene) : "";
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

/** 一覧の並び: 時刻の昇順、同じ時刻なら実行内容の名称順。 */
export function sortSchedules(items: ScheduleItem[]): ScheduleItem[] {
  return [...items].sort(
    (a, b) =>
      a.run_time.localeCompare(b.run_time) ||
      actionText(a).localeCompare(actionText(b), "ja") ||
      a.id - b.id,
  );
}

/** 実行内容の種類。scene = 一括切替、device = 機器の個別切替。空文字は未選択。 */
export type ActionType = "" | "scene" | "device";

/**
 * 定期実行入力フォームの値。空文字は未選択。time は `HH:MM`。
 * holidayMode / dayShift は、実行条件が「曜日の指定」のときだけ意味を持つ。
 * scene は actionType が scene のとき、device と state は actionType が device のときだけ意味を持つ。
 */
export type ScheduleForm = {
  condition: "" | Condition;
  weekdays: number[];
  holidayMode: HolidayMode;
  dayShift: DayShift;
  time: string;
  actionType: ActionType;
  scene: "" | SceneKey;
  device: "" | TimerDeviceKey;
  state: "" | OnOff;
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
];

/** 祝日の扱いの選択肢（既定は「指定した曜日のみ」）。 */
export const HOLIDAY_MODE_OPTIONS: { value: HolidayMode; label: string }[] = [
  { value: "none", label: "指定した曜日のみ" },
  { value: "include", label: "祝日も実行" },
  { value: "exclude", label: "祝日は実行しない" },
];

/** 実行日の取り方の選択肢（既定は「当日」）。 */
export const DAY_SHIFT_OPTIONS: { value: DayShift; label: string }[] = [
  { value: "same", label: "当日" },
  { value: "before", label: "の前の日" },
  { value: "after", label: "の次の日" },
];

/** 実行内容の種類の選択肢。 */
export const ACTION_TYPE_OPTIONS: { value: "scene" | "device"; label: string }[] = [
  { value: "scene", label: "一括切替" },
  { value: "device", label: "機器の個別切替" },
];

/** 個別切替の機器の選択肢（玄関ドアは含めない）。電灯は未実装。 */
export const TIMER_DEVICES: { key: TimerDeviceKey; label: string }[] = [
  { key: "ceiling_light", label: "電灯（未実装）" },
  { key: "indirect_light", label: DEVICE_LABELS.indirect_light },
  { key: "indoor_speaker", label: DEVICE_LABELS.indoor_speaker },
  { key: "bedside_speaker", label: DEVICE_LABELS.bedside_speaker },
];

/** 個別切替の状態の選択肢。 */
export const STATE_OPTIONS: { value: OnOff; label: string }[] = [
  { value: "on", label: "ON" },
  { value: "off", label: "OFF" },
];

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

/** 送信前の検証。問題があれば、最初の 1 件を一文で返す（実行条件 → 曜日 → 時刻 → 実行内容の順）。問題がなければ null。 */
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
  if (form.actionType === "") {
    return "実行内容を選択してください。";
  }
  if (form.actionType === "scene") {
    return form.scene === "" ? "一括切替を選択してください。" : null;
  }
  if (form.device === "") {
    return "機器を選択してください。";
  }
  if (form.state === "") {
    return "状態（ON / OFF）を選択してください。";
  }
  return null;
}

/**
 * API へ送る本文。曜日・祝日の扱い・実行日の取り方は、実行条件が「曜日の指定」のときだけ付ける。
 * 実行内容は、一括切替なら scene、個別切替なら device と state のどちらか一方だけを付ける。
 */
export function toScheduleBody(form: ScheduleForm): ScheduleInput {
  const body: ScheduleInput = {
    condition: form.condition as Condition,
    weekdays: form.condition === "weekdays" ? [...form.weekdays].sort((a, b) => a - b) : [],
    run_time: form.time,
    is_enabled: form.enabled,
  };
  if (form.condition === "weekdays") {
    body.holiday_mode = form.holidayMode;
    body.day_shift = form.dayShift;
  }
  if (form.actionType === "device") {
    body.device = form.device as TimerDeviceKey;
    body.state = form.state as OnOff;
  } else {
    body.scene = form.scene as SceneKey;
  }
  return body;
}

/** 登録・変更の要求本文。 */
export type ScheduleInput = {
  condition: Condition;
  weekdays: number[];
  holiday_mode?: HolidayMode;
  day_shift?: DayShift;
  run_time: string;
  scene?: SceneKey;
  device?: TimerDeviceKey;
  state?: OnOff;
  is_enabled: boolean;
};

/** 既存の定期実行から、入力フォームの初期値を作る。新規は、実行条件と実行内容の種類を未選択にする。 */
export function formFromItem(item: ScheduleItem | null): ScheduleForm {
  if (item === null) {
    return {
      condition: "",
      weekdays: [],
      holidayMode: "none",
      dayShift: "same",
      time: "",
      actionType: "",
      scene: "",
      device: "",
      state: "",
      enabled: true,
    };
  }
  const isDevice = Boolean(item.device && item.state);
  return {
    condition: item.condition,
    weekdays: [...item.weekdays],
    holidayMode: item.holiday_mode ?? "none",
    dayShift: item.day_shift ?? "same",
    time: item.run_time,
    actionType: isDevice ? "device" : "scene",
    scene: isDevice ? "" : (item.scene ?? ""),
    device: isDevice ? (item.device ?? "") : "",
    state: isDevice ? (item.state ?? "") : "",
    enabled: item.is_enabled,
  };
}
