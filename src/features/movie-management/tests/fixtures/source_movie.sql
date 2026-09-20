-- 移行元（sample/movie）の DB の構造を再現する。移行プログラムのテストでだけ使う。
-- DB_MOVIE_SPEC.md と sample/movie/backend/app/models.py に基づく。
-- チャンクの長さの検査（octet_length）は、不整合なデータを用意できるよう、あえて付けない。

CREATE SCHEMA movie;

CREATE TABLE public.accounts (
    id          serial PRIMARY KEY,
    username    varchar NOT NULL UNIQUE,
    is_deleted  boolean NOT NULL DEFAULT false
);

CREATE TABLE movie.genre (
    genre_id    serial PRIMARY KEY,
    aid         integer NULL,
    name        varchar(100) NOT NULL,
    sort_order  integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aid, name)
);

CREATE TABLE movie.series (
    series_id    serial PRIMARY KEY,
    aid          integer NOT NULL,
    title        varchar(500) NOT NULL,
    description  text NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE movie.video (
    video_id         bigserial PRIMARY KEY,
    aid              integer NOT NULL,
    series_id        integer NULL REFERENCES movie.series (series_id) ON DELETE SET NULL,
    title            varchar(500) NOT NULL,
    description      text NULL,
    episode_number   integer NULL,
    episode_title    varchar(500) NULL,
    sort_order       integer NOT NULL DEFAULT 0,
    duration_ms      bigint NOT NULL,
    mime_type        varchar(100) NOT NULL DEFAULT 'video/mp4',
    file_size_bytes  bigint NOT NULL DEFAULT 0,
    chunk_count      integer NOT NULL DEFAULT 0,
    status           varchar(20) NOT NULL DEFAULT 'uploading',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (series_id, episode_number)
);

CREATE TABLE movie.video_genre (
    video_id    bigint NOT NULL REFERENCES movie.video (video_id) ON DELETE CASCADE,
    genre_id    integer NOT NULL REFERENCES movie.genre (genre_id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, genre_id)
);

CREATE TABLE movie.video_chunk (
    chunk_id       bigserial PRIMARY KEY,
    video_id       bigint NOT NULL REFERENCES movie.video (video_id) ON DELETE CASCADE,
    chunk_index    integer NOT NULL,
    start_time_ms  bigint NOT NULL,
    end_time_ms    bigint NOT NULL,
    byte_length    integer NOT NULL,
    data           bytea NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (video_id, chunk_index)
);

CREATE TABLE movie.thumbnail (
    thumbnail_id  serial PRIMARY KEY,
    video_id      bigint NOT NULL UNIQUE REFERENCES movie.video (video_id) ON DELETE CASCADE,
    mime_type     varchar(50) NOT NULL DEFAULT 'image/jpeg',
    width         integer NULL,
    height        integer NULL,
    data          bytea NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE movie.playback_state (
    playback_id     bigserial PRIMARY KEY,
    aid             integer NOT NULL,
    video_id        bigint NOT NULL REFERENCES movie.video (video_id) ON DELETE CASCADE,
    position_ms     bigint NOT NULL DEFAULT 0,
    completed       boolean NOT NULL DEFAULT false,
    play_count      integer NOT NULL DEFAULT 0,
    last_played_at  timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aid, video_id)
);

CREATE TABLE movie.playlist (
    playlist_id  serial PRIMARY KEY,
    aid          integer NOT NULL,
    name         varchar(500) NOT NULL,
    description  text NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE movie.playlist_item (
    playlist_item_id  bigserial PRIMARY KEY,
    playlist_id       integer NOT NULL REFERENCES movie.playlist (playlist_id) ON DELETE CASCADE,
    video_id          bigint NOT NULL REFERENCES movie.video (video_id) ON DELETE CASCADE,
    sort_order        integer NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE movie.playback_context (
    aid                        integer PRIMARY KEY,
    last_video_id              bigint NULL REFERENCES movie.video (video_id) ON DELETE SET NULL,
    last_video_position_ms     bigint NOT NULL DEFAULT 0,
    last_video_updated_at      timestamptz NULL,
    last_playlist_id           integer NULL REFERENCES movie.playlist (playlist_id) ON DELETE SET NULL,
    last_playlist_item_id      bigint NULL REFERENCES movie.playlist_item (playlist_item_id) ON DELETE SET NULL,
    last_playlist_position_ms  bigint NOT NULL DEFAULT 0,
    last_playlist_updated_at   timestamptz NULL,
    updated_at                 timestamptz NOT NULL DEFAULT now()
);
