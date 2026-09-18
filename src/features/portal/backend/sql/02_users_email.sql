ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS email varchar(255) NOT NULL DEFAULT '';
