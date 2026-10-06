-- 定期実行のタイトルと表示順。
-- すでに room.room_schedules がある DB へ、タイトルと表示順の列を足す。空の DB でも、01〜03 のあとに適用して同じ結果になる。
-- 繰り返し適用しても壊れない（列は IF NOT EXISTS、制約は付け替え、インデックスは IF NOT EXISTS）。既存のデータは変換しない。

-- 1. 列を足す。既存の行は、すべて NULL（タイトル無し、表示順なし）になる
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS title varchar(50) NULL;
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS display_order integer NULL;

-- 2. 制約を付け替える
-- タイトルは、あれば 1〜50 文字で、前後に空白を持たない（空の入力は NULL にする）
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_title_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_title_check
    CHECK (title IS NULL OR (char_length(title) BETWEEN 1 AND 50 AND title = btrim(title)));

ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_display_order_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_display_order_check
    CHECK (display_order IS NULL OR display_order BETWEEN 0 AND 9999);

-- 3. 一覧の並び（ORDER BY display_order ASC NULLS LAST, run_time, id）のためのインデックス
CREATE INDEX IF NOT EXISTS ix_room_schedules_display_order
    ON room.room_schedules (display_order, run_time, id);
