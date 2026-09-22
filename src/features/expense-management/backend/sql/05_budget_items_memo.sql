ALTER TABLE expense_management.budget_items
    ADD COLUMN IF NOT EXISTS memo text NULL;
