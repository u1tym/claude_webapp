ALTER TABLE expense_management.expenses
    ALTER COLUMN budget_item_id DROP NOT NULL;

ALTER TABLE expense_management.expenses
    ADD COLUMN IF NOT EXISTS budget_period_id integer NULL;

UPDATE expense_management.expenses e
SET budget_period_id = bi.budget_period_id
FROM expense_management.budget_items bi
WHERE e.budget_item_id = bi.id AND e.budget_period_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'expenses_budget_period_id_fkey'
    ) THEN
        ALTER TABLE expense_management.expenses
            ADD CONSTRAINT expenses_budget_period_id_fkey
                FOREIGN KEY (budget_period_id) REFERENCES expense_management.budget_periods (id) ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'expenses_budget_link_consistency'
    ) THEN
        ALTER TABLE expense_management.expenses
            ADD CONSTRAINT expenses_budget_link_consistency
                CHECK (budget_period_id IS NOT NULL OR budget_item_id IS NULL);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS expenses_user_budget_period_active_idx
    ON expense_management.expenses (user_id, budget_period_id)
    WHERE is_deleted = false;
