-- Normalize lead_* temporal columns to timezone-aware storage.
-- Assumption: existing naive timestamps are already UTC; convert with AT TIME ZONE 'UTC'.

DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name LIKE 'lead\_%' ESCAPE '\'
          AND data_type = 'timestamp without time zone'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE TIMESTAMPTZ USING %I AT TIME ZONE ''UTC''',
            rec.table_name,
            rec.column_name,
            rec.column_name
        );
    END LOOP;
END $$;
