// api-design.md の全エンドポイントに対応する呼び出し。

import { apiUrl, jsonBody, queryString, request, requestVoid } from "./client";
import type {
  Genre,
  HistoryItem,
  LastPlayback,
  ListVideosQuery,
  NextVideo,
  Paged,
  PlaybackInfo,
  PlaylistDetail,
  PlaylistPlaybackItem,
  PlaylistSummary,
  Series,
  SeriesDetail,
  Settings,
  VideoCreateBody,
  VideoDetail,
  VideoSummary,
  VideoUpdateBody,
} from "../types";

export * from "./client";

// ---- 設定 ------------------------------------------------------------

export const getSettings = (): Promise<Settings> => request<Settings>("/settings");

// ---- ジャンル ----------------------------------------------------------

export const listGenres = (): Promise<{ items: Genre[] }> => request("/genres");

export const createGenre = (name: string, sortOrder: number): Promise<Genre> =>
  request("/genres", { method: "POST", body: jsonBody({ name, sort_order: sortOrder }) });

// ---- 作品 ------------------------------------------------------------

export const listSeries = (page: number, q?: string, perPage = 20): Promise<Paged<Series>> =>
  request(`/series${queryString({ page, per_page: perPage, q })}`);

export const createSeries = (title: string, description?: string): Promise<Series> =>
  request("/series", { method: "POST", body: jsonBody({ title, description: description || null }) });

export const getSeries = (id: number): Promise<SeriesDetail> => request(`/series/${id}`);

// ---- 動画 ------------------------------------------------------------

export const listVideos = (query: ListVideosQuery): Promise<Paged<VideoSummary>> =>
  request(`/videos${queryString({ ...query })}`);

export const createVideo = (body: VideoCreateBody): Promise<{ id: number; status: string }> =>
  request("/videos", { method: "POST", body: jsonBody(body) });

export const getVideo = (id: number): Promise<VideoDetail> => request(`/videos/${id}`);

export const updateVideo = (id: number, body: VideoUpdateBody): Promise<VideoDetail> =>
  request(`/videos/${id}`, { method: "PATCH", body: jsonBody(body) });

export const deleteVideo = (id: number): Promise<void> => requestVoid(`/videos/${id}`, { method: "DELETE" });

export const replaceVideoFile = (id: number, durationMs: number, mimeType: string): Promise<void> =>
  requestVoid(`/videos/${id}/replace`, {
    method: "POST",
    body: jsonBody({ duration_ms: durationMs, mime_type: mimeType }),
  });

export const uploadChunk = (
  id: number,
  chunkIndex: number,
  startMs: number,
  endMs: number,
  data: Blob,
): Promise<void> => {
  const form = new FormData();
  form.append("chunk_index", String(chunkIndex));
  form.append("start_time_ms", String(startMs));
  form.append("end_time_ms", String(endMs));
  form.append("data", data, `chunk_${chunkIndex}`);
  return requestVoid(`/videos/${id}/chunks`, { method: "POST", body: form });
};

export const completeUpload = (id: number, durationMs: number, chunkCount: number): Promise<void> =>
  requestVoid(`/videos/${id}/complete`, {
    method: "POST",
    body: jsonBody({ duration_ms: durationMs, chunk_count: chunkCount }),
  });

export const putThumbnail = (id: number, blob: Blob, width?: number, height?: number): Promise<void> => {
  const form = new FormData();
  form.append("data", blob, "thumbnail");
  form.append("mime_type", blob.type || "image/jpeg");
  if (width !== undefined) form.append("width", String(width));
  if (height !== undefined) form.append("height", String(height));
  return requestVoid(`/videos/${id}/thumbnail`, { method: "PUT", body: form });
};

/** 動画要素・画像要素に直接指定する URL（Cookie はブラウザが送る）。 */
export const streamUrl = (id: number): string => apiUrl(`/videos/${id}/stream`);
export const thumbnailUrl = (id: number): string => apiUrl(`/videos/${id}/thumbnail`);

// ---- 再生 ------------------------------------------------------------

export const startPlayback = (id: number, resume: boolean): Promise<PlaybackInfo> =>
  request(`/videos/${id}/playback/start`, { method: "POST", body: jsonBody({ resume }) });

// keepalive: 画面を閉じる直前の保存でも、リクエストを完了させる
export const saveVideoState = (
  id: number,
  positionMs: number,
  completed: boolean,
  keepalive = false,
): Promise<void> =>
  requestVoid(`/videos/${id}/playback/state`, {
    method: "PUT",
    body: jsonBody({ position_ms: positionMs, completed }),
    keepalive,
  });

export const getNextVideo = (id: number): Promise<NextVideo> => request(`/videos/${id}/next`);

export const listHistory = (page: number): Promise<Paged<HistoryItem>> =>
  request(`/playback/history${queryString({ page })}`);

export const getLastPlayback = (): Promise<LastPlayback> => request("/playback/last");

// ---- プレイリスト ------------------------------------------------------

export const listPlaylists = (page: number): Promise<Paged<PlaylistSummary>> =>
  request(`/playlists${queryString({ page })}`);

export const createPlaylist = (name: string, description?: string): Promise<PlaylistDetail> =>
  request("/playlists", { method: "POST", body: jsonBody({ name, description: description || null }) });

export const getPlaylist = (id: number): Promise<PlaylistDetail> => request(`/playlists/${id}`);

export const updatePlaylist = (
  id: number,
  body: { name?: string; description?: string | null },
): Promise<PlaylistDetail> => request(`/playlists/${id}`, { method: "PATCH", body: jsonBody(body) });

export const deletePlaylist = (id: number): Promise<void> => requestVoid(`/playlists/${id}`, { method: "DELETE" });

export const replacePlaylistItems = (id: number, videoIds: number[]): Promise<PlaylistDetail> =>
  request(`/playlists/${id}/items`, {
    method: "PUT",
    body: jsonBody({ items: videoIds.map((video_id) => ({ video_id })) }),
  });

export const startPlaylistPlayback = (id: number, resume: boolean): Promise<PlaylistPlaybackItem> =>
  request(`/playlists/${id}/playback/start`, { method: "POST", body: jsonBody({ resume }) });

export const getNextPlaylistItem = (
  id: number,
  itemId: number,
): Promise<{ has_next: boolean; item: PlaylistPlaybackItem | null }> =>
  request(`/playlists/${id}/items/${itemId}/next`);

export const getPrevPlaylistItem = (
  id: number,
  itemId: number,
): Promise<{ has_prev: boolean; item: PlaylistPlaybackItem | null }> =>
  request(`/playlists/${id}/items/${itemId}/prev`);

export const savePlaylistItemState = (
  id: number,
  itemId: number,
  positionMs: number,
  completed: boolean,
  keepalive = false,
): Promise<void> =>
  requestVoid(`/playlists/${id}/items/${itemId}/playback/state`, {
    method: "PUT",
    body: jsonBody({ position_ms: positionMs, completed }),
    keepalive,
  });
