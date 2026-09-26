export type ApiKeyStatus = "active" | "expired" | "revoked";

export interface ApiKeyItem {
  id: number;
  name: string;
  key_prefix: string;
  status: ApiKeyStatus;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface IssuedApiKey extends ApiKeyItem {
  key: string;
}

export interface Settings {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
}

/** 401 / 403 は画面側で扱いを分けるため、状態コードを持たせて投げる。 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function baseUrl(): string {
  const raw = import.meta.env.VITE_API_API_KEY_MANAGEMENT_URL;
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}

let loginUrl: string | null = null;

export function setLoginUrl(url: string): void {
  loginUrl = url;
}

function redirectToLogin(): void {
  if (loginUrl) {
    window.location.href = loginUrl;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl()}${path}`, {
      method,
      credentials: "include",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network");
  }
  if (res.status === 401) {
    redirectToLogin();
    throw new ApiError(401, "unauthenticated");
  }
  if (!res.ok) {
    throw new ApiError(res.status, "failed");
  }
  return (await res.json()) as T;
}

export function fetchSettings(): Promise<Settings> {
  return request<Settings>("GET", "/settings");
}

export async function listApiKeys(): Promise<ApiKeyItem[]> {
  const body = await request<{ items: ApiKeyItem[] }>("GET", "/api-keys");
  return body.items;
}

export function issueApiKey(name: string, expiresAt: string | null): Promise<IssuedApiKey> {
  return request<IssuedApiKey>("POST", "/api-keys", { name, expires_at: expiresAt });
}

export function revokeApiKey(id: number): Promise<ApiKeyItem> {
  return request<ApiKeyItem>("POST", `/api-keys/${id}/revoke`);
}
