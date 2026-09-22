ALTER TABLE expense_management.expenses
    ADD COLUMN IF NOT EXISTS payment_date_is_auto boolean NOT NULL DEFAULT true;
