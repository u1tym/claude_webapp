// api-design.md のオブジェクトに対応する型。

export type VideoStatus = "uploading" | "ready" | "error";

export type Pagination = {
  page: number;
  per_page: number;
  total_count: number;
  total_pages: number;
};

export type Paged<T> = { items: T[]; pagination: Pagination };

export type Settings = {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
};

export type Genre = { id: number; name: string; sort_order: number; is_system: boolean };

export type Series = {
  id: number;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type SeriesVideo = {
  id: number;
  title: string;
  episode_number: number | null;
  episode_title: string | null;
  sort_order: number;
  duration_ms: number;
  status: VideoStatus;
};

export type SeriesDetail = Series & { videos: SeriesVideo[] };

export type VideoSummary = {
  id: number;
  title: string;
  description: string | null;
  series_id: number | null;
  series_title: string | null;
  episode_number: number | null;
  episode_title: string | null;
  sort_order: number;
  duration_ms: number;
  mime_type: string;
  file_size_bytes: number;
  status: VideoStatus;
  genres: { id: number; name: string }[];
  has_thumbnail: boolean;
  position_ms: number | null;
  completed: boolean;
  created_at: string;
  updated_at: string;
};

export type VideoDetail = VideoSummary & {
  chunk_count: number;
  play_count: number;
  last_played_at: string | null;
};

export type VideoCreateBody = {
  title: string;
  description?: string | null;
  series_id?: number | null;
  episode_number?: number | null;
  episode_title?: string | null;
  sort_order?: number;
  duration_ms: number;
  mime_type?: string;
  genre_ids?: number[];
};

export type VideoUpdateBody = {
  title?: string;
  description?: string | null;
  series_id?: number | null;
  episode_number?: number | null;
  episode_title?: string | null;
  sort_order?: number;
  genre_ids?: number[];
};

export type ListVideosQuery = {
  page: number;
  per_page?: number;
  genre_id?: number;
  series_id?: number;
  status?: "ready" | "uploading" | "error" | "all";
  q?: string;
  sort?: "created_at" | "title" | "last_played_at";
  order?: "asc" | "desc";
};

export type ChunkMeta = {
  chunk_index: number;
  start_time_ms: number;
  end_time_ms: number;
  byte_length: number;
};

export type PlaybackInfo = {
  id: number;
  title: string;
  duration_ms: number;
  mime_type: string;
  chunk_count: number;
  position_ms: number;
  completed: boolean;
  status: VideoStatus;
  start_chunk: ChunkMeta | null;
};

export type NextVideo = {
  has_next: boolean;
  video: {
    id: number;
    title: string;
    episode_number: number | null;
    sort_order: number;
    duration_ms: number;
    status: VideoStatus;
  } | null;
};

export type HistoryItem = {
  video_id: number;
  title: string;
  position_ms: number;
  completed: boolean;
  duration_ms: number;
  last_played_at: string;
};

export type LastPlayback = {
  video: {
    video_id: number;
    title: string;
    duration_ms: number;
    position_ms: number;
    updated_at: string;
  } | null;
  playlist: {
    playlist_id: number;
    playlist_name: string;
    item_id: number;
    video_id: number;
    video_title: string;
    duration_ms: number;
    position_ms: number;
    updated_at: string;
  } | null;
};

export type PlaylistSummary = {
  id: number;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export type PlaylistItem = {
  item_id: number;
  video_id: number;
  title: string;
  duration_ms: number;
  status: VideoStatus;
  has_thumbnail: boolean;
  sort_order: number;
};

export type PlaylistDetail = {
  id: number;
  name: string;
  description: string | null;
  items: PlaylistItem[];
  created_at: string;
  updated_at: string;
};

export type PlaylistPlaybackItem = {
  playlist_id: number;
  item_id: number;
  video_id: number;
  title: string;
  duration_ms: number;
  mime_type: string;
  status: VideoStatus;
  position_ms: number;
  sort_order: number;
  has_next: boolean;
  has_prev: boolean;
  start_chunk: ChunkMeta | null;
};

/** 動画登録・編集の共通の入力欄。 */
export type VideoMetaForm = {
  title: string;
  description: string;
  seriesId: number | null;
  newSeriesTitle: string;
  episodeNumber: number | null;
  episodeTitle: string;
  sortOrder: number;
  genreIds: number[];
};
