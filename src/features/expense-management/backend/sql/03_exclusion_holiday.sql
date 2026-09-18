ALTER TABLE expense_management.payment_method_exclusions
    DROP CONSTRAINT IF EXISTS payment_method_exclusions_kind_check;

ALTER TABLE expense_management.payment_method_exclusions
    ADD CONSTRAINT payment_method_exclusions_kind_check CHECK (
        exclusion_kind IN (
            'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
            'nonexistent_day', 'holiday'
        )
    );
