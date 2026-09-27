ALTER TABLE expense_management.payment_methods
    ADD COLUMN IF NOT EXISTS is_credit boolean NOT NULL DEFAULT false;

ALTER TABLE expense_management.payment_methods
    ADD COLUMN IF NOT EXISTS is_credit_payment boolean NOT NULL DEFAULT false;

ALTER TABLE expense_management.payment_methods
    DROP CONSTRAINT IF EXISTS payment_methods_credit_exclusive;

ALTER TABLE expense_management.payment_methods
    ADD CONSTRAINT payment_methods_credit_exclusive CHECK (NOT (is_credit AND is_credit_payment));
