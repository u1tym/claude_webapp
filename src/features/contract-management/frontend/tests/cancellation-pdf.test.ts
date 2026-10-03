import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError } from "../src/api/client";
import type { Contract, Plan, PlanCandidate } from "../src/api/types";
import { formatLocalDate } from "../src/format";
import CancellationView from "../src/views/CancellationView.vue";

const getPlan = vi.fn<() => Promise<Plan>>();
const getCandidates = vi.fn<() => Promise<PlanCandidate[]>>();
const savePlan = vi.fn<(ids: number[]) => Promise<Plan>>();
const listContracts = vi.fn<() => Promise<Contract[]>>();
const getContractPassword = vi.fn<(id: number) => Promise<string | null>>();
const getContract = vi.fn<(id: number) => Promise<Contract>>();

vi.mock("../src/api/cancellation", () => ({
  getPlan: () => getPlan(),
  getCandidates: () => getCandidates(),
  savePlan: (ids: number[]) => savePlan(ids),
}));
vi.mock("../src/api/contracts", () => ({
  listContracts: () => listContracts(),
  getContractPassword: (id: number) => getContractPassword(id),
  getContract: (id: number) => getContract(id),
}));

function contract(id: number, name: string, overrides: Partial<Contract> = {}): Contract {
  return {
    id, name, has_contract: true, category: { id: 1, name: "その他", is_financial: false }, status: "active",
    homepage: null, memo: null, login_methods: ["password"], twofa_mail_address: null, twofa_tel_number: null,
    username: "secret-user-name", has_password: true, password_unset: false, registered_email: "secret-mail@example.com",
    fee_amount: null, fee_cycle: null, renewal_date: null, contract_date: null, contract_date_precision: null,
    trial_end_date: null, end_date: null, auto_renewal: null, holder_name: null, member_number: null,
    cancel_notice_days: null, cancellation_fee: null, min_term_months: null, contact_phone: null, contact_email: null,
    contact_hours: null, cancellation_method: null, depends_on: [], payment_contract: null, depended_by: [],
    payment_for: [], ...overrides,
  };
}

const A = contract(1, "プロバイダ", { cancellation_method: "電話で連絡する" });
const B = contract(2, "動画", { cancellation_method: "マイページから\n解約する", depends_on: [{ id: 1, name: "プロバイダ" }] });
const C = contract(3, "ジム");

function planOf(...cs: Contract[]): Plan {
  return {
    items: cs.map((c, i) => ({ position: i + 1, contract_id: c.id, name: c.name, cancellation_method: c.cancellation_method, depends_on: c.depends_on })),
    warnings: [],
  };
}

const printSpy = vi.fn();

async function mountView(plan: Plan, cands: PlanCandidate[] = []) {
  getPlan.mockResolvedValue(plan);
  getCandidates.mockResolvedValue(cands);
  listContracts.mockResolvedValue([A, B, C]);
  const wrapper = mount(CancellationView, { attachTo: document.body });
  await flushPromises();
  return wrapper;
}

const pdfButton = (w: Awaited<ReturnType<typeof mountView>>) => w.get('[aria-label="PDF出力"]');
const printArea = () => document.querySelector(".print-area") as HTMLElement;

beforeEach(() => {
  for (const m of [getPlan, getCandidates, savePlan, listContracts, getContractPassword, getContract]) {
    m.mockReset();
  }
  printSpy.mockReset();
  window.print = printSpy;
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("PDF 出力のボタン", () => {
  it("文字ラベルのボタン「PDF出力」。保存済みの解約順があり、未保存の変更がなければ、有効", async () => {
    const wrapper = await mountView(planOf(A, B));
    expect(pdfButton(wrapper).text()).toBe("PDF出力");
    expect(pdfButton(wrapper).attributes("disabled")).toBeUndefined();
    expect(wrapper.find('[data-testid="pdf-reason"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("解約の対象が 0 件のときは無効にし、理由を併記する", async () => {
    const wrapper = await mountView(planOf(), [{ id: 3, name: "ジム", category_name: "その他", has_cancellation_method: false }]);
    expect(pdfButton(wrapper).attributes("disabled")).toBeDefined();
    expect(wrapper.get('[data-testid="pdf-reason"]').text()).toBe("解約の対象がないため、PDF 出力できません");
    await pdfButton(wrapper).trigger("click");
    expect(printSpy).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("未保存の変更があるときは無効にし、理由を併記する。保存すると、有効になる", async () => {
    const wrapper = await mountView(planOf(A, B));
    await wrapper.get('[aria-label="プロバイダを下へ"]').trigger("click");
    expect(pdfButton(wrapper).attributes("disabled")).toBeDefined();
    expect(wrapper.get('[data-testid="pdf-reason"]').text()).toBe("未保存の変更があるため、PDF 出力できません。先に保存してください");
    savePlan.mockResolvedValue(planOf(B, A));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(pdfButton(wrapper).attributes("disabled")).toBeUndefined();
    expect(wrapper.find('[data-testid="pdf-reason"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("保存して空にしたとき（0 件）も、無効になる", async () => {
    const wrapper = await mountView(planOf(A));
    await wrapper.get('[aria-label="プロバイダを解約順から外す"]').trigger("click");
    savePlan.mockResolvedValue(planOf());
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(pdfButton(wrapper).attributes("disabled")).toBeDefined();
    expect(wrapper.get('[data-testid="pdf-reason"]').text()).toContain("解約の対象がない");
    wrapper.unmount();
  });
});

describe("印刷用の領域", () => {
  it("押すと、保存済みの解約順を取得して、見出し・出力日・番号・名称・解約方法を、解約順に組み、印刷を開く", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 3, 0, 30)); // 日本時間の 0 時台（UTC では前日になる時刻）
    const wrapper = await mountView(planOf(A, B));
    getPlan.mockClear();
    getPlan.mockResolvedValue(planOf(B, A, C)); // 押した時点の保存済みの解約順を取得し直す
    expect(printArea().textContent).not.toContain("動画"); // 押すまでは、組まない
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(getPlan).toHaveBeenCalledTimes(1);
    expect(printSpy).toHaveBeenCalledTimes(1);
    const area = printArea();
    expect(area.querySelector("h1")?.textContent).toBe("解約手順");
    expect(area.querySelector("p")?.textContent).toBe("出力日: 2026年10月3日");
    const items = [...area.querySelectorAll("li")].map((li) => ({
      title: li.querySelector("h2")?.textContent,
      method: li.querySelector(".print-method")?.textContent,
    }));
    expect(items).toEqual([
      { title: "1. 動画", method: "マイページから\n解約する" },
      { title: "2. プロバイダ", method: "電話で連絡する" },
      { title: "3. ジム", method: "未入力" },
    ]);
    expect(area.querySelector(".print-method")?.className).toContain("print-method");
    wrapper.unmount();
  });

  it("印刷を開く時点で、印刷用の領域は組み終わっている", async () => {
    const wrapper = await mountView(planOf(A));
    let textAtPrint = "";
    printSpy.mockImplementation(() => {
      textAtPrint = printArea().textContent ?? "";
    });
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(textAtPrint).toContain("1. プロバイダ");
    wrapper.unmount();
  });

  it("印刷用の領域は、画面には出さない（aria-hidden。画面の表示は CSS で隠す）", async () => {
    const wrapper = await mountView(planOf(A));
    expect(printArea().getAttribute("aria-hidden")).toBe("true");
    expect(printArea().parentElement).toBe(document.body);
    wrapper.unmount();
    expect(document.querySelector(".print-area")).toBeNull();
  });

  it("パスワード・ユーザ名・登録メールアドレスを、取得も、出力もしない", async () => {
    const wrapper = await mountView(planOf(A, B));
    getContractPassword.mockClear();
    getContract.mockClear();
    listContracts.mockClear();
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(getContractPassword).not.toHaveBeenCalled();
    expect(getContract).not.toHaveBeenCalled();
    expect(listContracts).not.toHaveBeenCalled();
    const text = printArea().textContent ?? "";
    for (const secret of ["secret-user-name", "secret-mail@example.com", "パスワード", "ユーザ名", "メールアドレス"]) {
      expect(text).not.toContain(secret);
    }
    wrapper.unmount();
  });

  it("出力のたびに、組み直す（解約順を変えて保存したあとは、新しい並びで出す）", async () => {
    const wrapper = await mountView(planOf(A, B));
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect([...printArea().querySelectorAll("h2")].map((e) => e.textContent)).toEqual(["1. プロバイダ", "2. 動画"]);
    await wrapper.get('[aria-label="プロバイダを下へ"]').trigger("click");
    savePlan.mockResolvedValue(planOf(B, A));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    getPlan.mockResolvedValue(planOf(B, A));
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect([...printArea().querySelectorAll("h2")].map((e) => e.textContent)).toEqual(["1. 動画", "2. プロバイダ"]);
    expect(printSpy).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});

describe("PDF 出力の失敗", () => {
  it("取得に失敗したら、一文を出し、印刷は開かない。内部理由は出さない", async () => {
    const wrapper = await mountView(planOf(A));
    getPlan.mockRejectedValueOnce(new Error("boom: internal"));
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("PDF 出力に失敗しました");
    expect(wrapper.text()).not.toContain("internal");
    expect(printSpy).not.toHaveBeenCalled();
    getPlan.mockRejectedValueOnce(new ApiError(500, "サーバエラーです"));
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("PDF 出力に失敗しました");
    wrapper.unmount();
  });

  it("401 は、メッセージを出さずに殻へ通知する。失敗のあとも、再度出力できる", async () => {
    const wrapper = await mountView(planOf(A));
    getPlan.mockRejectedValueOnce(new AuthError(401));
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
    expect(pdfButton(wrapper).attributes("disabled")).toBeUndefined();
    getPlan.mockResolvedValue(planOf(A));
    await pdfButton(wrapper).trigger("click");
    await flushPromises();
    expect(printSpy).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});

describe("出力日の形式", () => {
  it("ローカル日付（日本時間）で、「年月日」にする（UTC にしない）", () => {
    expect(formatLocalDate(new Date(2026, 0, 5))).toBe("2026年1月5日");
    expect(formatLocalDate(new Date(2026, 11, 31, 23, 59))).toBe("2026年12月31日");
    expect(formatLocalDate(new Date(2026, 9, 3, 0, 5))).toBe("2026年10月3日");
  });
});
