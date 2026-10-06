-- 電灯の調光（固定 4 種の調光パターン）。
-- すでに room.room_schedules がある DB へ、調光パターンの列を足す。空の DB でも、01・02 のあとに適用して同じ結果になる。
-- 繰り返し適用しても壊れない（列は IF NOT EXISTS、制約は付け替え）。既存のデータは変換しない。

-- 1. 列を足す。既存の行は、すべて NULL（既定のパターン = 全灯）になる。
--    調光パターンは、電灯を ON にする個別切替のときだけ持つ。明るさと色温度の値は持たない（コードの定数）
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS dimming_pattern varchar(16) NULL;

-- 2. 制約を付け替える
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_dimming_pattern_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_dimming_pattern_check
    CHECK (dimming_pattern IN ('full', 'reading', 'relax', 'night'));

-- 調光パターンは、電灯を ON にする個別切替のときだけ
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_dimming_consistency_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_dimming_consistency_check
    CHECK (
        dimming_pattern IS NULL
        OR (action_type = 'device' AND device = 'ceiling_light' AND target_state = 'on')
    );
