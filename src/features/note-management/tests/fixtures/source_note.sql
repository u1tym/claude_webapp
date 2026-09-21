-- 移行元（sample/note）の DB の構造を再現する。移行プログラムのテストでだけ使う。
-- sample/note/DB_NOTE_SPEC.md と、実際の移行元の列の型（ptype は text）に基づく。表（table）のテーブルも含める。

CREATE TABLE public.accounts (
    id        serial PRIMARY KEY,
    username  text NOT NULL UNIQUE
);

CREATE SCHEMA note;

CREATE TABLE note.folder (
    id              serial PRIMARY KEY,
    aid             integer NOT NULL REFERENCES public.accounts (id),
    parent          integer NULL REFERENCES note.folder (id),
    name            text NOT NULL,
    dorder          integer NOT NULL,
    deleted_number  integer NOT NULL DEFAULT 0,
    UNIQUE (aid, parent, deleted_number, name),
    UNIQUE (aid, parent, dorder)
);

CREATE TABLE note.file (
    id              serial PRIMARY KEY,
    aid             integer NOT NULL REFERENCES public.accounts (id),
    belong          integer NOT NULL REFERENCES note.folder (id),
    title           text NOT NULL,
    dorder          integer NOT NULL,
    deleted_number  integer NOT NULL DEFAULT 0,
    UNIQUE (aid, belong, deleted_number, title),
    UNIQUE (aid, belong, dorder)
);

CREATE TABLE note.parts (
    id           serial PRIMARY KEY,
    aid          integer NOT NULL REFERENCES public.accounts (id),
    file         integer NOT NULL REFERENCES note.file (id),
    dorder       integer NOT NULL,
    is_deleted   boolean NOT NULL,
    ptype        text NOT NULL,
    data         text NOT NULL,
    filename     text NOT NULL DEFAULT '',
    title        text NOT NULL DEFAULT '',
    markers      text NOT NULL DEFAULT '[]',
    image_scale  real NOT NULL DEFAULT 1.0,
    UNIQUE (aid, file, dorder)
);

CREATE TABLE note.parts_revision (
    id               serial PRIMARY KEY,
    aid              integer NOT NULL REFERENCES public.accounts (id),
    parts_id         integer NOT NULL REFERENCES note.parts (id),
    revision_number  integer NOT NULL,
    filename         text NOT NULL,
    ptype            text NOT NULL,
    data             text NOT NULL,
    created_at       timestamp NOT NULL DEFAULT now(),
    UNIQUE (parts_id, revision_number)
);

CREATE TABLE note."table" (
    id         serial PRIMARY KEY,
    aid        integer NOT NULL REFERENCES public.accounts (id),
    row_count  integer NOT NULL DEFAULT 5,
    col_count  integer NOT NULL DEFAULT 5,
    title      text NOT NULL DEFAULT ''
);

CREATE TABLE note.table_cell (
    id              serial PRIMARY KEY,
    table_id        integer NOT NULL REFERENCES note."table" (id) ON DELETE CASCADE,
    x               integer NOT NULL,
    y               integer NOT NULL,
    cell_type       text NOT NULL,
    input_value     text NOT NULL,
    display_format  text NOT NULL,
    display_value   text NOT NULL,
    text_align      text NOT NULL,
    UNIQUE (table_id, x, y)
);

CREATE TABLE note.table_col_width (
    id        serial PRIMARY KEY,
    table_id  integer NOT NULL REFERENCES note."table" (id) ON DELETE CASCADE,
    x         integer NOT NULL,
    width_px  integer NOT NULL,
    UNIQUE (table_id, x)
);

CREATE TABLE note.checklist (
    id     serial PRIMARY KEY,
    aid    integer NOT NULL REFERENCES public.accounts (id),
    title  text NOT NULL DEFAULT ''
);

CREATE TABLE note.checklist_category (
    id            serial PRIMARY KEY,
    checklist_id  integer NOT NULL REFERENCES note.checklist (id) ON DELETE CASCADE,
    name          text NOT NULL DEFAULT '',
    dorder        integer NOT NULL DEFAULT 0,
    is_deleted    boolean NOT NULL DEFAULT false
);

CREATE TABLE note.checklist_item (
    id            serial PRIMARY KEY,
    checklist_id  integer NOT NULL REFERENCES note.checklist (id) ON DELETE CASCADE,
    category_id   integer NOT NULL REFERENCES note.checklist_category (id) ON DELETE CASCADE,
    title         text NOT NULL DEFAULT '',
    is_checked    boolean NOT NULL DEFAULT false,
    dorder        integer NOT NULL DEFAULT 0,
    is_deleted    boolean NOT NULL DEFAULT false
);
