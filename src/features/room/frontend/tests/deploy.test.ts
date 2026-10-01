import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// vitest は frontend/ を作業フォルダにして動く。import.meta.url は Vite の base に置き換わるため使わない
const path = (relative: string): string => resolve(process.cwd(), relative);
const read = (relative: string): string => readFileSync(path(relative), "utf-8");

/** nginx の設定から、コメントを除いた行だけを返す。 */
function directives(conf: string): string[] {
  return conf
    .split("\n")
    .map((line) => line.replace(/#.*/, "").trim())
    .filter((line) => line !== "");
}

describe("Vite の設定（公開 URL）", () => {
  const config = read("vite.config.ts");

  it("base は公開 URL /portal_room/（末尾にスラッシュ）", () => {
    expect(config).toMatch(/base:\s*"\/portal_room\/"/);
  });

  it("ディスクのパスや別名を base にしていない", () => {
    expect(config).not.toContain("/features/room/");
    expect(config).not.toContain("/feature_room/");
  });

  it("Vue Router は BASE_URL を使う", () => {
    expect(read("src/router.ts")).toContain("createWebHistory(import.meta.env.BASE_URL)");
  });
});

describe("nginx の設定例（rules/17-nginx-deploy.md）", () => {
  const conf = read("nginx.example.conf");
  const lines = directives(conf);
  const text = lines.join("\n");

  it("スラッシュなしの /portal_room は、スラッシュ付きへ 301 で転送する", () => {
    expect(text).toContain("location = /portal_room {");
    expect(text).toContain("return 301 /portal_room/;");
  });

  it("公開 URL /portal_room/ を、ディスクの features/room/ へ rewrite ... last で対応づける", () => {
    expect(text).toContain("location /portal_room/ {");
    expect(text).toContain("rewrite ^/portal_room/(.*)$ /features/room/$1 last;");
  });

  it("rewrite に break を使わない", () => {
    expect(text).not.toMatch(/rewrite .* break;/);
    expect(text).not.toMatch(/^break;/m);
  });

  it("ディスク側の location は internal で、index.html へフォールバックする", () => {
    const block = text.slice(text.indexOf("location /features/room/ {"));
    expect(block).toContain("internal;");
    expect(block).toContain("try_files $uri /features/room/index.html;");
  });

  it("try_files と rewrite break を同じ location に置かない", () => {
    // try_files を持つ location には rewrite を置かない
    const portal = text.slice(
      text.indexOf("location /portal_room/ {"),
      text.indexOf("location /features/room/ {"),
    );
    expect(portal).not.toContain("try_files");
    const features = text.slice(text.indexOf("location /features/room/ {"));
    expect(features.split("}")[0]).not.toContain("rewrite");
  });

  it("$uri/ を使わない", () => {
    expect(text).not.toContain("$uri/");
  });

  it("公開 URL はアンダースコア名で、ディスクはハイフンの機能名（features/room/）", () => {
    expect(text).toContain("/portal_room");
    expect(text).not.toContain("/feature_room/");
    expect(text).not.toContain("/portal-room/");
  });

  it("API を同一オリジンで中継するときは、バックエンドの待ち受け（8011）へ渡す", () => {
    expect(text).toContain("location /portal-room-api/ {");
    expect(text).toContain("proxy_pass http://127.0.0.1:8011/;");
    expect(text).toContain("proxy_set_header Host $host;");
  });

  it("括弧の対応が取れている", () => {
    const open = (text.match(/{/g) ?? []).length;
    const close = (text.match(/}/g) ?? []).length;
    expect(open).toBe(close);
  });
});

// ビルド済みの成果物があるときだけ確認する（npm run build のあと）
describe.skipIf(!existsSync(path("dist/index.html")))("ビルド成果物（dist）", () => {
  const html = read("dist/index.html");

  it("JS・CSS は公開 URL /portal_room/ 配下を指す", () => {
    const urls = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]);
    expect(urls.length).toBeGreaterThan(0);
    for (const url of urls) {
      expect(url).toMatch(/^\/portal_room\/assets\//);
    }
  });

  it("ディスクのパス（/features/room/）を含まない", () => {
    expect(html).not.toContain("/features/room/");
  });
});
