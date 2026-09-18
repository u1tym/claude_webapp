CREATE TABLE IF NOT EXISTS mail_notice.notified_schedules (
    schedule_id integer PRIMARY KEY,
    notified_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT notified_schedules_schedule_id_fkey
        FOREIGN KEY (schedule_id) REFERENCES schedule.schedules (id) ON DELETE RESTRICT
);
