export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_PASSWORD_MANAGEMENT_URL;
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

export type PasswordSummary = {
  id: number;
  title: string;
  userword: string;
  site: string | null;
  memo: string | null;
};

export type PasswordEntry = PasswordSummary & {
  psword: string;
};

export async function getPasswords(keyword?: string): Promise<PasswordSummary[]> {
  const params = keyword && keyword.trim() !== "" ? `?keyword=${encodeURIComponent(keyword)}` : "";
  const res = await apiFetch(`/passwords${params}`);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("passwords");
  }
  return ((await res.json()) as { items: PasswordSummary[] }).items;
}

export async function getPassword(id: number): Promise<PasswordEntry | "missing"> {
  const res = await apiFetch(`/passwords/${id}`);
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as PasswordEntry;
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("password");
}

export type PasswordInput = {
  title: string;
  userword: string;
  psword: string;
  site: string | null;
  memo: string | null;
};

export async function createPassword(input: PasswordInput): Promise<PasswordEntry | "invalid" | "conflict"> {
  const res = await apiFetch("/passwords", {
    method: "POST",
    body: JSON.stringify(input),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as PasswordEntry;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("password");
}

export async function updatePassword(
  id: number,
  input: PasswordInput,
): Promise<PasswordEntry | "invalid" | "missing" | "conflict"> {
  const res = await apiFetch(`/passwords/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as PasswordEntry;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 404) {
    return "missing";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("password");
}

export async function deletePassword(id: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/passwords/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("password");
}
