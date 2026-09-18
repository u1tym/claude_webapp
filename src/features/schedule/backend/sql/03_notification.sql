ALTER TABLE schedule.schedules
    ADD COLUMN IF NOT EXISTS needs_notification boolean NOT NULL DEFAULT false;

ALTER TABLE schedule.routines
    ADD COLUMN IF NOT EXISTS needs_notification boolean NOT NULL DEFAULT false;
