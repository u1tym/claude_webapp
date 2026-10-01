import type {
  DeviceKey,
  DeviceState,
  Devices,
  LockState,
  OnOff,
  SceneKey,
  SceneOutcome,
  ScheduleInput,
  ScheduleItem,
} from "./room";

/** 未ログイン（401）または権限なし（403）。画面は誘導・表示の切替に使う。 */
export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

/** API の基点 URL（環境変数）にパスを足す。ホストをコードに直書きしない。 */
export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_ROOM_URL;
  return `${base.replace(/\/$/, "")}${path}`;
}

/** API を呼ぶ。Cookie を送る（セッション ID は localStorage や URL に置かない）。 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(apiUrl(path), {
    ...init,
    headers,
    credentials: "include",
  });
}

/** 401 / 403 なら AuthError を投げる。 */
export function throwIfAuthFailed(res: Response): void {
  if (res.status === 401 || res.status === 403) {
    throw new AuthError(res.status);
  }
}

export type Settings = {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
};

/** ログイン URL、メニュー URL、アイコンを取得する（認証不要）。 */
export async function getSettings(): Promise<Settings> {
  const res = await apiFetch("/settings");
  if (!res.ok) {
    throw new Error("settings failed");
  }
  return (await res.json()) as Settings;
}

/** GET /state の応答。 */
export type StateResponse = {
  fetched_at: string;
  devices: Devices;
};

/** PUT /devices/{device}/state の応答。 */
export type SwitchResponse = {
  device: DeviceKey;
  applied: boolean;
  fetched_at: string;
  result: DeviceState;
};

/** 5 機器の状態と取得日時を取得する。401 / 403 は AuthError。 */
export async function getState(): Promise<StateResponse> {
  const res = await apiFetch("/state");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("state failed");
  }
  return (await res.json()) as StateResponse;
}

/** 切替の失敗。status は HTTP ステータス、message は画面に出せる一文（内部理由は含まない）。 */
export class SwitchError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** 1 機器を目標の状態へ切り替える。目標の状態は必ず明示する（「反転」は送らない）。 */
export async function putDeviceState(
  device: DeviceKey,
  state: OnOff | LockState,
): Promise<SwitchResponse> {
  const res = await apiFetch(`/devices/${device}/state`, {
    method: "PUT",
    body: JSON.stringify({ state }),
  });
  throwIfAuthFailed(res);
  if (!res.ok) {
    // 502 は「機器を操作できませんでした」。それ以外は一般的な文言にする
    throw new SwitchError(
      res.status,
      res.status === 502 ? "機器を操作できませんでした。" : "操作に失敗しました。",
    );
  }
  return (await res.json()) as SwitchResponse;
}

/** POST /scenes/{scene} の応答。 */
export type SceneResponse = {
  scene: SceneKey;
  outcome: "success" | "partial" | "failure";
  results: SceneOutcome[];
  fetched_at: string;
  devices: Devices;
};

/** 一括切替を実行する。一部の機器が失敗しても 200 で返り、機器ごとの結果が results に入る。 */
export async function postScene(scene: SceneKey): Promise<SceneResponse> {
  const res = await apiFetch(`/scenes/${scene}`, { method: "POST" });
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new SwitchError(res.status, "操作に失敗しました。");
  }
  return (await res.json()) as SceneResponse;
}

/** 定期実行の一覧を取得する。401 / 403 は AuthError。 */
export async function getSchedules(): Promise<ScheduleItem[]> {
  const res = await apiFetch("/schedules");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("schedules failed");
  }
  return ((await res.json()) as { schedules: ScheduleItem[] }).schedules;
}

/** 定期実行の有効／無効を切り替える。 */
export async function setScheduleEnabled(id: number, isEnabled: boolean): Promise<ScheduleItem> {
  const res = await apiFetch(`/schedules/${id}/enabled`, {
    method: "PUT",
    body: JSON.stringify({ is_enabled: isEnabled }),
  });
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new SwitchError(res.status, "操作に失敗しました。");
  }
  return (await res.json()) as ScheduleItem;
}

/** 定期実行を削除する。 */
export async function deleteSchedule(id: number): Promise<void> {
  const res = await apiFetch(`/schedules/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new SwitchError(res.status, "操作に失敗しました。");
  }
}

/** 登録・変更の失敗の文言。400 は入力の見直しを促し、それ以外は一般的な文言にする。 */
function saveFailureMessage(status: number): string {
  return status === 400 ? "保存できませんでした。入力内容を確認してください。" : "操作に失敗しました。";
}

/** 定期実行を登録する（201）。 */
export async function createSchedule(input: ScheduleInput): Promise<ScheduleItem> {
  const res = await apiFetch("/schedules", { method: "POST", body: JSON.stringify(input) });
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new SwitchError(res.status, saveFailureMessage(res.status));
  }
  return (await res.json()) as ScheduleItem;
}

/** 定期実行を変更する（全項目を置き換える）。 */
export async function updateSchedule(id: number, input: ScheduleInput): Promise<ScheduleItem> {
  const res = await apiFetch(`/schedules/${id}`, { method: "PUT", body: JSON.stringify(input) });
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new SwitchError(res.status, saveFailureMessage(res.status));
  }
  return (await res.json()) as ScheduleItem;
}
