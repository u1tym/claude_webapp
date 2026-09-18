export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_PORTAL_URL;
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

export type Settings = {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_settings: string;
  icon_back: string;
};

export type MenuItem = {
  id: string;
  title: string;
  url: string;
  icon: string;
};

export async function getSettings(): Promise<Settings> {
  const res = await apiFetch("/settings");
  if (!res.ok) {
    throw new Error("settings");
  }
  return (await res.json()) as Settings;
}

export async function getSession(): Promise<{ username: string } | null> {
  try {
    const res = await apiFetch("/auth/session");
    if (!res.ok) {
      return null;
    }
    return (await res.json()) as { username: string };
  } catch {
    return null;
  }
}

export async function login(username: string, password: string): Promise<"ok" | "fail" | "invalid"> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 400) {
    return "invalid";
  }
  return "fail";
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}

export async function getMenu(): Promise<MenuItem[]> {
  const res = await apiFetch("/menu");
  if (res.status === 401) {
    throw new Error("unauth");
  }
  if (!res.ok) {
    throw new Error("menu");
  }
  const body = (await res.json()) as { items: MenuItem[] };
  return body.items;
}

export type MenuNavLog = {
  id: string;
  title: string;
  from_db: string;
  destination: string;
  error: string;
};

export async function logMenuNavigation(payload: MenuNavLog): Promise<void> {
  await apiFetch("/menu/nav-log", {
    method: "POST",
    body: JSON.stringify(payload),
    keepalive: true,
  });
}
