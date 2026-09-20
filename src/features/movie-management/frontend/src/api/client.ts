// API の呼び出しの共通処理。基点 URL は環境変数、呼び出し時は Cookie を含める。

export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

/** サーバが返した失敗。message は画面に出してよい一文（内部理由を含まない）。 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type AuthHandler = (error: AuthError) => void;

let authHandler: AuthHandler | null = null;

/** 401（ログイン画面へ）・403（権限なしの表示）を、画面側の 1 か所で扱うための登録。 */
export function setAuthHandler(handler: AuthHandler | null): void {
  authHandler = handler;
}

export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_MOVIE_MANAGEMENT_URL;
  return `${base.replace(/\/$/, "")}${path}`;
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  // multipart（FormData）は境界付きの Content-Type をブラウザに任せる
  if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(apiUrl(path), { ...init, headers, credentials: "include" });
}

async function fail(res: Response): Promise<never> {
  if (res.status === 401 || res.status === 403) {
    const error = new AuthError(res.status);
    authHandler?.(error);
    throw error;
  }
  let message = "サーバエラーです";
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      message = body.detail;
    }
  } catch {
    // 本文が JSON でないときは既定の文言のまま
  }
  throw new ApiError(res.status, message);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    return fail(res);
  }
  return (await res.json()) as T;
}

/** 本文のない成功応答（204）を返す API。 */
export async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    await fail(res);
  }
}

export function jsonBody(value: unknown): RequestInit["body"] {
  return JSON.stringify(value);
}

/** 画面に出す失敗の文言。認証エラーは画面側で処理済みのため文言を出さない。 */
export function errorMessage(error: unknown, fallback = "サーバエラーです"): string {
  if (error instanceof AuthError) {
    return "";
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

export function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
