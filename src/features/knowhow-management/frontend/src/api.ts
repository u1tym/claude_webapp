export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_KNOWHOW_MANAGEMENT_URL;
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

export type MajorCategory = {
  id: number;
  name: string;
  display_order: number;
};

export type MiddleCategory = {
  id: number;
  major_category_id: number;
  name: string;
  display_order: number;
};

export type KnowhowSummary = {
  id: number;
  title: string;
  keywords: string | null;
  middle_category_id: number | null;
  display_order: number;
};

export type KnowhowDetail = {
  id: number;
  title: string;
  keywords: string | null;
  content: string;
  middle_category_id: number | null;
  display_order: number;
};

export type KnowhowSearchResult = {
  knowhow_id: number;
  title: string;
  display_order: number;
  major_category_id: number | null;
  major_category_name: string | null;
  middle_category_id: number | null;
  middle_category_name: string | null;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("request-failed");
  }
  return (await res.json()) as T;
}

export async function getMajorCategories(): Promise<MajorCategory[]> {
  return (await requestJson<{ items: MajorCategory[] }>("/major-categories")).items;
}

export async function createMajorCategory(name: string): Promise<MajorCategory | "invalid" | "conflict"> {
  const res = await apiFetch("/major-categories", { method: "POST", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as MajorCategory;
  if (res.status === 400) return "invalid";
  if (res.status === 409) return "conflict";
  throw new Error("major-categories");
}

export async function renameMajorCategory(
  id: number,
  name: string,
): Promise<MajorCategory | "invalid" | "missing" | "conflict"> {
  const res = await apiFetch(`/major-categories/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as MajorCategory;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  if (res.status === 409) return "conflict";
  throw new Error("major-categories");
}

export async function deleteMajorCategory(id: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/major-categories/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  throw new Error("major-categories");
}

export async function getMiddleCategories(majorId: number): Promise<MiddleCategory[] | "missing"> {
  const res = await apiFetch(`/major-categories/${majorId}/middle-categories`);
  throwIfAuthFailed(res);
  if (res.status === 200) return ((await res.json()) as { items: MiddleCategory[] }).items;
  if (res.status === 404) return "missing";
  throw new Error("middle-categories");
}

export async function createMiddleCategory(
  majorId: number,
  name: string,
): Promise<MiddleCategory | "invalid" | "missing" | "conflict"> {
  const res = await apiFetch(`/major-categories/${majorId}/middle-categories`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as MiddleCategory;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  if (res.status === 409) return "conflict";
  throw new Error("middle-categories");
}

export async function renameMiddleCategory(
  id: number,
  name: string,
): Promise<MiddleCategory | "invalid" | "missing" | "conflict"> {
  const res = await apiFetch(`/middle-categories/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as MiddleCategory;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  if (res.status === 409) return "conflict";
  throw new Error("middle-categories");
}

export async function deleteMiddleCategory(id: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/middle-categories/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  throw new Error("middle-categories");
}

export async function getKnowhows(middleId: number): Promise<KnowhowSummary[] | "missing"> {
  const res = await apiFetch(`/middle-categories/${middleId}/knowhows`);
  throwIfAuthFailed(res);
  if (res.status === 200) return ((await res.json()) as { items: KnowhowSummary[] }).items;
  if (res.status === 404) return "missing";
  throw new Error("knowhows");
}

export async function searchKnowhows(keywords: string[]): Promise<KnowhowSearchResult[]> {
  const params = new URLSearchParams();
  for (const keyword of keywords) {
    params.append("keyword", keyword);
  }
  return (await requestJson<{ items: KnowhowSearchResult[] }>(`/knowhows/search?${params.toString()}`)).items;
}

export async function getKnowhow(id: number): Promise<KnowhowDetail | "missing"> {
  const res = await apiFetch(`/knowhows/${id}`);
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as KnowhowDetail;
  if (res.status === 404) return "missing";
  throw new Error("knowhows");
}

export type KnowhowInput = {
  title: string;
  keywords: string | null;
  content: string;
  middle_category_id: number | null;
};

export async function createKnowhow(input: KnowhowInput): Promise<KnowhowDetail | "invalid" | "missing"> {
  const res = await apiFetch("/knowhows", { method: "POST", body: JSON.stringify(input) });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as KnowhowDetail;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("knowhows");
}

export async function updateKnowhow(
  id: number,
  input: KnowhowInput,
): Promise<KnowhowDetail | "invalid" | "missing"> {
  const res = await apiFetch(`/knowhows/${id}`, { method: "PATCH", body: JSON.stringify(input) });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as KnowhowDetail;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("knowhows");
}

export async function deleteKnowhow(id: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/knowhows/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  throw new Error("knowhows");
}

export async function swapKnowhowDisplayOrder(idA: number, idB: number): Promise<"ok" | "invalid" | "missing"> {
  const res = await apiFetch("/knowhows/swap-display-order", {
    method: "POST",
    body: JSON.stringify({ knowhow_id_a: idA, knowhow_id_b: idB }),
  });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("knowhows");
}
