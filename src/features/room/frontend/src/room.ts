/** 機器のキー（API の `device`）。 */
export type DeviceKey =
  | "ceiling_light"
  | "indirect_light"
  | "indoor_speaker"
  | "bedside_speaker"
  | "front_door";

/** パーツのクリックで切り替えられる機器（5 機器すべて。電池残量は機器ではなく、表示のみ）。 */
export type OperableDeviceKey = DeviceKey;

export type OnOff = "on" | "off";
export type LockState = "locked" | "unlocked";

/**
 * API の `device_state`。status が error のとき state は null（状態を推測しない）。
 * 電灯の状態は電源（on / off）だけで、明るさと色温度は持たない。
 */
export type DeviceState = {
  status: "ok" | "error";
  state: OnOff | LockState | null;
  /** 玄関ドアだけが持つ。0〜100。取得できなければ null */
  battery?: number | null;
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

/** 切り替えられる機器か（5 機器すべて）。 */
export function isOperable(_key: DeviceKey): _key is OperableDeviceKey {
  return true;
}

/** 調光パターンの識別子（API の `pattern`）。 */
export type PatternKey = "full" | "reading" | "relax" | "night";

/** API の調光パターン 1 種（GET /dimming-patterns）。明るさ 1〜100、色温度 2700〜6500。 */
export type DimmingPattern = {
  id: PatternKey;
  name: string;
  brightness: number;
  color_temperature: number;
};

/** GET /dimming-patterns の応答。default は、パターンを選ばずに ON にするときのパターン。 */
export type DimmingPatterns = {
  default: PatternKey;
  patterns: DimmingPattern[];
};

/**
 * 調光パターンの名称（固定 4 種。表示の順）。定期実行の一覧の表示と、入力の選択肢に使う。
 * 明るさと色温度の値は持たない（GET /dimming-patterns の値を、目安として添える）。
 */
export const PATTERN_OPTIONS: { value: PatternKey; label: string }[] = [
  { value: "full", label: "全灯" },
  { value: "reading", label: "読書" },
  { value: "relax", label: "くつろぎ" },
  { value: "night", label: "夜" },
];

/** 調光パターンを選ばずに電灯を ON にするときのパターン（API の既定と同じ）。 */
export const DEFAULT_PATTERN: PatternKey = "full";

/** 調光パターンの明るさと色温度の目安（選択肢の Caption）。 */
export function patternCaption(pattern: DimmingPattern): string {
  return `明るさ ${pattern.brightness}・色温度 ${pattern.color_temperature}`;
}

/** 調光パターンの名称。一覧に無い識別子は、識別子のまま返す。 */
export function patternName(patterns: DimmingPattern[], id: string): string {
  return patterns.find((p) => p.id === id)?.name ?? id;
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
  const next = nextState(key, device);
  if (next === null) {
    return `${name} 取得できません`;
  }
  const current = stateText(device);
  if (key === "ceiling_light") {
    // 電灯は、押すと調光パターンダイアログを開く（すぐには切り替えない）
    return device.state === "on"
      ? `${name} ${current}。押すと調光パターンの変更または消灯ができます`
      : `${name} ${current}。押すと調光パターンを選んで点灯します`;
  }
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

/** 切替が成功したときのステータスの一文。電灯を ON にしたときは、調光パターンの名称を添える。 */
export function switchSuccessMessage(
  key: DeviceKey,
  target: OnOff | LockState,
  patternLabel?: string,
): string {
  if (key === "front_door") {
    return `玄関ドアを${DOOR_ACTION_TEXT[target as LockState]}しました。`;
  }
  if (key === "ceiling_light" && target === "on" && patternLabel) {
    return `${DEVICE_LABELS[key]}を ${STATE_TEXT[target]}（${patternLabel}）にしました。`;
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

/** 一括切替の機器ごとの結果。 */
export type SceneOutcome = {
  device: DeviceKey;
  target: OnOff;
  outcome: "success" | "failure";
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

/**
 * 一括切替の結果のステータス。失敗があるときは、成功した機器と失敗した機器の名称を示す。
 * 電灯選択で調光パターンを選んだときは、成功の一文にパターンの名称を添える。
 */
export function sceneStatus(
  scene: SceneKey,
  outcome: "success" | "partial" | "failure",
  results: SceneOutcome[],
  patternLabel?: string,
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
  const detail = scene === "ceiling_light" && patternLabel ? `（${patternLabel}）` : "";
  return { kind: "success", text: `${sceneLabel(scene)}${detail}を実行しました。` };
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
  /** 電灯を ON にする個別切替の調光パターン。それ以外は null */
  pattern?: PatternKey | null;
  /** 付いているタイトル（50 文字まで）。付いていなければ null */
  title?: string | null;
  /** 付いている表示順（0〜9999）。付いていなければ null（一覧の末尾） */
  display_order?: number | null;
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
 * 電灯を ON にするときは、調光パターンの名称を添える（「電灯を ON（読書）」）。
 */
export function actionText(
  item: Pick<ScheduleItem, "scene" | "device" | "state"> & Partial<Pick<ScheduleItem, "pattern">>,
): string {
  if (item.device && item.state) {
    const base = `${DEVICE_LABELS[item.device]}を ${item.state === "on" ? "ON" : "OFF"}`;
    if (item.device === "ceiling_light" && item.state === "on" && item.pattern) {
      const label = PATTERN_OPTIONS.find((o) => o.value === item.pattern)?.label ?? item.pattern;
      return `${base}（${label}）`;
    }
    return base;
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
  /** 調光パターン。電灯を ON にする個別切替のときだけ意味を持つ（既定は全灯） */
  pattern: PatternKey;
  /** タイトル（任意。空は「付けない」）。入力欄の値のまま持つ */
  title: string;
  /** 表示順（任意。空は「付けない」）。入力欄の値のまま持つ（検証で、0〜9999 の整数かを確かめる） */
  displayOrder: string;
  enabled: boolean;
};

/** タイトルの最大の長さ（文字）。表示順の範囲。Web アプリの API と同じ。 */
export const TITLE_MAX_LENGTH = 50;
export const DISPLAY_ORDER_MAX = 9999;
const DISPLAY_ORDER_PATTERN = /^[0-9]{1,4}$/;

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

/** 個別切替の機器の選択肢（玄関ドアは含めない）。 */
export const TIMER_DEVICES: { key: TimerDeviceKey; label: string }[] = [
  { key: "ceiling_light", label: DEVICE_LABELS.ceiling_light },
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
    if (form.scene === "") {
      return "一括切替を選択してください。";
    }
    return validateTitleAndOrder(form);
  }
  if (form.device === "") {
    return "機器を選択してください。";
  }
  if (form.state === "") {
    return "状態（ON / OFF）を選択してください。";
  }
  return validateTitleAndOrder(form);
}

/** タイトルと表示順の検証。問題があれば、最初の 1 件を一文で返す（タイトル → 表示順）。どちらも空でよい。 */
export function validateTitleAndOrder(form: Pick<ScheduleForm, "title" | "displayOrder">): string | null {
  if (form.title.trim().length > TITLE_MAX_LENGTH) {
    return `タイトルは ${TITLE_MAX_LENGTH} 文字以内で入力してください。`;
  }
  const order = form.displayOrder.trim();
  if (order !== "" && (!DISPLAY_ORDER_PATTERN.test(order) || Number(order) > DISPLAY_ORDER_MAX)) {
    return `表示順は 0 以上 ${DISPLAY_ORDER_MAX} 以下の整数で入力してください。`;
  }
  return null;
}

/**
 * API へ送る本文。曜日・祝日の扱い・実行日の取り方は、実行条件が「曜日の指定」のときだけ付ける。
 * 実行内容は、一括切替なら scene、個別切替なら device と state のどちらか一方だけを付ける。
 */
export function toScheduleBody(form: ScheduleForm): ScheduleInput {
  // タイトルと表示順は、常に送る（空は null。Web アプリは、項目が無いと現在の値を変えないため、外すには null を送る）
  const title = form.title.trim();
  const order = form.displayOrder.trim();
  const body: ScheduleInput = {
    condition: form.condition as Condition,
    weekdays: form.condition === "weekdays" ? [...form.weekdays].sort((a, b) => a - b) : [],
    run_time: form.time,
    title: title === "" ? null : title,
    display_order: order === "" ? null : Number(order),
    is_enabled: form.enabled,
  };
  if (form.condition === "weekdays") {
    body.holiday_mode = form.holidayMode;
    body.day_shift = form.dayShift;
  }
  if (form.actionType === "device") {
    body.device = form.device as TimerDeviceKey;
    body.state = form.state as OnOff;
    // 調光パターンは、電灯を ON にするときだけ送る
    if (isCeilingOn(form)) {
      body.pattern = form.pattern;
    }
  } else {
    body.scene = form.scene as SceneKey;
  }
  return body;
}

/** 入力フォームが「電灯を ON にする個別切替」か（調光パターンを選べる条件）。 */
export function isCeilingOn(form: Pick<ScheduleForm, "actionType" | "device" | "state">): boolean {
  return form.actionType === "device" && form.device === "ceiling_light" && form.state === "on";
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
  pattern?: PatternKey;
  /** タイトル。空は null（外す） */
  title: string | null;
  /** 表示順。空は null（外す） */
  display_order: number | null;
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
      pattern: DEFAULT_PATTERN,
      title: "",
      displayOrder: "",
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
    pattern: item.pattern ?? DEFAULT_PATTERN,
    title: item.title ?? "",
    displayOrder: item.display_order == null ? "" : String(item.display_order),
    enabled: item.is_enabled,
  };
}
