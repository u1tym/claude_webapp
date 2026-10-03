/** 未ログイン（401）または権限なし（403）。画面は誘導・表示の切替に使う。 */
export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

/** 入力不正（400）・競合（409）など、画面にメッセージを出す失敗。内部理由は含まない。 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** API の基点 URL（環境変数）にパスを足す。ホストをコードに直書きしない。 */
export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_CONTRACT_MANAGEMENT_URL;
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

/** 応答が成功でなければ、AuthError か ApiError を投げる。本文の detail（内部理由を含まない一文）を使う。 */
export async function ensureOk(res: Response): Promise<Response> {
  throwIfAuthFailed(res);
  if (!res.ok) {
    let message = "サーバエラーです";
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // 本文が JSON でないときは、既定の文言のまま
    }
    throw new ApiError(res.status, message);
  }
  return res;
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
