// 再生の対象ごとの、サーバとのやり取り（usePlayer に渡す）。

import {
  getNextPlaylistItem,
  getNextVideo,
  getPrevPlaylistItem,
  saveVideoState,
  savePlaylistItemState,
  startPlayback,
  startPlaylistPlayback,
} from "../api";
import type { PlaybackInfo, PlaylistPlaybackItem } from "../types";
import type { PlayerBackend, PlayItem } from "./usePlayer";

async function hasNextVideo(videoId: number): Promise<boolean> {
  try {
    return (await getNextVideo(videoId)).has_next;
  } catch {
    return false;
  }
}

async function fromPlayback(info: PlaybackInfo): Promise<PlayItem> {
  return {
    videoId: info.id,
    itemId: null,
    title: info.title,
    durationMs: info.duration_ms,
    positionMs: info.position_ms,
    playable: info.status === "ready",
    hasNext: await hasNextVideo(info.id),
    hasPrev: false,
  };
}

/**
 * 単独の動画の再生。次の動画は、作品内順序（または登録日時順）で決まる。
 * 画面の動画が切り替わる（URL が変わる）ことがあるため、動画の識別子は呼び出しのたびに取得する。
 */
export function videoBackend(videoId: () => number): PlayerBackend {
  return {
    async start(resume) {
      return fromPlayback(await startPlayback(videoId(), resume));
    },
    async next(current) {
      const next = await getNextVideo(current.videoId);
      if (!next.has_next || !next.video) {
        return null;
      }
      // 次の動画は先頭から再生する
      return fromPlayback(await startPlayback(next.video.id, false));
    },
    async prev() {
      return null;
    },
    save: (current, positionMs, completed, keepalive) =>
      saveVideoState(current.videoId, positionMs, completed, keepalive),
  };
}

function fromPlaylistItem(item: PlaylistPlaybackItem): PlayItem {
  return {
    videoId: item.video_id,
    itemId: item.item_id,
    title: item.title,
    durationMs: item.duration_ms,
    positionMs: item.position_ms,
    playable: item.status === "ready",
    hasNext: item.has_next,
    hasPrev: item.has_prev,
  };
}

/** プレイリストの再生。前後の動画は、並び順で隣り合う項目。 */
export function playlistBackend(playlistId: number): PlayerBackend {
  return {
    async start(resume) {
      return fromPlaylistItem(await startPlaylistPlayback(playlistId, resume));
    },
    async next(current) {
      const result = await getNextPlaylistItem(playlistId, current.itemId ?? 0);
      return result.item ? fromPlaylistItem(result.item) : null;
    },
    async prev(current) {
      const result = await getPrevPlaylistItem(playlistId, current.itemId ?? 0);
      return result.item ? fromPlaylistItem(result.item) : null;
    },
    save: (current, positionMs, completed, keepalive) =>
      savePlaylistItemState(playlistId, current.itemId ?? 0, positionMs, completed, keepalive),
  };
}
