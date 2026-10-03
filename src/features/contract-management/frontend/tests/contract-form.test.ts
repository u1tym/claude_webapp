import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError } from "../src/api/client";
import type { Category, Contract, ContractInput } from "../src/api/types";
import ContractForm from "../src/components/ContractForm.vue";

const createContract = vi.fn<(input: ContractInput) => Promise<Contract>>();
const updateContract = vi.fn<(id: number, input: ContractInput) => Promise<Contract>>();
const listContracts = vi.fn<() => Promise<Contract[]>>();
vi.mock("../src/api/contracts", () => ({
  listContracts: () => listContracts(),
  createContract: (input: ContractInput) => createContract(input),
  updateContract: (id: number, input: ContractInput) => updateContract(id, input),
}));

const CATEGORIES: Category[] = [
  { id: 1, name: "その他", is_default: true, is_financial: false },
  { id: 2, name: "動画配信", is_default: false, is_financial: false },
];

function contract(overrides: Partial<Contract> = {}): Contract {
  return {
    id: 7, name: "ネット動画", has_contract: true, category: { id: 2, name: "動画配信", is_financial: false }, status: "active",
    homepage: "https://video.example.com", memo: "メモ", login_methods: ["password", "2fa_mail"], twofa_mail_address: "2fa@example.com",
    twofa_tel_number: null, username: "taro", has_password: true, password_unset: false, registered_email: "me@example.com",
    fee_amount: 990, fee_cycle: "monthly", renewal_date: "2026-11-05", contract_date: "2020-04", contract_date_precision: "month",
    trial_end_date: "2026-10-31", end_date: null, auto_renewal: true, holder_name: "山田", member_number: "A-1",
    cancel_notice_days: 7, cancellation_fee: "なし", min_term_months: 12, contact_phone: "0120", contact_email: "s@example.com",
    contact_hours: "平日", cancellation_method: "マイページ", depends_on: [{ id: 8, name: "プロバイダ" }],
    payment_contract: { id: 5, name: "Aカード" }, depended_by: [], payment_for: [], ...overrides,
  };
}

function open(existing?: Contract) {
  return mount(ContractForm, { props: { contract: existing, categories: CATEGORIES }, attachTo: document.body });
}

type Wrapper = ReturnType<typeof open>;

async function type(wrapper: Wrapper, label: string, value: string): Promise<void> {
  await wrapper.get(`[aria-label="${label}"]`).setValue(value);
}

async function submit(wrapper: Wrapper): Promise<void> {
  await wrapper.get('[aria-label="保存"]').trigger("click");
  await flushPromises();
}

function sent(): ContractInput {
  return createContract.mock.calls.at(-1)?.[0] as ContractInput;
}

function sentUpdate(): { id: number; input: ContractInput } {
  const call = updateContract.mock.calls.at(-1) as [number, ContractInput];
  return { id: call[0], input: call[1] };
}

beforeEach(() => {
  createContract.mockReset();
  updateContract.mockReset();
  listContracts.mockReset();
  listContracts.mockResolvedValue([]);
  document.body.innerHTML = "";
});

describe("登録フォーム", () => {
  it("既定は、契約を伴う・ステータスは有効・区分は「その他」。パスワード欄は空", async () => {
    const wrapper = open();
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[role="dialog"]').attributes("aria-label")).toBe("契約の新規登録");
    const radios = wrapper.findAll('input[name="has_contract"]').map((r) => (r.element as HTMLInputElement).checked);
    expect(radios).toEqual([true, false]);
    expect((wrapper.get('[aria-label="ステータス"]').element as HTMLSelectElement).value).toBe("active");
    expect((wrapper.get('[aria-label="区分"]').element as HTMLSelectElement).value).toBe("1");
    expect((wrapper.get('[aria-label="パスワード"]').element as HTMLTextAreaElement).placeholder).toBe("");
    expect(wrapper.findAll('[aria-label="区分"] option').map((o) => o.text())).toEqual(["その他", "動画配信"]);
    expect(wrapper.findAll('[aria-label="ステータス"] option').map((o) => o.text())).toEqual(["有効", "休止中", "解約"]);
    expect(document.activeElement).toBe(wrapper.get('[aria-label="名称"]').element); // 最初のフォーカスは名称
    wrapper.unmount();
  });

  it("名称だけで登録できる（空の項目は null、パスワードは送らない）", async () => {
    createContract.mockResolvedValue(contract());
    const wrapper = open();
    await type(wrapper, "名称", "  名称だけ  ");
    await submit(wrapper);
    expect(createContract).toHaveBeenCalledTimes(1);
    const input = sent();
    expect(input).toMatchObject({
      name: "名称だけ", has_contract: true, category_id: 1, status: "active", homepage: null, memo: null,
      login_methods: [], twofa_mail_address: null, twofa_tel_number: null, username: null, registered_email: null,
      fee_amount: null, depends_on_ids: [], payment_contract_id: null,
    });
    expect("password" in input).toBe(false);
    expect(wrapper.emitted("saved")?.[0]?.[1]).toBe(true); // 新規
    wrapper.unmount();
  });

  it("基本とログインの項目を、入力のとおりに送る", async () => {
    createContract.mockResolvedValue(contract());
    const wrapper = open();
    await type(wrapper, "名称", "動画");
    await wrapper.get('[aria-label="区分"]').setValue("2");
    await wrapper.get('[aria-label="ステータス"]').setValue("paused");
    await type(wrapper, "ホームページ", " https://e.com ");
    await type(wrapper, "メモ", "一行目\n二行目");
    await wrapper.get('[aria-label="パスキー"]').setValue(true);
    await wrapper.get('[aria-label="ユーザ名とパスワード"]').setValue(true);
    await wrapper.get('[aria-label="2段階認証（TEL）"]').setValue(true);
    await type(wrapper, "2段階認証（TEL）の送付先", " 090-1111-2222 ");
    await type(wrapper, "ユーザ名", " taro ");
    await type(wrapper, "パスワード", "  複数\n行  ");
    await type(wrapper, "登録メールアドレス", "me@example.com");
    await submit(wrapper);
    expect(sent()).toMatchObject({
      name: "動画", category_id: 2, status: "paused", homepage: "https://e.com", memo: "一行目\n二行目",
      login_methods: ["passkey", "password", "2fa_tel"], twofa_mail_address: null, twofa_tel_number: "090-1111-2222",
      username: "taro", password: "  複数\n行  ", registered_email: "me@example.com",
    });
    wrapper.unmount();
  });

  it("2段階認証の送付先の欄は、対応する方式を選んだときだけ出す。外すと、値も消える", async () => {
    createContract.mockResolvedValue(contract());
    const wrapper = open();
    expect(wrapper.find('[aria-label="2段階認証（メール）の送付先"]').exists()).toBe(false);
    expect(wrapper.find('[aria-label="2段階認証（TEL）の送付先"]').exists()).toBe(false);
    await wrapper.get('[aria-label="2段階認証（メール）"]').setValue(true);
    await type(wrapper, "2段階認証（メール）の送付先", "a@example.com");
    await wrapper.get('[aria-label="2段階認証（メール）"]').setValue(false);
    expect(wrapper.find('[aria-label="2段階認証（メール）の送付先"]').exists()).toBe(false);
    await wrapper.get('[aria-label="2段階認証（メール）"]').setValue(true);
    expect((wrapper.get('[aria-label="2段階認証（メール）の送付先"]').element as HTMLInputElement).value).toBe("");
    await type(wrapper, "名称", "x");
    await wrapper.get('[aria-label="2段階認証（メール）"]').setValue(false);
    await submit(wrapper);
    expect(sent().twofa_mail_address).toBeNull();
    expect(sent().login_methods).toEqual([]);
    wrapper.unmount();
  });

  it("名称が空白のみ・200 文字超のときは、送らず、名称の欄の近くに示す", async () => {
    const wrapper = open();
    await type(wrapper, "名称", "   ");
    await submit(wrapper);
    expect(wrapper.get(".field-error").text()).toBe("名称を入力してください");
    await type(wrapper, "名称", "あ".repeat(201));
    await submit(wrapper);
    expect(wrapper.get(".field-error").text()).toContain("200 文字以内");
    expect(createContract).not.toHaveBeenCalled();
    createContract.mockResolvedValue(contract());
    await type(wrapper, "名称", "あ".repeat(200));
    await submit(wrapper);
    expect(createContract).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("パスワードの入力欄は、既定で文字を伏せる。「表示」「隠す」で切り替える", async () => {
    const wrapper = open();
    const area = wrapper.get('[aria-label="パスワード"]');
    expect(area.classes()).toContain("masked");
    await wrapper.get('[aria-label="パスワードを表示"]').trigger("click");
    expect(area.classes()).not.toContain("masked");
    expect(wrapper.get('[aria-label="パスワードを隠す"]').text()).toBe("隠す");
    await wrapper.get('[aria-label="パスワードを隠す"]').trigger("click");
    expect(area.classes()).toContain("masked");
    wrapper.unmount();
  });

  it("保存の失敗は、本文の一文をフォーム内に示し、フォームは残す（入力も残る）", async () => {
    const wrapper = open();
    await type(wrapper, "名称", "動画");
    createContract.mockRejectedValueOnce(new ApiError(400, "入力が不正です"));
    await submit(wrapper);
    expect(wrapper.get('[role="alert"]').text()).toBe("入力が不正です");
    expect(wrapper.emitted("saved")).toBeUndefined();
    expect((wrapper.get('[aria-label="名称"]').element as HTMLInputElement).value).toBe("動画");
    createContract.mockRejectedValueOnce(new Error("boom: internal"));
    await submit(wrapper);
    expect(wrapper.get('[role="alert"]').text()).toBe("保存に失敗しました");
    expect(wrapper.text()).not.toContain("internal");
    createContract.mockResolvedValueOnce(contract());
    await submit(wrapper);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.emitted("saved")).toHaveLength(1);
    wrapper.unmount();
  });

  it("401 / 403 は、メッセージを出さず、殻へ通知する", async () => {
    const wrapper = open();
    await type(wrapper, "名称", "動画");
    createContract.mockRejectedValueOnce(new AuthError(401));
    await submit(wrapper);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect((wrapper.emitted("auth-error")?.[0]?.[0] as AuthError).status).toBe(401);
    wrapper.unmount();
  });

  it("キャンセルボタンと Esc で閉じる（入力は捨てる）。背景を押しても閉じない", async () => {
    const wrapper = open();
    await wrapper.get(".dialog-overlay").trigger("click");
    expect(wrapper.emitted("cancel")).toBeUndefined();
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    await wrapper.get('[role="dialog"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("cancel")).toHaveLength(2);
    expect(createContract).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});

describe("編集フォーム", () => {
  it("現在の内容を初期値にする。パスワード欄は空で、「変更するときだけ入力」と示す", () => {
    const wrapper = open(contract());
    expect(wrapper.get('[role="dialog"]').attributes("aria-label")).toBe("契約の編集");
    expect((wrapper.get('[aria-label="名称"]').element as HTMLInputElement).value).toBe("ネット動画");
    expect((wrapper.get('[aria-label="区分"]').element as HTMLSelectElement).value).toBe("2");
    expect((wrapper.get('[aria-label="ユーザ名"]').element as HTMLInputElement).value).toBe("taro");
    expect((wrapper.get('[aria-label="2段階認証（メール）の送付先"]').element as HTMLInputElement).value).toBe("2fa@example.com");
    const methods = ["ユーザ名とパスワード", "パスキー", "2段階認証（メール）", "2段階認証（TEL）"].map(
      (l) => (wrapper.get(`[aria-label="${l}"]`).element as HTMLInputElement).checked,
    );
    expect(methods).toEqual([true, false, true, false]);
    const password = wrapper.get('[aria-label="パスワード"]').element as HTMLTextAreaElement;
    expect(password.value).toBe("");
    expect(password.placeholder).toBe("変更するときだけ入力");
    wrapper.unmount();
  });

  it("パスワードを空欄のまま保存すると、password を送らない。ほかの項目は、現在の値のまま全項目を送る", async () => {
    updateContract.mockResolvedValue(contract({ name: "改名" }));
    const wrapper = open(contract());
    await type(wrapper, "名称", "改名");
    await submit(wrapper);
    const { id, input } = sentUpdate();
    expect(id).toBe(7);
    expect("password" in input).toBe(false);
    expect(input).toMatchObject({
      name: "改名", has_contract: true, category_id: 2, fee_amount: 990, fee_cycle: "monthly", renewal_date: "2026-11-05",
      contract_date: "2020-04", contract_date_precision: "month", auto_renewal: true, holder_name: "山田",
      cancellation_method: "マイページ", depends_on_ids: [8], payment_contract_id: 5, contact_phone: "0120",
    });
    expect(wrapper.emitted("saved")?.[0]?.[1]).toBe(false); // 更新
    wrapper.unmount();
  });

  it("パスワードを入力して保存すると、その値を送る", async () => {
    updateContract.mockResolvedValue(contract());
    const wrapper = open(contract());
    await type(wrapper, "パスワード", "new-pass");
    await submit(wrapper);
    expect(sentUpdate().input.password).toBe("new-pass");
    wrapper.unmount();
  });

  it("ステータスを解約以外に変えると、契約終了日を送らない。解約のままなら、保持する", async () => {
    updateContract.mockResolvedValue(contract());
    const cancelled = contract({ status: "cancelled", end_date: "2026-09-30" });
    const keep = open(cancelled);
    await submit(keep);
    expect(sentUpdate().input).toMatchObject({ status: "cancelled", end_date: "2026-09-30" });
    keep.unmount();
    const changed = open(cancelled);
    await changed.get('[aria-label="ステータス"]').setValue("active");
    await submit(changed);
    expect(sentUpdate().input).toMatchObject({ status: "active", end_date: null });
    changed.unmount();
  });

  it("契約を伴わないに変えて、消える項目に値があるときは、保存の前に確認する。キャンセルでフォームに戻る", async () => {
    updateContract.mockResolvedValue(contract({ has_contract: false }));
    const wrapper = open(contract());
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    await submit(wrapper);
    expect(updateContract).not.toHaveBeenCalled();
    const dialog = wrapper.get('.dialog-overlay .dialog-overlay [role="dialog"], [aria-label="契約を伴わないへの変更"]');
    expect(dialog.text()).toContain("契約に関する項目が消えます");
    await dialog.get('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.find('[aria-label="契約を伴わないへの変更"]').exists()).toBe(false);
    expect(updateContract).not.toHaveBeenCalled();
    expect(wrapper.emitted("cancel")).toBeUndefined(); // フォームは残る
    await submit(wrapper);
    await wrapper.get('[aria-label="契約を伴わないへの変更"] [aria-label="確定"]').trigger("click");
    await flushPromises();
    const { input } = sentUpdate();
    expect(input.has_contract).toBe(false);
    expect(input).toMatchObject({
      fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null, contract_date_precision: null,
      auto_renewal: null, holder_name: null, cancellation_method: null, depends_on_ids: [], payment_contract_id: null,
      name: "ネット動画", username: "taro", login_methods: ["password", "2fa_mail"],
    });
    wrapper.unmount();
  });

  it("確認の Esc は、確認だけを閉じ、フォームは閉じない", async () => {
    const wrapper = open(contract());
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    await submit(wrapper);
    await wrapper.get('[aria-label="契約を伴わないへの変更"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.find('[aria-label="契約を伴わないへの変更"]').exists()).toBe(false);
    expect(wrapper.emitted("cancel")).toBeUndefined();
    wrapper.unmount();
  });

  it("消える項目に値が無いときは、確認せずに保存する", async () => {
    updateContract.mockResolvedValue(contract({ has_contract: false }));
    const empty = contract({
      fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null, contract_date_precision: null,
      trial_end_date: null, auto_renewal: null, holder_name: null, member_number: null, cancel_notice_days: null,
      cancellation_fee: null, min_term_months: null, contact_phone: null, contact_email: null, contact_hours: null,
      cancellation_method: null, depends_on: [], payment_contract: null,
    });
    const wrapper = open(empty);
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    await submit(wrapper);
    expect(wrapper.find('[aria-label="契約を伴わないへの変更"]').exists()).toBe(false);
    expect(sentUpdate().input.has_contract).toBe(false);
    wrapper.unmount();
  });

  it("もともと契約を伴わない契約は、確認なしで保存できる", async () => {
    updateContract.mockResolvedValue(contract({ has_contract: false }));
    const noContract = contract({
      has_contract: false, fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null,
      contract_date_precision: null, trial_end_date: null, auto_renewal: null, holder_name: null, member_number: null,
      cancel_notice_days: null, cancellation_fee: null, min_term_months: null, contact_phone: null, contact_email: null,
      contact_hours: null, cancellation_method: null, depends_on: [], payment_contract: null,
    });
    const wrapper = open(noContract);
    await submit(wrapper);
    expect(wrapper.find('[aria-label="契約を伴わないへの変更"]').exists()).toBe(false);
    expect(updateContract).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
