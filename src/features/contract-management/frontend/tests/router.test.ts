import { createMemoryHistory } from "vue-router";
import { describe, expect, it } from "vitest";
import { createAppRouter, routes } from "../src/router";

describe("ルート", () => {
  it("4 つの画面のルートが解決される（アカウント一覧が基点）", async () => {
    const router = createAppRouter(createMemoryHistory("/portal_contract_management/"));
    const cases: [string, string, string][] = [
      ["/", "accounts", "アカウント一覧"],
      ["/contracts", "contracts", "契約一覧"],
      ["/categories", "categories", "区分"],
      ["/cancellation", "cancellation", "解約順"],
    ];
    for (const [path, name, title] of cases) {
      await router.push(path);
      await router.isReady();
      expect(router.currentRoute.value.name).toBe(name);
      expect(router.currentRoute.value.meta.title).toBe(title);
    }
    expect(routes.map((r) => r.path)).toEqual(["/", "/contracts", "/categories", "/cancellation"]);
  });

  it("未定義のパスはどのルートにも一致しない", async () => {
    const router = createAppRouter(createMemoryHistory("/portal_contract_management/"));
    await router.push("/no-such-page");
    expect(router.currentRoute.value.matched).toHaveLength(0);
  });
});
