export class AuthError extends Error {
  status: 401 | 403;

  constructor(status: 401 | 403) {
    super(status === 401 ? "unauth" : "forbidden");
    this.status = status;
  }
}

export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_GOODS_MANAGEMENT_URL;
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

export type Person = {
  id: number;
  name: string;
};

export type Artist = {
  id: number;
  name: string;
};

export type ArtistDetail = {
  id: number;
  name: string;
  persons: Person[];
};

export type Media = {
  id: number;
  name: string;
};

export type GoodsListItem = {
  goods_id: number;
  media_id: number;
  media_name: string;
  artist_id: number;
  artist_name: string;
  title: string;
  release_date: string;
  is_owned: boolean;
  code_number: string | null;
  thumbnail_image_type: string | null;
  thumbnail_image_data: string | null;
};

export type GoodsImage = {
  id: number;
  image_type: string;
  image_data: string;
  display_order: number;
};

export type GoodsDetail = {
  id: number;
  media_id: number;
  artist_id: number;
  title: string;
  release_date: string;
  memo: string | null;
  is_owned: boolean;
  code_number: string | null;
  images: GoodsImage[];
};

export type GoodsInput = {
  media_id: number;
  artist_id: number;
  title: string;
  release_date?: string | null;
  memo?: string | null;
  is_owned?: boolean;
  code_number?: string | null;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("request-failed");
  }
  return (await res.json()) as T;
}

// ---- persons ------------------------------------------------------------------

export async function getPersons(): Promise<Person[]> {
  return (await requestJson<{ items: Person[] }>("/persons")).items;
}

export async function createPerson(name: string): Promise<Person | "invalid"> {
  const res = await apiFetch("/persons", { method: "POST", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as Person;
  if (res.status === 400) return "invalid";
  throw new Error("persons");
}

export async function renamePerson(id: number, name: string): Promise<Person | "invalid" | "missing"> {
  const res = await apiFetch(`/persons/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as Person;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("persons");
}

export async function deletePerson(id: number): Promise<"ok" | "missing" | "referenced"> {
  const res = await apiFetch(`/persons/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  if (res.status === 409) return "referenced";
  throw new Error("persons");
}

export async function getRelatedArtists(personId: number): Promise<Artist[] | "missing"> {
  const res = await apiFetch(`/persons/${personId}/related-artists`);
  throwIfAuthFailed(res);
  if (res.status === 200) return ((await res.json()) as { items: Artist[] }).items;
  if (res.status === 404) return "missing";
  throw new Error("related-artists");
}

export async function getRelatedMedia(personId: number): Promise<Media[] | "missing"> {
  const res = await apiFetch(`/persons/${personId}/related-media`);
  throwIfAuthFailed(res);
  if (res.status === 200) return ((await res.json()) as { items: Media[] }).items;
  if (res.status === 404) return "missing";
  throw new Error("related-media");
}

// ---- artists ------------------------------------------------------------------

export async function getArtists(): Promise<Artist[]> {
  return (await requestJson<{ items: Artist[] }>("/artists")).items;
}

export async function getArtistDetail(id: number): Promise<ArtistDetail | "missing"> {
  const res = await apiFetch(`/artists/${id}`);
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as ArtistDetail;
  if (res.status === 404) return "missing";
  throw new Error("artists");
}

export async function createArtist(
  name: string,
  personIds: number[],
): Promise<ArtistDetail | "invalid" | "missing"> {
  const res = await apiFetch("/artists", {
    method: "POST",
    body: JSON.stringify({ name, person_ids: personIds }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as ArtistDetail;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("artists");
}

export async function updateArtist(
  id: number,
  name: string,
  personIds: number[],
): Promise<ArtistDetail | "invalid" | "missing"> {
  const res = await apiFetch(`/artists/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name, person_ids: personIds }),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as ArtistDetail;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("artists");
}

export async function deleteArtist(id: number): Promise<"ok" | "missing" | "referenced"> {
  const res = await apiFetch(`/artists/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  if (res.status === 409) return "referenced";
  throw new Error("artists");
}

// ---- media --------------------------------------------------------------------

export async function getMediaList(): Promise<Media[]> {
  return (await requestJson<{ items: Media[] }>("/media")).items;
}

export async function createMedia(name: string): Promise<Media | "invalid"> {
  const res = await apiFetch("/media", { method: "POST", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as Media;
  if (res.status === 400) return "invalid";
  throw new Error("media");
}

export async function renameMedia(id: number, name: string): Promise<Media | "invalid" | "missing"> {
  const res = await apiFetch(`/media/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as Media;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("media");
}

export async function deleteMedia(id: number): Promise<"ok" | "missing" | "referenced"> {
  const res = await apiFetch(`/media/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  if (res.status === 409) return "referenced";
  throw new Error("media");
}

// ---- goods ----------------------------------------------------------------------

export async function getGoodsList(
  personId: number,
  artistId: number | null,
  mediaId: number | null,
): Promise<GoodsListItem[] | "missing"> {
  const params = new URLSearchParams({ person_id: String(personId) });
  if (artistId !== null) params.set("artist_id", String(artistId));
  if (mediaId !== null) params.set("media_id", String(mediaId));
  const res = await apiFetch(`/goods?${params.toString()}`);
  throwIfAuthFailed(res);
  if (res.status === 200) return ((await res.json()) as { items: GoodsListItem[] }).items;
  if (res.status === 404) return "missing";
  throw new Error("goods");
}

export async function getGoods(id: number): Promise<GoodsDetail | "missing"> {
  const res = await apiFetch(`/goods/${id}`);
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as GoodsDetail;
  if (res.status === 404) return "missing";
  throw new Error("goods");
}

export async function createGoods(input: GoodsInput): Promise<GoodsDetail | "invalid" | "missing"> {
  const res = await apiFetch("/goods", { method: "POST", body: JSON.stringify(input) });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as GoodsDetail;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("goods");
}

export async function updateGoods(
  id: number,
  input: GoodsInput,
): Promise<GoodsDetail | "invalid" | "missing"> {
  const res = await apiFetch(`/goods/${id}`, { method: "PATCH", body: JSON.stringify(input) });
  throwIfAuthFailed(res);
  if (res.status === 200) return (await res.json()) as GoodsDetail;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("goods");
}

export async function deleteGoods(id: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/goods/${id}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  throw new Error("goods");
}

export async function addGoodsImage(
  goodsId: number,
  imageType: string,
  imageData: string,
): Promise<GoodsImage | "invalid" | "missing"> {
  const res = await apiFetch(`/goods/${goodsId}/images`, {
    method: "POST",
    body: JSON.stringify({ image_type: imageType, image_data: imageData }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) return (await res.json()) as GoodsImage;
  if (res.status === 400) return "invalid";
  if (res.status === 404) return "missing";
  throw new Error("goods-images");
}

export async function deleteGoodsImage(goodsId: number, imageId: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/goods/${goodsId}/images/${imageId}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) return "ok";
  if (res.status === 404) return "missing";
  throw new Error("goods-images");
}
