import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api/client";
import type { Contract } from "../src/api/types";
import ContractDetail from "../src/components/ContractDetail.vue";

const getContractPassword = vi.fn<(id: number) => Promise<string | null>>();
vi.mock("../src/api/contracts", () => ({ getContractPassword: (id: number) => getContractPassword(id) }));

let clipboard: string[];

function full(overrides: Partial<Contract> = {}): Contract {
  return {
    id: 1, name: "ネット動画", has_contract: true, category: { id: 2, name: "動画配信", is_financial: false }, status: "paused",
    homepage: "https://video.example.com", memo: "家族で共有\n二行目", login_methods: ["password", "2fa_mail", "2fa_tel"],
    twofa_mail_address: "2fa@example.com", twofa_tel_number: "090-1111-2222", username: "taro", has_password: true,
    password_unset: false, registered_email: "me@example.com", fee_amount: 990, fee_cycle: "monthly",
    renewal_date: "2026-11-05", contract_date: "2020-04", contract_date_precision: "month", trial_end_date: "2026-10-31",
    end_date: null, auto_renewal: true, holder_name: "山田 太郎", member_number: "A-123", cancel_notice_days: 7,
    cancellation_fee: "なし", min_term_months: 12, contact_phone: "0120-000-000", contact_email: "support@example.com",
    contact_hours: "平日 10:00-18:00", cancellation_method: "マイページ\nから解約",
    depends_on: [{ id: 8, name: "プロバイダ" }, { id: 9, name: "回線" }], payment_contract: { id: 5, name: "Aカード" },
    depended_by: [{ id: 20, name: "音楽" }], payment_for: [{ id: 30, name: "ジム" }], ...overrides,
  };
}

function noContract(overrides: Partial<Contract> = {}): Contract {
  return full({
    has_contract: false, status: "active", memo: null, login_methods: ["password"], twofa_mail_address: null,
    twofa_tel_number: null, fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null,
    contract_date_precision: null, trial_end_date: null, end_date: null, auto_renewal: null, holder_name: null,
    member_number: null, cancel_notice_days: null, cancellation_fee: null, min_term_months: null, contact_phone: null,
    contact_email: null, contact_hours: null, cancellation_method: null, depends_on: [], payment_contract: null,
    depended_by: [], payment_for: [], ...overrides,
  });
}

function open(contract: Contract) {
  return mount(ContractDetail, { props: { contract }, attachTo: document.body });
}

function rowText(wrapper: ReturnType<typeof open>, label: string): string {
  const row = wrapper.findAll(".detail-row").find((r) => r.get("dt").text() === label);
  if (!row) {
    throw new Error(`row not found: ${label}`);
  }
  return row.get("dd").text();
}

beforeEach(() => {
  clipboard = [];
  getContractPassword.mockReset();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(async (text: string) => void clipboard.push(text)) },
  });
});

describe("契約の詳細（契約を伴う契約）", () => {
  it("5 つの節（基本・ログイン・契約・問い合わせ先・関連）を表示する", () => {
    const wrapper = open(full());
    expect(wrapper.findAll("section").map((s) => s.attributes("aria-label"))).toEqual(["基本", "ログイン", "契約", "問い合わせ先", "関連"]);
    expect(wrapper.get(".detail-title").text()).toBe("ネット動画");
    expect(wrapper.get('[role="dialog"]').attributes("aria-label")).toBe("ネット動画の詳細");
    wrapper.unmount();
  });

  it("基本: 契約の有無・区分・ステータス・ホームページのリンク・メモ（改行を保つ）", () => {
    const wrapper = open(full());
    expect(rowText(wrapper, "契約")).toBe("契約を伴う");
    expect(rowText(wrapper, "区分")).toBe("動画配信");
    expect(rowText(wrapper, "ステータス")).toBe("休止中");
    const link = wrapper.get('a[href="https://video.example.com"]');
    expect(link.attributes()).toMatchObject({ target: "_blank", rel: "noopener noreferrer" });
    expect(wrapper.findAll(".detail-row").find((r) => r.get("dt").text() === "メモ")?.get("dd").classes()).toContain("pre");
    wrapper.unmount();
  });

  it("ホームページ・メモが無いときは、その行を出さない。http(s) 以外はリンクにしない", () => {
    const none = open(full({ homepage: null, memo: null }));
    expect(none.findAll(".detail-row").map((r) => r.get("dt").text())).not.toContain("ホームページ");
    expect(none.findAll(".detail-row").map((r) => r.get("dt").text())).not.toContain("メモ");
    none.unmount();
    const bad = open(full({ homepage: "javascript:alert(1)" }));
    expect(bad.find("a").exists()).toBe(false);
    bad.unmount();
  });

  it("ログイン: ログイン方法・2段階認証の送付先（設定されているものだけ）", () => {
    const wrapper = open(full());
    expect(rowText(wrapper, "ログイン方法")).toBe("ユーザ名とパスワード、2段階認証（メール）、2段階認証（TEL）");
    expect(rowText(wrapper, "2段階認証（メール）の送付先")).toBe("2fa@example.com");
    expect(rowText(wrapper, "2段階認証（TEL）の送付先")).toBe("090-1111-2222");
    wrapper.unmount();
    const only = open(full({ login_methods: ["passkey"], twofa_mail_address: null, twofa_tel_number: null }));
    const labels = only.findAll(".detail-row").map((r) => r.get("dt").text());
    expect(labels).not.toContain("2段階認証（メール）の送付先");
    expect(labels).not.toContain("2段階認証（TEL）の送付先");
    only.unmount();
  });

  it("契約: 維持費・日付・自動更新・名義・番号・受付期限・手数料・最低契約期間・解約方法を、定められた形式で表示する", () => {
    const wrapper = open(full());
    expect(rowText(wrapper, "維持費")).toBe("月額 990 円");
    expect(rowText(wrapper, "更新日")).toBe("2026年11月5日");
    expect(rowText(wrapper, "契約日")).toBe("2020年4月");
    expect(rowText(wrapper, "無料期間の終了日")).toBe("2026年10月31日");
    expect(rowText(wrapper, "契約終了日")).toBe("-");
    expect(rowText(wrapper, "自動更新")).toBe("あり");
    expect(rowText(wrapper, "契約者名義")).toBe("山田 太郎");
    expect(rowText(wrapper, "会員番号・契約番号")).toContain("A-123");
    expect(rowText(wrapper, "解約の受付期限")).toBe("更新日の 7 日前まで");
    expect(rowText(wrapper, "解約手数料・違約金")).toBe("なし");
    expect(rowText(wrapper, "最低契約期間")).toBe("12 か月");
    expect(rowText(wrapper, "解約方法")).toBe("マイページ\nから解約");
    expect(wrapper.findAll(".detail-row").find((r) => r.get("dt").text() === "解約方法")?.get("dd").classes()).toContain("pre");
    wrapper.unmount();
  });

  it("設定されていない項目は「-」。契約日が不明のときは「不明」", () => {
    const wrapper = open(
      full({
        fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null, contract_date_precision: "unknown",
        trial_end_date: null, auto_renewal: null, holder_name: null, member_number: null, cancel_notice_days: null,
        cancellation_fee: null, min_term_months: null, cancellation_method: null, contact_phone: null, contact_email: null,
        contact_hours: null, username: null, registered_email: null, login_methods: [],
      }),
    );
    for (const label of ["維持費", "更新日", "無料期間の終了日", "契約者名義", "会員番号・契約番号", "解約の受付期限", "解約手数料・違約金", "最低契約期間", "解約方法", "電話番号", "メールアドレス", "受付時間", "ユーザ名", "登録メールアドレス", "ログイン方法"]) {
      expect(rowText(wrapper, label), label).toBe("-");
    }
    expect(rowText(wrapper, "契約日")).toBe("不明");
    expect(rowText(wrapper, "自動更新")).toBe("未設定");
    wrapper.unmount();
  });

  it("関連: 依存契約・支払方法・依存されている契約・支払方法としている契約を、名称のリンクで表示する", async () => {
    const wrapper = open(full());
    expect(wrapper.findAll(".detail-row").find((r) => r.get("dt").text() === "依存契約")?.findAll(".link-button").map((b) => b.text())).toEqual(["プロバイダ", "回線"]);
    expect(rowText(wrapper, "支払方法")).toBe("Aカード");
    expect(rowText(wrapper, "この契約に依存している契約")).toBe("音楽");
    expect(rowText(wrapper, "この契約を支払方法としている契約")).toBe("ジム");
    await wrapper.findAll(".link-button").find((b) => b.text() === "回線")?.trigger("click");
    await wrapper.findAll(".link-button").find((b) => b.text() === "Aカード")?.trigger("click");
    await wrapper.findAll(".link-button").find((b) => b.text() === "ジム")?.trigger("click");
    expect(wrapper.emitted("open")).toEqual([[9], [5], [30]]);
    wrapper.unmount();
  });

  it("関連が無いときは「-」", () => {
    const wrapper = open(full({ depends_on: [], payment_contract: null, depended_by: [], payment_for: [] }));
    for (const label of ["依存契約", "支払方法", "この契約に依存している契約", "この契約を支払方法としている契約"]) {
      expect(rowText(wrapper, label)).toBe("-");
    }
    wrapper.unmount();
  });

  it("編集・削除・閉じるのボタン（アイコンのみ、aria-label 付き）。最初のフォーカスは閉じるに置く", async () => {
    const wrapper = open(full());
    await wrapper.vm.$nextTick();
    expect(document.activeElement).toBe(wrapper.get('[aria-label="閉じる"]').element);
    await wrapper.get('[aria-label="編集"]').trigger("click");
    await wrapper.get('[aria-label="削除"]').trigger("click");
    await wrapper.get('[aria-label="閉じる"]').trigger("click");
    await wrapper.get('[role="dialog"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("edit")).toHaveLength(1);
    expect(wrapper.emitted("delete")).toHaveLength(1);
    expect(wrapper.emitted("close")).toHaveLength(2);
    for (const label of ["編集", "削除", "閉じる"]) {
      expect(wrapper.get(`[aria-label="${label}"]`).find("svg.icon").exists()).toBe(true);
    }
    await wrapper.get(".dialog-overlay").trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(2); // 背景では閉じない
    wrapper.unmount();
  });
});

describe("契約の詳細（契約を伴わない契約）", () => {
  it("契約・問い合わせ先・依存契約・支払方法は出さない", () => {
    const wrapper = open(noContract());
    expect(wrapper.findAll("section").map((s) => s.attributes("aria-label"))).toEqual(["基本", "ログイン"]);
    expect(rowText(wrapper, "契約")).toBe("契約を伴わない");
    wrapper.unmount();
  });

  it("他の契約から参照されているとき（支払方法のカードなど）は、その逆引きだけを出す", () => {
    const wrapper = open(noContract({ payment_for: [{ id: 3, name: "動画" }], depended_by: [] }));
    expect(wrapper.findAll("section").map((s) => s.attributes("aria-label"))).toEqual(["基本", "ログイン", "関連"]);
    const labels = wrapper.findAll(".detail-row").map((r) => r.get("dt").text());
    expect(labels).not.toContain("依存契約");
    expect(labels).not.toContain("支払方法");
    expect(rowText(wrapper, "この契約を支払方法としている契約")).toBe("動画");
    wrapper.unmount();
  });
});

describe("パスワードの扱い", () => {
  it("既定ではマスク表示で、取得しない。「表示」「コピー」の操作時に取得する", async () => {
    getContractPassword.mockResolvedValue("S3cret-Pass");
    const wrapper = open(full({ id: 42 }));
    expect(getContractPassword).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
    expect(wrapper.html()).not.toContain("S3cret-Pass");
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(getContractPassword).toHaveBeenCalledWith(42);
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("S3cret-Pass");
    await wrapper.get('[aria-label="パスワードを隠す"]').trigger("click");
    expect(wrapper.html()).not.toContain("S3cret-Pass");
    await wrapper.get('[aria-label="パスワードをコピー"]').trigger("click");
    await flushPromises();
    expect(clipboard).toEqual(["S3cret-Pass"]);
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••"); // マスク中でもコピーできる
    wrapper.unmount();
  });

  it("未設定のときは「パスワード未設定」だけを出す。パスワードを使わない契約は「-」", () => {
    const unset = open(full({ has_password: false, password_unset: true }));
    expect(rowText(unset, "パスワード")).toBe("パスワード未設定");
    expect(unset.findAll('[aria-label^="パスワード"]')).toHaveLength(0);
    unset.unmount();
    const unused = open(full({ has_password: false, password_unset: false, login_methods: ["passkey"] }));
    expect(rowText(unused, "パスワード")).toBe("-");
    unused.unmount();
  });

  it("ユーザ名・登録メールアドレス・会員番号・電話番号・問い合わせ先のメールアドレスをコピーできる", async () => {
    const wrapper = open(full());
    for (const label of ["ユーザ名をコピー", "登録メールアドレスをコピー", "会員番号・契約番号をコピー", "電話番号をコピー", "問い合わせ先のメールアドレスをコピー"]) {
      await wrapper.get(`[aria-label="${label}"]`).trigger("click");
      await flushPromises();
    }
    expect(clipboard).toEqual(["taro", "me@example.com", "A-123", "0120-000-000", "support@example.com"]);
    wrapper.unmount();
  });

  it("取得の失敗は、ダイアログ内に一文を出す（401 / 403 は殻へ通知し、メッセージは出さない）", async () => {
    const wrapper = open(full());
    getContractPassword.mockRejectedValueOnce(new Error("x"));
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("操作に失敗しました");
    expect(wrapper.get('[data-testid="password-value"]').text()).toBe("••••••••");
    wrapper.unmount();

    const denied = open(full());
    getContractPassword.mockRejectedValueOnce(new AuthError(401));
    await denied.get('[aria-label="パスワードをコピー"]').trigger("click");
    await flushPromises();
    expect(denied.find('[role="alert"]').exists()).toBe(false);
    expect((denied.emitted("error")?.[0]?.[0] as AuthError).status).toBe(401);
    denied.unmount();
  });
});
