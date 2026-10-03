import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthError } from "../src/api/client";
import type { Category, Contract, ContractInput } from "../src/api/types";
import ContractForm from "../src/components/ContractForm.vue";

const createContract = vi.fn<(input: ContractInput) => Promise<Contract>>();
const updateContract = vi.fn<(id: number, input: ContractInput) => Promise<Contract>>();
const listContracts = vi.fn<() => Promise<Contract[]>>();
vi.mock("../src/api/contracts", () => ({
  createContract: (input: ContractInput) => createContract(input),
  updateContract: (id: number, input: ContractInput) => updateContract(id, input),
  listContracts: () => listContracts(),
}));

const CATEGORIES: Category[] = [
  { id: 1, name: "その他", is_default: true, is_financial: false },
  { id: 3, name: "銀行", is_default: false, is_financial: true },
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

const BANK_CARD = contract(50, { name: "Aカード", category: { id: 3, name: "銀行", is_financial: true }, has_contract: false });
const PLAIN = contract(51, { name: "プロバイダ" });
const OTHER = contract(52, { name: "動画サービス" });

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

async function openAndLoad(existing?: Contract): Promise<Wrapper> {
  const wrapper = open(existing);
  await flushPromises();
  await type(wrapper, "名称", existing?.name ?? "テスト契約");
  return wrapper;
}

beforeEach(() => {
  createContract.mockReset();
  createContract.mockResolvedValue(contract(1));
  updateContract.mockReset();
  updateContract.mockResolvedValue(contract(1));
  listContracts.mockReset();
  listContracts.mockResolvedValue([BANK_CARD, PLAIN, OTHER]);
  document.body.innerHTML = "";
});

describe("契約を伴う契約だけの入力項目", () => {
  it("契約を伴うときは契約・問い合わせ先・関連の節を出し、契約を伴わないに切り替えると隠す", async () => {
    const wrapper = open();
    await flushPromises();
    expect(wrapper.findAll("fieldset").map((f) => f.attributes("aria-label") ?? f.get("legend").text())).toEqual(["基本", "ログイン", "契約", "問い合わせ先", "関連"]);
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    expect(wrapper.findAll("fieldset").map((f) => f.get("legend").text())).toEqual(["基本", "ログイン"]);
    await wrapper.findAll('input[name="has_contract"]')[0]?.setValue(true);
    expect(wrapper.findAll("fieldset")).toHaveLength(5);
    wrapper.unmount();
  });

  it("すべて空のまま登録すると、契約の項目は空で送る（維持費の周期は、金額が無ければ送らない）", async () => {
    const wrapper = await openAndLoad();
    await submit(wrapper);
    expect(sent()).toMatchObject({
      fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null, contract_date_precision: null,
      trial_end_date: null, end_date: null, auto_renewal: null, holder_name: null, member_number: null,
      cancel_notice_days: null, cancellation_fee: null, min_term_months: null, contact_phone: null, contact_email: null,
      contact_hours: null, cancellation_method: null, depends_on_ids: [], payment_contract_id: null,
    });
    wrapper.unmount();
  });

  it("維持費: 金額と周期（既定は月額）を送る。年間も選べる", async () => {
    const wrapper = await openAndLoad();
    const cycles = wrapper.findAll('input[name="fee_cycle"]');
    expect((cycles[0]?.element as HTMLInputElement).checked).toBe(true);
    expect(wrapper.findAll('[aria-label="維持費の周期"] label').map((l) => l.text())).toEqual(["月額", "年間"]);
    await type(wrapper, "維持費の金額", " 990 ");
    await submit(wrapper);
    expect(sent()).toMatchObject({ fee_amount: 990, fee_cycle: "monthly" });
    await cycles[1]?.setValue(true);
    await type(wrapper, "維持費の金額", "0");
    await submit(wrapper);
    expect(sent()).toMatchObject({ fee_amount: 0, fee_cycle: "yearly" });
    wrapper.unmount();
  });

  it("維持費が整数でないとき（小数・負・文字）は、送らず、欄の近くに示す", async () => {
    const wrapper = await openAndLoad();
    for (const bad of ["1.5", "-1", "abc", "１２"]) {
      createContract.mockClear();
      await type(wrapper, "維持費の金額", bad);
      await submit(wrapper);
      expect(wrapper.get(".field-error").text()).toContain("0 以上の整数");
      expect(createContract).not.toHaveBeenCalled();
    }
    wrapper.unmount();
  });

  it("更新日・無料期間の終了日（日付）・自動更新（あり / なし / 未設定）・文字列の項目を送る", async () => {
    const wrapper = await openAndLoad();
    await type(wrapper, "更新日", "2026-11-05");
    await type(wrapper, "無料期間の終了日", "2026-10-31");
    await type(wrapper, "自動更新", "false");
    await type(wrapper, "契約者名義", " 山田 太郎 ");
    await type(wrapper, "会員番号・契約番号", "A-123");
    await type(wrapper, "解約手数料・違約金", "なし");
    await type(wrapper, "解約方法", "マイページから\n解約する");
    await type(wrapper, "問い合わせ先の電話番号", "0120-000-000");
    await type(wrapper, "問い合わせ先のメールアドレス", "s@example.com");
    await type(wrapper, "問い合わせ先の受付時間", "平日 10:00-18:00");
    await submit(wrapper);
    expect(sent()).toMatchObject({
      renewal_date: "2026-11-05", trial_end_date: "2026-10-31", auto_renewal: false, holder_name: "山田 太郎",
      member_number: "A-123", cancellation_fee: "なし", cancellation_method: "マイページから\n解約する",
      contact_phone: "0120-000-000", contact_email: "s@example.com", contact_hours: "平日 10:00-18:00",
    });
    await type(wrapper, "自動更新", "true");
    await submit(wrapper);
    expect(sent().auto_renewal).toBe(true);
    await type(wrapper, "自動更新", "");
    await submit(wrapper);
    expect(sent().auto_renewal).toBeNull();
    wrapper.unmount();
  });

  it("解約の受付期限・最低契約期間: 0 以上の整数（0 も可）。それ以外は送らない", async () => {
    const wrapper = await openAndLoad();
    await type(wrapper, "解約の受付期限（日数）", "0");
    await type(wrapper, "最低契約期間（月数）", "12");
    await submit(wrapper);
    expect(sent()).toMatchObject({ cancel_notice_days: 0, min_term_months: 12 });
    createContract.mockClear();
    await type(wrapper, "解約の受付期限（日数）", "-3");
    await type(wrapper, "最低契約期間（月数）", "半年");
    await submit(wrapper);
    expect(wrapper.findAll(".field-error").map((e) => e.text())).toEqual([
      "解約の受付期限は 0 以上の整数（日数）で入力してください",
      "最低契約期間は 0 以上の整数（月数）で入力してください",
    ]);
    expect(createContract).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("契約終了日の欄は、ステータスが解約のときだけ出す", async () => {
    const wrapper = await openAndLoad();
    expect(wrapper.find('[aria-label="契約終了日"]').exists()).toBe(false);
    await wrapper.get('[aria-label="ステータス"]').setValue("cancelled");
    await type(wrapper, "契約終了日", "2026-09-30");
    await submit(wrapper);
    expect(sent()).toMatchObject({ status: "cancelled", end_date: "2026-09-30" });
    await wrapper.get('[aria-label="ステータス"]').setValue("paused");
    expect(wrapper.find('[aria-label="契約終了日"]').exists()).toBe(false);
    await submit(wrapper);
    expect(sent()).toMatchObject({ status: "paused", end_date: null });
    wrapper.unmount();
  });
});

describe("契約日（精度に応じた入力）", () => {
  it("精度の選択肢は、指定しない・年月日・年月・年・不明。選んだ精度に応じて、入力欄が変わる", async () => {
    const wrapper = await openAndLoad();
    expect(wrapper.findAll('[aria-label="契約日の精度"] option').map((o) => o.text())).toEqual(["指定しない", "年月日", "年月", "年", "不明"]);
    const inputs = () => wrapper.findAll('input[aria-label^="契約日の"]').map((i) => i.attributes("aria-label"));
    expect(inputs()).toEqual([]);
    await type(wrapper, "契約日の精度", "day");
    expect(inputs()).toEqual(["契約日の年", "契約日の月", "契約日の日"]);
    await type(wrapper, "契約日の精度", "month");
    expect(inputs()).toEqual(["契約日の年", "契約日の月"]);
    await type(wrapper, "契約日の精度", "year");
    expect(inputs()).toEqual(["契約日の年"]);
    await type(wrapper, "契約日の精度", "unknown");
    expect(inputs()).toEqual([]);
    wrapper.unmount();
  });

  it("精度ごとの形式で送る。不明・指定しないときは、日付を送らない", async () => {
    const wrapper = await openAndLoad();
    await type(wrapper, "契約日の精度", "day");
    await type(wrapper, "契約日の年", "2020");
    await type(wrapper, "契約日の月", "4");
    await type(wrapper, "契約日の日", "3");
    await submit(wrapper);
    expect(sent()).toMatchObject({ contract_date: "2020-04-03", contract_date_precision: "day" });
    await type(wrapper, "契約日の精度", "month");
    await submit(wrapper);
    expect(sent()).toMatchObject({ contract_date: "2020-04", contract_date_precision: "month" });
    await type(wrapper, "契約日の精度", "year");
    await submit(wrapper);
    expect(sent()).toMatchObject({ contract_date: "2020", contract_date_precision: "year" });
    await type(wrapper, "契約日の精度", "unknown");
    await submit(wrapper);
    expect(sent()).toMatchObject({ contract_date: null, contract_date_precision: "unknown" });
    await type(wrapper, "契約日の精度", "");
    await submit(wrapper);
    expect(sent()).toMatchObject({ contract_date: null, contract_date_precision: null });
    wrapper.unmount();
  });

  it("年・月・日が正しくないときは、送らず、欄の近くに示す（うるう年を考慮する）", async () => {
    const wrapper = await openAndLoad();
    await type(wrapper, "契約日の精度", "day");
    for (const [y, m, d, message] of [
      ["20", "4", "3", "年"],
      ["2020", "13", "3", "月"],
      ["2023", "2", "29", "日"],
      ["2020", "4", "", "日"],
    ] as const) {
      createContract.mockClear();
      await type(wrapper, "契約日の年", y);
      await type(wrapper, "契約日の月", m);
      await type(wrapper, "契約日の日", d);
      await submit(wrapper);
      expect(wrapper.get(".field-error").text()).toContain(message);
      expect(createContract).not.toHaveBeenCalled();
    }
    await type(wrapper, "契約日の年", "2024");
    await type(wrapper, "契約日の月", "2");
    await type(wrapper, "契約日の日", "29");
    await submit(wrapper);
    expect(sent()).toMatchObject({ contract_date: "2024-02-29" });
    wrapper.unmount();
  });

  it("編集では、保存済みの契約日を、精度に応じた欄に入れる", async () => {
    const wrapper = open(contract(9, { name: "既存", contract_date: "2020-04", contract_date_precision: "month" }));
    await flushPromises();
    expect((wrapper.get('[aria-label="契約日の精度"]').element as HTMLSelectElement).value).toBe("month");
    expect((wrapper.get('[aria-label="契約日の年"]').element as HTMLInputElement).value).toBe("2020");
    expect((wrapper.get('[aria-label="契約日の月"]').element as HTMLInputElement).value).toBe("4");
    expect(wrapper.find('[aria-label="契約日の日"]').exists()).toBe(false);
    wrapper.unmount();
  });
});

describe("関連（依存契約・支払方法）", () => {
  it("依存契約は、自分以外の契約から複数を選べる。名称で絞り込める", async () => {
    const wrapper = await openAndLoad();
    const labels = () => wrapper.findAll('[aria-label="依存契約の選択肢"] label').map((l) => l.text());
    expect(labels()).toEqual(["Aカード（銀行）", "プロバイダ（その他）", "動画サービス（その他）"]);
    await type(wrapper, "依存契約を絞り込む", "ＡＢ");
    expect(wrapper.find('[aria-label="依存契約の選択肢"]').text()).toContain("選べる契約がありません");
    await type(wrapper, "依存契約を絞り込む", "プロ");
    expect(labels()).toEqual(["プロバイダ（その他）"]);
    await wrapper.get('[aria-label="プロバイダを依存契約にする"]').setValue(true);
    await type(wrapper, "依存契約を絞り込む", "");
    await wrapper.get('[aria-label="動画サービスを依存契約にする"]').setValue(true);
    await submit(wrapper);
    expect(sent().depends_on_ids).toEqual([51, 52]);
    wrapper.unmount();
  });

  it("編集では、自分自身を選択肢に出さない。選択済みの依存契約にはチェックが入る", async () => {
    listContracts.mockResolvedValue([BANK_CARD, PLAIN, OTHER, contract(9, { name: "編集中の契約" })]);
    const wrapper = open(contract(9, { name: "編集中の契約", depends_on: [{ id: 51, name: "プロバイダ" }], payment_contract: { id: 50, name: "Aカード" } }));
    await flushPromises();
    expect(wrapper.findAll('[aria-label="依存契約の選択肢"] label').map((l) => l.text())).not.toContain("編集中の契約（その他）");
    expect((wrapper.get('[aria-label="プロバイダを依存契約にする"]').element as HTMLInputElement).checked).toBe(true);
    expect((wrapper.get('[aria-label="動画サービスを依存契約にする"]').element as HTMLInputElement).checked).toBe(false);
    expect((wrapper.get('[aria-label="支払方法"]').element as HTMLSelectElement).value).toBe("50");
    await submit(wrapper);
    expect(updateContract.mock.calls.at(-1)?.[1]).toMatchObject({ depends_on_ids: [51], payment_contract_id: 50 });
    wrapper.unmount();
  });

  it("支払方法は、金融機関の区分の契約だけを選べる（選ばないこともできる）", async () => {
    const wrapper = await openAndLoad();
    expect(wrapper.findAll('[aria-label="支払方法"] option').map((o) => o.text())).toEqual(["選ばない", "Aカード（銀行）"]);
    await submit(wrapper);
    expect(sent().payment_contract_id).toBeNull();
    await type(wrapper, "支払方法", "50");
    await submit(wrapper);
    expect(sent().payment_contract_id).toBe(50);
    // 「選ばない」を選び直す（利用者が選択肢を選ぶ操作）
    const select = wrapper.get('[aria-label="支払方法"]');
    (select.findAll("option")[0]?.element as HTMLOptionElement).selected = true;
    await select.trigger("change");
    await submit(wrapper);
    expect(sent().payment_contract_id).toBeNull();
    wrapper.unmount();
  });

  it("金融機関の区分の契約が無いときは、その旨を示す", async () => {
    listContracts.mockResolvedValue([PLAIN]);
    const wrapper = await openAndLoad();
    expect(wrapper.get('fieldset[aria-label="関連"]').text()).toContain("金融機関の区分の契約がありません");
    expect(wrapper.findAll('[aria-label="支払方法"] option').map((o) => o.text())).toEqual(["選ばない"]);
    wrapper.unmount();
  });

  it("選択肢を読み込めなくても、フォームは使える（メッセージを出す）。401 は殻へ通知する", async () => {
    listContracts.mockRejectedValueOnce(new Error("x"));
    const failed = await openAndLoad();
    expect(failed.get('fieldset[aria-label="関連"] [role="alert"]').text()).toBe("依存契約・支払方法の選択肢を読み込めませんでした");
    await submit(failed);
    expect(createContract).toHaveBeenCalledTimes(1);
    failed.unmount();
    listContracts.mockRejectedValueOnce(new AuthError(401));
    const unauth = open();
    await flushPromises();
    expect((unauth.emitted("auth-error")?.[0]?.[0] as AuthError).status).toBe(401);
    unauth.unmount();
  });

  it("契約を伴わないときは、依存契約・支払方法を送らない", async () => {
    const wrapper = await openAndLoad();
    await wrapper.get('[aria-label="プロバイダを依存契約にする"]').setValue(true);
    await type(wrapper, "支払方法", "50");
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    await submit(wrapper);
    // 値が入っているので、確認が出る
    await wrapper.get('[aria-label="契約を伴わないへの変更"] [aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(sent()).toMatchObject({ has_contract: false, depends_on_ids: [], payment_contract_id: null });
    wrapper.unmount();
  });
});

describe("契約を伴わないへの切り替えの確認（新規登録でも、入力した値が消えるとき）", () => {
  it("契約の項目に値を入力してから、契約を伴わないに切り替えて保存すると、確認が出る。キャンセルで戻れる", async () => {
    const wrapper = await openAndLoad();
    await type(wrapper, "維持費の金額", "500");
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    await submit(wrapper);
    expect(createContract).not.toHaveBeenCalled();
    expect(wrapper.get('[aria-label="契約を伴わないへの変更"]').text()).toContain("契約に関する項目が消えます");
    await wrapper.get('[aria-label="契約を伴わないへの変更"] [aria-label="キャンセル"]').trigger("click");
    await wrapper.findAll('input[name="has_contract"]')[0]?.setValue(true);
    expect((wrapper.get('[aria-label="維持費の金額"]').element as HTMLInputElement).value).toBe("500"); // 入力は残っている
    wrapper.unmount();
  });

  it("契約の項目に何も入力していなければ、確認せずに保存する", async () => {
    const wrapper = await openAndLoad();
    await wrapper.findAll('input[name="has_contract"]')[1]?.setValue(true);
    await submit(wrapper);
    expect(wrapper.find('[aria-label="契約を伴わないへの変更"]').exists()).toBe(false);
    expect(sent().has_contract).toBe(false);
    wrapper.unmount();
  });
});

describe("編集の初期値", () => {
  it("契約の項目・関連を、保存済みの値で入れる。保存すると、同じ値を送る", async () => {
    listContracts.mockResolvedValue([BANK_CARD, PLAIN, OTHER]);
    const existing = contract(9, {
      name: "動画", fee_amount: 12000, fee_cycle: "yearly", renewal_date: "2026-11-05", trial_end_date: "2026-10-31",
      auto_renewal: true, holder_name: "山田", member_number: "A-1", cancel_notice_days: 7, cancellation_fee: "なし",
      min_term_months: 12, cancellation_method: "手順", contact_phone: "0120", contact_email: "s@e.com", contact_hours: "平日",
      contract_date: "2020-04-03", contract_date_precision: "day", depends_on: [{ id: 51, name: "プロバイダ" }],
      payment_contract: { id: 50, name: "Aカード" },
    });
    const wrapper = open(existing);
    await flushPromises();
    const value = (label: string) => (wrapper.get(`[aria-label="${label}"]`).element as HTMLInputElement).value;
    expect(value("維持費の金額")).toBe("12000");
    expect((wrapper.findAll('input[name="fee_cycle"]')[1]?.element as HTMLInputElement).checked).toBe(true);
    expect(value("更新日")).toBe("2026-11-05");
    expect(value("契約者名義")).toBe("山田");
    expect(value("解約の受付期限（日数）")).toBe("7");
    expect(value("最低契約期間（月数）")).toBe("12");
    expect(value("自動更新")).toBe("true");
    expect(value("契約日の日")).toBe("3");
    await submit(wrapper);
    expect(updateContract.mock.calls.at(-1)?.[1]).toMatchObject({
      fee_amount: 12000, fee_cycle: "yearly", renewal_date: "2026-11-05", trial_end_date: "2026-10-31", auto_renewal: true,
      holder_name: "山田", member_number: "A-1", cancel_notice_days: 7, cancellation_fee: "なし", min_term_months: 12,
      cancellation_method: "手順", contact_phone: "0120", contact_email: "s@e.com", contact_hours: "平日",
      contract_date: "2020-04-03", contract_date_precision: "day", depends_on_ids: [51], payment_contract_id: 50,
    });
    wrapper.unmount();
  });
});
