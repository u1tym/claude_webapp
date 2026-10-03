import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError } from "../src/api/client";
import type { Category, Contract, ContractFilters } from "../src/api/types";
import ContractsView from "../src/views/ContractsView.vue";

const listContracts = vi.fn<(filters?: ContractFilters) => Promise<Contract[]>>();
const listCategories = vi.fn<() => Promise<Category[]>>();

const getContract = vi.fn<(id: number) => Promise<Contract>>();
const getContractPassword = vi.fn<(id: number) => Promise<string | null>>();
const deleteContract = vi.fn<(id: number) => Promise<void>>();
const createContract = vi.fn<(input: unknown) => Promise<Contract>>();
const updateContract = vi.fn<(id: number, input: unknown) => Promise<Contract>>();

vi.mock("../src/api/contracts", () => ({
  deleteContract: (id: number) => deleteContract(id),
  createContract: (input: unknown) => createContract(input),
  updateContract: (id: number, input: unknown) => updateContract(id, input),
  listContracts: (f?: ContractFilters) => listContracts(f),
  getContract: (id: number) => getContract(id),
  getContractPassword: (id: number) => getContractPassword(id),
}));
vi.mock("../src/api/categories", () => ({ listCategories: () => listCategories() }));

const CATEGORIES: Category[] = [
  { id: 1, name: "その他", is_default: true, is_financial: false },
  { id: 2, name: "動画配信", is_default: false, is_financial: false },
];

function contract(id: number, overrides: Partial<Contract> = {}): Contract {
  return {
    id, name: `契約${id}`, has_contract: true, category: { id: 1, name: "その他", is_financial: false }, status: "active",
    homepage: null, memo: null, login_methods: [], twofa_mail_address: null, twofa_tel_number: null, username: null,
    has_password: false, password_unset: false, registered_email: null, fee_amount: null, fee_cycle: null,
    renewal_date: null, contract_date: null, contract_date_precision: null, trial_end_date: null, end_date: null,
    auto_renewal: null, holder_name: null, member_number: null, cancel_notice_days: null, cancellation_fee: null,
    min_term_months: null, contact_phone: null, contact_email: null, contact_hours: null, cancellation_method: null,
    depends_on: [], payment_contract: null, depended_by: [], payment_for: [], ...overrides,
  };
}

async function mountView(items: Contract[] = [contract(1), contract(2)]) {
  listContracts.mockResolvedValue(items);
  const wrapper = mount(ContractsView);
  await flushPromises();
  return wrapper;
}

function lastFilters(): ContractFilters {
  return listContracts.mock.calls.at(-1)?.[0] ?? {};
}

beforeEach(() => {
  listContracts.mockReset();
  listCategories.mockReset();
  listCategories.mockResolvedValue(CATEGORIES);
  getContract.mockReset();
  getContractPassword.mockReset();
  createContract.mockReset();
  updateContract.mockReset();
  deleteContract.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("契約一覧", () => {
  it("取得中は「読み込み中…」を出す", () => {
    listContracts.mockReturnValue(new Promise(() => undefined));
    expect(mount(ContractsView).text()).toContain("読み込み中…");
  });

  it("既定では、絞り込みなしで取得する（ステータスが解約の契約も表示する）", async () => {
    const wrapper = await mountView([contract(1), contract(2, { status: "cancelled" })]);
    expect(lastFilters()).toEqual({ keyword: "", category_id: null, status: "", has_contract: null, password_unset: false });
    expect(wrapper.findAll(".list-row")).toHaveLength(2);
    expect(wrapper.text()).toContain("解約");
  });

  it("名称・区分・ステータス・維持費・更新日を表示する。無いときは「-」", async () => {
    const wrapper = await mountView([
      contract(1, {
        name: "ネット動画", category: { id: 2, name: "動画配信", is_financial: false }, status: "paused",
        fee_amount: 12000, fee_cycle: "yearly", renewal_date: "2026-11-05",
      }),
      contract(2, { name: "アカウントだけ", has_contract: false }),
    ]);
    const [first, second] = wrapper.findAll(".list-row");
    expect(first?.findAll('[role="cell"]').map((c) => c.text())).toEqual(["ネット動画", "動画配信", "休止中", "年間 12,000 円", "2026年11月5日"]);
    expect(second?.findAll('[role="cell"]').map((c) => c.text())).toEqual(["アカウントだけ", "その他", "有効", "-", "-"]);
    expect(wrapper.findAll('[role="columnheader"]').map((c) => c.text())).toEqual(["名称", "区分", "ステータス", "維持費", "更新日"]);
  });

  it("パスワード未設定の契約には、名称の横に文字のバッジを付ける", async () => {
    const wrapper = await mountView([contract(1, { password_unset: true }), contract(2)]);
    const rows = wrapper.findAll(".list-row");
    expect(rows[0]?.get(".badge").text()).toBe("パスワード未設定");
    expect(rows[1]?.find(".badge").exists()).toBe(false);
  });

  it("区分の選択肢は、「すべて」と各区分。ステータス・契約の有無も選べる", async () => {
    const wrapper = await mountView();
    const options = (label: string) => wrapper.findAll(`select[aria-label="${label}"] option`).map((o) => o.text());
    expect(options("区分で絞り込む")).toEqual(["すべて", "その他", "動画配信"]);
    expect(options("ステータスで絞り込む")).toEqual(["すべて", "有効", "休止中", "解約"]);
    expect(options("契約の有無で絞り込む")).toEqual(["すべて", "契約を伴う", "契約を伴わない"]);
    expect(wrapper.text()).toContain("パスワード未設定のみ");
  });

  it("区分・ステータス・契約の有無・パスワード未設定の選択で、すぐに再取得する。組み合わせる", async () => {
    const wrapper = await mountView();
    await wrapper.get('select[aria-label="区分で絞り込む"]').setValue("2");
    await flushPromises();
    expect(lastFilters()).toMatchObject({ category_id: 2 });
    await wrapper.get('select[aria-label="ステータスで絞り込む"]').setValue("paused");
    await flushPromises();
    await wrapper.get('select[aria-label="契約の有無で絞り込む"]').setValue("false");
    await flushPromises();
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await flushPromises();
    expect(lastFilters()).toEqual({ keyword: "", category_id: 2, status: "paused", has_contract: false, password_unset: true });
    await wrapper.get('select[aria-label="契約の有無で絞り込む"]').setValue("true");
    await flushPromises();
    expect(lastFilters()).toMatchObject({ has_contract: true });
    await wrapper.get('select[aria-label="区分で絞り込む"]').setValue("");
    await flushPromises();
    expect(lastFilters()).toMatchObject({ category_id: null });
  });

  it("検索語の入力は、続く間は間引いて再取得する", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView();
    listContracts.mockClear();
    const input = wrapper.get('input[aria-label="検索"]');
    expect(input.attributes("placeholder")).toBe("検索");
    await input.setValue("n");
    await input.setValue("net");
    await vi.advanceTimersByTimeAsync(100);
    expect(listContracts).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    expect(listContracts).toHaveBeenCalledTimes(1);
    expect(lastFilters()).toMatchObject({ keyword: "net" });
  });

  it("0 件の文言は、絞り込み・検索の有無で変わる", async () => {
    const wrapper = await mountView([]);
    expect(wrapper.text()).toContain("データがありません");
    expect(wrapper.text()).not.toContain("該当するデータがありません");
    listContracts.mockResolvedValue([]);
    await wrapper.get('select[aria-label="ステータスで絞り込む"]').setValue("cancelled");
    await flushPromises();
    expect(wrapper.text()).toContain("該当するデータがありません");
    // 新規登録は、0 件でもできる（ボタンは常にある）
    expect(wrapper.find('button[aria-label="新規"]').exists()).toBe(true);
  });

  it("新規ボタンは、絞り込みから離して置く。アイコンのみで aria-label を持つ", async () => {
    const wrapper = await mountView();
    const button = wrapper.get('button[aria-label="新規"]');
    expect(button.classes()).toContain("toolbar-end");
    expect(button.find("svg.icon").exists()).toBe(true);
  });

  it("行は、名称を持つボタンで、選ぶと選択中になる", async () => {
    const wrapper = await mountView();
    const row = wrapper.get('button[aria-label="契約2の詳細を表示"]');
    expect(row.attributes("aria-pressed")).toBe("false");
    await row.trigger("click");
    expect(row.attributes("aria-pressed")).toBe("true");
    expect(wrapper.get('button[aria-label="契約1の詳細を表示"]').attributes("aria-pressed")).toBe("false");
  });

  it("古い応答は捨てる", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView([contract(1)]);
    let resolveSlow: (value: Contract[]) => void = () => undefined;
    listContracts.mockReturnValueOnce(new Promise((r) => (resolveSlow = r)));
    await wrapper.get('select[aria-label="ステータスで絞り込む"]').setValue("paused");
    listContracts.mockResolvedValueOnce([contract(9, { name: "新しい結果" })]);
    await wrapper.get('select[aria-label="ステータスで絞り込む"]').setValue("cancelled");
    await flushPromises();
    resolveSlow([contract(8, { name: "古い結果" })]);
    await flushPromises();
    expect(wrapper.text()).toContain("新しい結果");
    expect(wrapper.text()).not.toContain("古い結果");
  });

  it("取得の失敗は、内部理由を含まないメッセージ。401 / 403 は、メッセージを出さずに殻へ通知する", async () => {
    listContracts.mockRejectedValue(new Error("boom: internal"));
    const failed = mount(ContractsView);
    await flushPromises();
    expect(failed.get('[role="alert"]').text()).toBe("読み込みに失敗しました");
    expect(failed.text()).not.toContain("internal");

    listContracts.mockRejectedValue(new AuthError(403));
    const denied = mount(ContractsView);
    await flushPromises();
    expect(denied.find('[role="alert"]').exists()).toBe(false);
    expect((denied.emitted("auth-error")?.[0]?.[0] as AuthError).status).toBe(403);
  });

  it("区分の取得に失敗しても、一覧は表示する（メッセージを出す）", async () => {
    listCategories.mockRejectedValue(new Error("x"));
    const wrapper = await mountView();
    expect(wrapper.findAll(".list-row")).toHaveLength(2);
    expect(wrapper.get('[role="alert"]').text()).toBe("区分の読み込みに失敗しました");
  });

  it("行を選ぶと、詳細表示（モーダル）を開く。閉じるボタンと Esc で閉じる。背景では閉じない", async () => {
    listContracts.mockResolvedValue([contract(1, { name: "動画" }), contract(2)]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    const dialog = wrapper.get('[role="dialog"]');
    expect(dialog.attributes("aria-label")).toBe("動画の詳細");
    expect(dialog.get(".detail-title").text()).toBe("動画");
    await wrapper.get(".dialog-overlay").trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
    await wrapper.get('[aria-label="閉じる"]').trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    await wrapper.get('[role="dialog"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("関連する契約の名称を選ぶと、その契約の詳細に切り替える（一覧に無い契約も、取得して開く）", async () => {
    listContracts.mockResolvedValue([contract(1, { name: "動画", depends_on: [{ id: 8, name: "プロバイダ" }] })]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    getContract.mockResolvedValue(contract(8, { name: "プロバイダ" }));
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    await wrapper.get(".link-button").trigger("click");
    await flushPromises();
    expect(getContract).toHaveBeenCalledWith(8);
    expect(wrapper.get(".detail-title").text()).toBe("プロバイダ");
    wrapper.unmount();
  });

  it("関連する契約の取得に失敗したら、詳細を閉じて、メッセージを出す。401 は殻へ通知する", async () => {
    listContracts.mockResolvedValue([contract(1, { name: "動画", depends_on: [{ id: 8, name: "プロバイダ" }] })]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    getContract.mockRejectedValueOnce(new Error("x"));
    await wrapper.get(".link-button").trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(wrapper.get('[role="alert"]').text()).toBe("契約の読み込みに失敗しました");
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    getContract.mockRejectedValueOnce(new AuthError(401));
    await wrapper.get(".link-button").trigger("click");
    await flushPromises();
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
    wrapper.unmount();
  });

  it("新規ボタンで登録フォームを開く（詳細は開かない）。キャンセルで閉じる", async () => {
    listContracts.mockResolvedValue([contract(1)]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    expect(wrapper.get('[role="dialog"]').attributes("aria-label")).toBe("契約の新規登録");
    expect(wrapper.findAll('[role="dialog"]')).toHaveLength(1);
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("登録に成功したら、フォームを閉じ、成功メッセージを数秒出して、一覧を再取得する", async () => {
    vi.useFakeTimers();
    listContracts.mockResolvedValue([contract(1)]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    createContract.mockResolvedValue(contract(2, { name: "新規契約" }));
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    listContracts.mockClear(); // フォームの選択肢の取得は、数えない
    listContracts.mockResolvedValue([contract(1), contract(2, { name: "新規契約" })]);
    await wrapper.get('[aria-label="名称"]').setValue("新規契約");
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(createContract).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(wrapper.get('[role="status"]').text()).toBe("登録しました");
    expect(listContracts).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll(".list-row")).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(3100);
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("詳細の編集ボタンで、その契約の編集フォームを開く。更新に成功したら、閉じて「更新しました」を出す", async () => {
    listContracts.mockResolvedValue([contract(1, { name: "動画" })]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    await wrapper.get('[aria-label="編集"]').trigger("click");
    const dialog = wrapper.get('[role="dialog"]');
    expect(dialog.attributes("aria-label")).toBe("契約の編集");
    expect(wrapper.findAll('[role="dialog"]')).toHaveLength(1); // 詳細は閉じる
    expect((wrapper.get('[aria-label="名称"]').element as HTMLInputElement).value).toBe("動画");
    updateContract.mockResolvedValue(contract(1, { name: "動画2" }));
    await wrapper.get('[aria-label="名称"]').setValue("動画2");
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(updateContract).toHaveBeenCalledWith(1, expect.objectContaining({ name: "動画2" }));
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(wrapper.get('[role="status"]').text()).toBe("更新しました");
    wrapper.unmount();
  });

  it("フォームで 401 を受けたら、殻へ通知する", async () => {
    listContracts.mockResolvedValue([]);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    createContract.mockRejectedValue(new AuthError(401));
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await wrapper.get('[aria-label="名称"]').setValue("x");
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
    wrapper.unmount();
  });

  async function openDelete(items: Contract[], name: string) {
    listContracts.mockResolvedValue(items);
    const wrapper = mount(ContractsView, { attachTo: document.body });
    await flushPromises();
    await wrapper.get(`button[aria-label="${name}の詳細を表示"]`).trigger("click");
    await wrapper.get('[aria-label="削除"]').trigger("click");
    return wrapper;
  }

  it("詳細の削除ボタンで、詳細を閉じて、削除の確認ダイアログを開く。キャンセルでは何も起きない", async () => {
    const wrapper = await openDelete([contract(1, { name: "動画" }), contract(2)], "動画");
    const dialogs = wrapper.findAll('[role="dialog"]');
    expect(dialogs).toHaveLength(1);
    expect(dialogs[0]?.attributes("aria-label")).toBe("契約の削除");
    expect(dialogs[0]?.text()).toContain("「動画」を削除しますか？");
    await wrapper.get(".dialog-overlay").trigger("click"); // 背景では閉じない
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(deleteContract).not.toHaveBeenCalled();
    expect(wrapper.findAll(".list-row")).toHaveLength(2);
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("削除を確定すると、削除して一覧を再取得し、「削除しました」を数秒出す", async () => {
    vi.useFakeTimers();
    const wrapper = await openDelete([contract(1, { name: "動画" }), contract(2)], "動画");
    deleteContract.mockResolvedValue(undefined);
    listContracts.mockClear();
    listContracts.mockResolvedValue([contract(2)]);
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(deleteContract).toHaveBeenCalledWith(1);
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(listContracts).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll(".list-row")).toHaveLength(1);
    expect(wrapper.get('[role="status"]').text()).toBe("削除しました");
    await vi.advanceTimersByTimeAsync(3100);
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("削除に失敗したら、一文のメッセージを出す（本文の一文、またはそれが無いとき「削除に失敗しました」）。一覧は変えない", async () => {
    const wrapper = await openDelete([contract(1, { name: "動画" })], "動画");
    deleteContract.mockRejectedValueOnce(new ApiError(404, "対象がありません"));
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("対象がありません");
    expect(wrapper.findAll(".list-row")).toHaveLength(1);
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
    await wrapper.get('button[aria-label="動画の詳細を表示"]').trigger("click");
    await wrapper.get('[aria-label="削除"]').trigger("click");
    deleteContract.mockRejectedValueOnce(new Error("boom: internal"));
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("削除に失敗しました");
    expect(wrapper.text()).not.toContain("internal");
    wrapper.unmount();
  });

  it("削除で 401 を受けたら、メッセージを出さずに殻へ通知する", async () => {
    const wrapper = await openDelete([contract(1, { name: "動画" })], "動画");
    deleteContract.mockRejectedValueOnce(new AuthError(401));
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
    wrapper.unmount();
  });
});
