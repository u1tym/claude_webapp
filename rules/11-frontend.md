# フロントエンド実装方式

> 元Cursorルールでの適用範囲: `src/features/**/frontend/**/*.{vue,ts,css,scss}` を編集するとき

フロントエンドは、`src/features/<feature-name>/frontend/`に置く

## 利用技術

- フレームワーク: **Vue.js**
- 言語: **typescript**（`any`の安易な使用は避ける）
- デバッグ実行では、**このディレクトリ配下**で、`npm run dev`で起動できること
- nginxでデプロイすることを想定。公開 URL とディスク配置は `rules/17-nginx-deploy.md`（`base` は公開 URL、`createWebHistory(import.meta.env.BASE_URL)`）

## 画面の見た目

見た目（色・余白・部品の見た目）と、画面分割・ナビは `rules/15-ui-style.md` に従う。

他機能の Vue / CSS / コンポーネントを import しない。トークンが必要なら、この機能の `frontend/` に同じ値を置く。ナビもこの機能の `frontend/` に、同ルールの形と見た目で実装する。

## 設定値

この機能の `frontend/.env` から取得する。コードに平文で埋め込まない。

設定値として、代表的なものは以下
- APIの基点URL

### APIの基点URL

機能毎のAPI参照時のURLは、その機能専用の環境変数で設定する。
名称は、`VITE_API_<FEATURE>_URL` とする。

- `<FEATURE>` は機能名（`<feature-name>`）を大文字にし、ハイフンをアンダースコアにする
- 例: `voice` → `VITE_API_VOICE_URL`

`VITE_API_BASE_URL` や `API_BASE_URL` のような機能横断の名前は使わない。他機能の API 基点を流用しない。

API を呼ぶときは Cookie を送る（credentials を含める）。セッション ID を `localStorage` や URL に置かない。
