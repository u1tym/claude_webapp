export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_SERVER_START_URL;
  return `${base.replace(/\/$/, "")}${path}`;
}

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

function throwIfAuthFailed(res: Response): void {
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

export async function getSettings(): Promise<Settings> {
  const res = await apiFetch("/settings");
  if (!res.ok) {
    throw new Error("settings");
  }
  return (await res.json()) as Settings;
}

export async function getStatus(): Promise<boolean> {
  const res = await apiFetch("/status");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("status");
  }
  const body = (await res.json()) as { is_up: boolean };
  return body.is_up;
}

export async function startPower(confirmed: boolean): Promise<void> {
  const res = await apiFetch("/start", {
    method: "POST",
    body: JSON.stringify({ confirmed }),
  });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return;
  }
  throw new Error("start");
}
