# nginx デプロイ（フロント）

> 元Cursorルールでの適用範囲: 常時適用（公開URLとディスク配置）

機能名はディレクトリどおり kebab-case（`<feature-name>`）。公開 URL 用の名前はハイフンをアンダースコアにする。

| | 規則 | 例（`user-management`） |
|---|---|---|
| ディスク | ドキュメントルートの `features/<feature-name>/` | `/var/www/html/features/user-management/` |
| 公開 URL | `/portal_<アンダースコア名>/` | `/portal_user_management/` |

`dist` はディスク側へコピーする。ブラウザでは公開 URL を開く。ディスク側のパスを URL として開かない。

## Vite / Vue Router

- `base` は公開 URL（末尾 `/`）
- `createWebHistory(import.meta.env.BASE_URL)`

```ts
// ✅ GOOD
base: "/portal_user_management/"

// ❌ BAD: ディスクパスや別名
base: "/features/user-management/"
base: "/feature_user_management/"
```

## nginx

`rewrite` は `last`。`break` と `try_files` を同じ location に置かない（JS/CSS が HTML になる）。`$uri/` は使わない。

`location /portal_user_management/` は末尾 `/` 付きだけにマッチする。スラッシュなしは 301 で付ける。

```nginx
location = /portal_user_management {
    return 301 /portal_user_management/;
}

location /portal_user_management/ {
    rewrite ^/portal_user_management/(.*)$ /features/user-management/$1 last;
}

location /features/user-management/ {
    internal;
    try_files $uri /features/user-management/index.html;
}
```

機能マスタの遷移先 URL も公開 URL に合わせる（例: `https://<ホスト>/portal_user_management/users`）。末尾 `/` の有無も公開 URL と揃える。

`return 301 /portal_user_management/;` はクエリを引き継がない。スラッシュなし（例: `/portal_schedule?a=1`）へ来ると `/portal_schedule/` になり `?a=` は消える。ポータルメニューのキャッシュ回避クエリがこれに当たる。対応は未決（`specs/portal/design.md` の未決事項）。引き継ぐなら `return 301 /portal_user_management/$is_args$args;`。

## 例外

機能 `portal` は既存どおり。公開 URL は `/portal/`、ディスクはドキュメントルートの `portal/`。
