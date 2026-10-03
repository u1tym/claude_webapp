// 実際の API クライアント（fetch）を使う結合テストのための、API の代役。
// api モジュールは差し替えず、fetch だけを差し替える（URL・メソッド・本文・Cookie の送信まで確かめるため）。
import { vi } from "vitest";
import type { Category, Contract, Plan, PlanCandidate } from "../../src/api/types";

export type RequestRecord = { method: string; path: string; body: unknown; credentials: RequestCredentials | undefined };

export const SECRET_PASSWORD = "S3cret-Pass-Value";

export function contract(id: number, name: string, overrides: Partial<Contract> = {}): Contract {
  return {
    id, name, has_contract: true, category: { id: 1, name: "その他", is_financial: false }, status: "active",
    homepage: null, memo: null, login_methods: ["password"], twofa_mail_address: null, twofa_tel_number: null,
    username: `user${id}`, has_password: true, password_unset: false, registered_email: null, fee_amount: null,
    fee_cycle: null, renewal_date: null, contract_date: null, contract_date_precision: null, trial_end_date: null,
    end_date: null, auto_renewal: null, holder_name: null, member_number: null, cancel_notice_days: null,
    cancellation_fee: null, min_term_months: null, contact_phone: null, contact_email: null, contact_hours: null,
    cancellation_method: `解約方法${id}`, depends_on: [], payment_contract: null, depended_by: [], payment_for: [],
    ...overrides,
  };
}

export const CATEGORIES: Category[] = [
  { id: 1, name: "その他", is_default: true, is_financial: false },
  { id: 2, name: "銀行", is_default: false, is_financial: true },
];

export type FakeData = {
  contracts: Contract[];
  plan: Plan;
  candidates: PlanCandidate[];
};

export function defaultData(): FakeData {
  const contracts = [contract(1, "動画"), contract(2, "音楽", { has_password: false, password_unset: true })];
  return {
    contracts,
    plan: {
      items: [{ position: 1, contract_id: 1, name: "動画", cancellation_method: "解約方法1", depends_on: [] }],
      warnings: [],
    },
    candidates: [{ id: 2, name: "音楽", category_name: "その他", has_cancellation_method: true }],
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** fetch を差し替える。リクエストの記録を返す。 */
export function installFakeApi(data: FakeData = defaultData()): RequestRecord[] {
  const log: RequestRecord[] = [];
  vi.stubEnv("VITE_API_CONTRACT_MANAGEMENT_URL", "http://api.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const parsed = new URL(url);
      const path = parsed.pathname;
      const method = init.method ?? "GET";
      log.push({
        method,
        path: path + parsed.search,
        body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
        credentials: init.credentials,
      });
      if (path === "/settings") {
        return json({ login_url: "https://host/login", menu_url: "https://host/menu", icon_system: "", icon_back: "" });
      }
      if (path === "/accounts") {
        return json({
          total: data.contracts.length,
          items: data.contracts.map((c) => ({
            id: c.id, name: c.name, username: c.username, homepage: c.homepage, has_password: c.has_password, password_unset: c.password_unset,
          })),
        });
      }
      const password = /^\/contracts\/(\d+)\/password$/.exec(path);
      if (password) {
        return json({ password: SECRET_PASSWORD });
      }
      const one = /^\/contracts\/(\d+)$/.exec(path);
      if (one && method === "GET") {
        const found = data.contracts.find((c) => c.id === Number(one[1]));
        return found ? json(found) : json({ detail: "対象がありません" }, 404);
      }
      if (one && method === "PATCH") {
        const found = data.contracts.find((c) => c.id === Number(one[1]));
        return json({ ...found, ...(JSON.parse(String(init.body)) as object) });
      }
      if (path === "/contracts" && method === "GET") {
        return json({ total: data.contracts.length, items: data.contracts });
      }
      if (path === "/contracts" && method === "POST") {
        return json(contract(99, "登録した契約"), 201);
      }
      if (path === "/categories" && method === "GET") {
        return json({ items: CATEGORIES });
      }
      if (path === "/cancellation-plan" && method === "GET") {
        return json(data.plan);
      }
      if (path === "/cancellation-plan" && method === "PUT") {
        const ids = (JSON.parse(String(init.body)) as { contract_ids: number[] }).contract_ids;
        return json({
          items: ids.map((id, i) => ({ position: i + 1, contract_id: id, name: data.contracts.find((c) => c.id === id)?.name ?? "", cancellation_method: null, depends_on: [] })),
          warnings: [],
        });
      }
      if (path === "/cancellation-plan/candidates") {
        return json({ items: data.candidates });
      }
      return json({ detail: "対象がありません" }, 404);
    }),
  );
  return log;
}
