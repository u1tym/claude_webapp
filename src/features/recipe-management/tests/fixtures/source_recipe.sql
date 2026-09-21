-- 移行元（sample/recipe）の DB の構造を再現する。移行プログラムのテストでだけ使う。
-- sample/recipe/backend/db/db.sql に基づく。
-- 材料・分量名称への参照制約（外部キー）は、存在しない材料を指す行の扱いを確かめられるよう、あえて付けない。

CREATE SCHEMA recipe;

CREATE TABLE recipe.ingredient (
    id    serial PRIMARY KEY,
    name  text NOT NULL,
    kana  text NOT NULL,
    UNIQUE (name)
);

CREATE TABLE recipe.measurements (
    id           serial PRIMARY KEY,
    name_bef     text NOT NULL,
    name_aft     text NOT NULL,
    ness_amount  boolean NOT NULL,
    UNIQUE (name_bef, name_aft)
);

CREATE TABLE recipe.menu (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    kana        text NOT NULL,
    is_deleted  boolean NOT NULL DEFAULT false,
    UNIQUE (name)
);

CREATE TABLE recipe.menu_step (
    id           serial PRIMARY KEY,
    menu_id      integer NOT NULL REFERENCES recipe.menu (id),
    step         integer NOT NULL,
    description  text NOT NULL,
    UNIQUE (menu_id, step)
);

CREATE TABLE recipe.menu_step_ingredient (
    id              serial PRIMARY KEY,
    menu_step_id    integer NOT NULL REFERENCES recipe.menu_step (id),
    ingredient_id   integer NOT NULL,
    measurement_id  integer NOT NULL,
    amount          text NOT NULL
);
