ALTER TABLE expense_management.budget_periods
    ADD COLUMN IF NOT EXISTS title varchar(255);

UPDATE expense_management.budget_periods
SET title = to_char(start_date, 'YYYY-MM-DD') || '〜' || to_char(end_date, 'YYYY-MM-DD')
WHERE title IS NULL;

ALTER TABLE expense_management.budget_periods
    ALTER COLUMN title SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'budget_periods_title_not_empty'
    ) THEN
        ALTER TABLE expense_management.budget_periods
            ADD CONSTRAINT budget_periods_title_not_empty CHECK (char_length(title) > 0);
    END IF;
END $$;
