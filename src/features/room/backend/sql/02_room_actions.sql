-- 定期実行の改訂（実行内容・祝日の扱い・実行日の取り方）。
-- すでに room.room_schedules がある DB を、新しい定義へ移行する。空の DB でも、01 のあとに適用して同じ結果になる。
-- 繰り返し適用しても壊れない（列は IF NOT EXISTS、制約は付け替え、変換は 1 回目だけ効く）。

-- 1. 列を足す。既存の行は、「一括切替・祝日は関係しない・当日」になる
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS holiday_mode varchar(8) NOT NULL DEFAULT 'none';
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS day_shift varchar(8) NOT NULL DEFAULT 'same';
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS action_type varchar(8) NOT NULL DEFAULT 'scene';
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS device varchar(16) NULL;
ALTER TABLE room.room_schedules
    ADD COLUMN IF NOT EXISTS target_state varchar(3) NULL;

-- 2. 機器の個別切替のとき、scene は NULL になる
ALTER TABLE room.room_schedules
    ALTER COLUMN scene DROP NOT NULL;

-- 3. 従来の実行条件「祝日の指定」（holiday）を、無効にして、全曜日の「曜日の指定」へ変換する。
--    祝日だけに実行していたものが、全曜日の定義になり、意味が変わるため、必ず無効にして残す。
--    利用者が、内容（曜日と祝日の扱い）を見直して、有効にする。
--    実行条件の制約を付け替える前に行う（付け替えのあとでは、holiday の行が制約に反する）。
INSERT INTO room.schedule_weekdays (schedule_id, weekday)
SELECT s.id, d.weekday
FROM room.room_schedules s
CROSS JOIN generate_series(1, 7) AS d(weekday)
WHERE s.condition_type = 'holiday'
ON CONFLICT DO NOTHING;

UPDATE room.room_schedules
SET condition_type = 'weekdays',
    holiday_mode = 'none',
    day_shift = 'same',
    is_enabled = false,
    updated_at = now()
WHERE condition_type = 'holiday';

-- 4. 制約を付け替える（実行条件から holiday を外し、新しい列の制約と、整合の制約を足す）
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_condition_type_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_condition_type_check
    CHECK (condition_type IN ('daily', 'weekdays'));

ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_holiday_mode_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_holiday_mode_check
    CHECK (holiday_mode IN ('none', 'include', 'exclude'));

ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_day_shift_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_day_shift_check
    CHECK (day_shift IN ('same', 'before', 'after'));

-- 毎日のときは、祝日の扱いと実行日の取り方を付けない
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_daily_plain_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_daily_plain_check
    CHECK (condition_type = 'weekdays' OR (holiday_mode = 'none' AND day_shift = 'same'));

ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_action_type_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_action_type_check
    CHECK (action_type IN ('scene', 'device'));

-- 機器の個別切替の機器。玄関ドアは含めない
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_device_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_device_check
    CHECK (device IN ('ceiling_light', 'indirect_light', 'indoor_speaker', 'bedside_speaker'));

ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_target_state_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_target_state_check
    CHECK (target_state IN ('on', 'off'));

-- 実行内容の種類に応じた列だけが入る
ALTER TABLE room.room_schedules DROP CONSTRAINT IF EXISTS room_schedules_action_consistency_check;
ALTER TABLE room.room_schedules
    ADD CONSTRAINT room_schedules_action_consistency_check
    CHECK (
        (action_type = 'scene' AND scene IS NOT NULL AND device IS NULL AND target_state IS NULL)
        OR
        (action_type = 'device' AND scene IS NULL AND device IS NOT NULL AND target_state IS NOT NULL)
    );
