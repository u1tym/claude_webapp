export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_USER_MANAGEMENT_URL;
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
  if (res.status === 401) {
    throw new Error("unauth");
  }
  if (res.status === 403) {
    throw new Error("forbidden");
  }
}

export type Settings = {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
};

export type UserItem = {
  id: number;
  username: string;
  email: string;
  is_self: boolean;
};

export type FeatureItem = {
  id: string;
  title: string;
  url: string;
  icon: string;
  is_protected: boolean;
};

export type AssignmentItem = {
  user_id: number;
  username: string;
  feature_id: string;
  feature_title: string;
  display_order: number;
  can_unassign: boolean;
};

export async function getSettings(): Promise<Settings> {
  const res = await apiFetch("/settings");
  if (!res.ok) {
    throw new Error("settings");
  }
  return (await res.json()) as Settings;
}

export async function getUsers(): Promise<UserItem[]> {
  const res = await apiFetch("/users");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("users");
  }
  return ((await res.json()) as { items: UserItem[] }).items;
}

export async function createUser(
  username: string,
  password: string,
  email: string,
): Promise<UserItem | "invalid" | "conflict"> {
  const res = await apiFetch("/users", {
    method: "POST",
    body: JSON.stringify({ username, password, email }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as UserItem;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("users");
}

export async function updateUser(
  userId: number,
  username: string,
  password: string,
  email: string,
): Promise<UserItem | "invalid" | "missing" | "conflict"> {
  const body: { username: string; email: string; password?: string } = { username, email };
  if (password !== "") {
    body.password = password;
  }
  const res = await apiFetch(`/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as UserItem;
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
  throw new Error("users");
}

export async function deleteUser(userId: number): Promise<"ok" | "missing" | "conflict"> {
  const res = await apiFetch(`/users/${userId}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("users");
}

export async function getFeatures(): Promise<FeatureItem[]> {
  const res = await apiFetch("/features");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("features");
  }
  return ((await res.json()) as { items: FeatureItem[] }).items;
}

export async function createFeature(
  id: string,
  title: string,
  url: string,
  icon: string,
): Promise<FeatureItem | "invalid" | "conflict"> {
  const res = await apiFetch("/features", {
    method: "POST",
    body: JSON.stringify({ id, title, url, icon }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as FeatureItem;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("features");
}

export async function updateFeature(
  featureId: string,
  title: string,
  url: string,
  icon: string,
): Promise<FeatureItem | "invalid" | "missing"> {
  const body: { title: string; url: string; icon?: string } = { title, url };
  if (icon !== "") {
    body.icon = icon;
  }
  const res = await apiFetch(`/features/${encodeURIComponent(featureId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as FeatureItem;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("features");
}

export async function deleteFeature(featureId: string): Promise<"ok" | "missing" | "conflict"> {
  const res = await apiFetch(`/features/${encodeURIComponent(featureId)}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("features");
}

export async function getAssignments(): Promise<AssignmentItem[]> {
  const res = await apiFetch("/assignments");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("assignments");
  }
  return ((await res.json()) as { items: AssignmentItem[] }).items;
}

export async function createAssignment(
  userId: number,
  featureId: string,
  displayOrder: number,
): Promise<AssignmentItem | "invalid" | "missing" | "conflict"> {
  const res = await apiFetch("/assignments", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, feature_id: featureId, display_order: displayOrder }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as AssignmentItem;
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
  throw new Error("assignments");
}

export async function deleteAssignment(
  userId: number,
  featureId: string,
): Promise<"ok" | "missing" | "conflict"> {
  const res = await apiFetch(`/assignments/${userId}/${encodeURIComponent(featureId)}`, {
    method: "DELETE",
  });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  if (res.status === 409) {
    return "conflict";
  }
  throw new Error("assignments");
}
