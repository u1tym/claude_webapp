# フォルダ構成

> 元Cursorルールでの適用範囲: 常時適用（参考情報）

## SPECのテンプレート

```
specs
└ templates
  ├ requirements-template.md
  ├ design-template.md
  ├ ui-design-template.md
  ├ db-design-template.md
  ├ api-design-template.md
  ├ tasks-template.md
  ├ frontend.env.example
  └ backend.env.example
```

## SPECのフォルダ構成

機能毎にまとめて作成する。
```
specs
└ <feature-name>
  ├ requirements.md
  ├ design.md
  ├ ui-design.md
  ├ db-design.md
  ├ api-design.md
  └ tasks.md
```

## 生成コードのフォルダ構成

```
src
└ features
  └ <feature-name>
    ├ backend     # venv/、.env、SQL、log/ を含む
    ├ frontend    # .env を含む
    └ tests       # 同一機能の backend は import してよい。venv は backend/venv を使う
```

nginx でフロントを出すときの公開 URL とディスク配置は `rules/17-nginx-deploy.md`。
