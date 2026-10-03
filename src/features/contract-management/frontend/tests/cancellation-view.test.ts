import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError } from "../src/api/client";
import type { Contract, Plan, PlanCandidate } from "../src/api/types";
import CancellationView from "../src/views/CancellationView.vue";

const getPlan = vi.fn<() => Promise<Plan>>();
const getCandidates = vi.fn<() => Promise<PlanCandidate[]>>();
const savePlan = vi.fn<(ids: number[]) => Promise<Plan>>();
const listContracts = vi.fn<() => Promise<Contract[]>>();

vi.mock("../src/api/cancellation", () => ({
  getPlan: () => getPlan(),
  getCandidates: () => getCandidates(),
  savePlan: (ids: number[]) => savePlan(ids),
}));
vi.mock("../src/api/contracts", () => ({ listContracts: () => listContracts() }));

function contract(id: number, name: string, overrides: Partial<Contract> = {}): Contract {
  return {
    id, name, has_contract: true, category: { id: 1, name: "その他", is_financial: false }, status: "active",
    homepage: null, memo: null, login_methods: [], twofa_mail_address: null, twofa_tel_number: null, username: null,
    has_password: false, password_unset: false, registered_email: null, fee_amount: null, fee_cycle: null,
    renewal_date: null, contract_date: null, contract_date_precision: null, trial_end_date: null, end_date: null,
    auto_renewal: null, holder_name: null, member_number: null, cancel_notice_days: null, cancellation_fee: null,
    min_term_months: null, contact_phone: null, contact_email: null, contact_hours: null, cancellation_method: null,
    depends_on: [], payment_contract: null, depended_by: [], payment_for: [], ...overrides,
  };
}

const PROVIDER = contract(1, "プロバイダ", { cancellation_method: "電話で連絡する" });
const VIDEO = contract(2, "動画", { cancellation_method: "マイページから\n解約する\n三行目\n四行目", depends_on: [{ id: 1, name: "プロバイダ" }] });
const GYM = contract(3, "ジム", { category: { id: 5, name: "スポーツ", is_financial: false } });
const MUSIC = contract(4, "音楽", { depends_on: [{ id: 1, name: "プロバイダ" }], cancellation_method: "設定から" });
const CONTRACTS = [PROVIDER, VIDEO, GYM, MUSIC];

function planOf(...contracts: Contract[]): Plan {
  return {
    items: contracts.map((c, i) => ({
      position: i + 1, contract_id: c.id, name: c.name, cancellation_method: c.cancellation_method, depends_on: c.depends_on,
    })),
    warnings: [],
  };
}

function candidate(c: Contract): PlanCandidate {
  return { id: c.id, name: c.name, category_name: c.category.name, has_cancellation_method: c.cancellation_method !== null };
}

async function mountView(plan: Plan, cands: PlanCandidate[]) {
  getPlan.mockResolvedValue(plan);
  getCandidates.mockResolvedValue(cands);
  listContracts.mockResolvedValue(CONTRACTS);
  const wrapper = mount(CancellationView);
  await flushPromises();
  return wrapper;
}

const rowNames = (w: VueWrapper) => w.findAll('[aria-label="解約順の一覧"] .plan-row .cell-title').map((e) => e.text());
const candidateNames = (w: VueWrapper) => w.findAll('[aria-label="対象にできる契約"] .plan-row .cell-title').map((e) => e.text());

beforeEach(() => {
  getPlan.mockReset();
  getCandidates.mockReset();
  savePlan.mockReset();
  listContracts.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("解約順の表示", () => {
  it("取得中は「読み込み中…」を出す", () => {
    getPlan.mockReturnValue(new Promise(() => undefined));
    getCandidates.mockResolvedValue([]);
    listContracts.mockResolvedValue([]);
    expect(mount(CancellationView).text()).toContain("読み込み中…");
  });

  it("解約順を番号付きで並べ、名称・解約方法・依存契約を出す。解約方法が未入力なら「未入力」", async () => {
    const wrapper = await mountView(planOf(PROVIDER, VIDEO, GYM), [candidate(MUSIC)]);
    const rows = wrapper.findAll('[aria-label="解約順の一覧"] .plan-row');
    expect(rows.map((r) => r.get(".plan-number").text())).toEqual(["1", "2", "3"]);
    expect(rowNames(wrapper)).toEqual(["プロバイダ", "動画", "ジム"]);
    expect(rows[0]?.get(".plan-method").text()).toBe("電話で連絡する");
    expect(rows[1]?.get(".plan-method").classes()).toContain("pre");
    expect(rows[1]?.text()).toContain("依存契約: プロバイダ");
    expect(rows[2]?.get(".plan-method").text()).toBe("解約方法: 未入力");
    expect(rows[0]?.text()).not.toContain("依存契約");
  });

  it("対象にできる契約には、名称・区分・解約方法の有無を出す", async () => {
    const wrapper = await mountView(planOf(), [candidate(GYM), candidate(MUSIC)]);
    const items = wrapper.findAll('[aria-label="対象にできる契約"] .plan-row');
    expect(items[0]?.text()).toContain("ジム");
    expect(items[0]?.text()).toContain("スポーツ／解約方法: 未入力");
    expect(items[1]?.text()).toContain("その他／解約方法: あり");
  });

  it("0 件の文言: 解約順は「解約の対象がありません」、対象にできる契約は「データがありません」", async () => {
    const wrapper = await mountView(planOf(), []);
    expect(wrapper.get('[aria-label="解約順の一覧"]').text()).toContain("解約の対象がありません");
    expect(wrapper.get('[aria-label="対象にできる契約"]').text()).toContain("データがありません");
    expect(wrapper.find(".plan-list").exists()).toBe(false);
  });

  it("対象にできる契約は、名称で絞り込める。該当が無いときは「該当するデータがありません」", async () => {
    const wrapper = await mountView(planOf(), [candidate(GYM), candidate(MUSIC)]);
    await wrapper.get('input[aria-label="対象にできる契約を絞り込む"]').setValue("音");
    expect(candidateNames(wrapper)).toEqual(["音楽"]);
    await wrapper.get('input[aria-label="対象にできる契約を絞り込む"]').setValue("なし");
    expect(wrapper.get('[aria-label="対象にできる契約"]').text()).toContain("該当するデータがありません");
  });
});

describe("解約順の編集", () => {
  it("上へ・下へで並べ替える。先頭の「上へ」と末尾の「下へ」は無効", async () => {
    const wrapper = await mountView(planOf(PROVIDER, VIDEO, GYM), []);
    const up = (name: string) => wrapper.get(`[aria-label="${name}を上へ"]`);
    const down = (name: string) => wrapper.get(`[aria-label="${name}を下へ"]`);
    expect(up("プロバイダ").attributes("disabled")).toBeDefined();
    expect(down("ジム").attributes("disabled")).toBeDefined();
    expect(down("プロバイダ").attributes("disabled")).toBeUndefined();
    await down("プロバイダ").trigger("click");
    expect(rowNames(wrapper)).toEqual(["動画", "プロバイダ", "ジム"]);
    await up("ジム").trigger("click");
    expect(rowNames(wrapper)).toEqual(["動画", "ジム", "プロバイダ"]);
    expect(wrapper.findAll(".plan-number").map((n) => n.text())).toEqual(["1", "2", "3"]);
    expect(up("動画").attributes("disabled")).toBeDefined();
    expect(down("プロバイダ").attributes("disabled")).toBeDefined();
  });

  it("「上へ」「下へ」は文字ラベルのボタン、「外す」はアイコンのボタン（aria-label 付き）", async () => {
    const wrapper = await mountView(planOf(PROVIDER), [candidate(GYM)]);
    expect(wrapper.get('[aria-label="プロバイダを上へ"]').text()).toBe("上へ");
    expect(wrapper.get('[aria-label="プロバイダを下へ"]').text()).toBe("下へ");
    const remove = wrapper.get('[aria-label="プロバイダを解約順から外す"]');
    expect(remove.find("svg.icon").exists()).toBe(true);
    expect(remove.text()).toBe("");
    expect(wrapper.get('[aria-label="ジムを解約順に加える"]').text()).toBe("加える");
  });

  it("加えるで、末尾に加わり（解約方法・依存契約も出る）、候補から消える。外すと、候補に戻る（ID 順）", async () => {
    const wrapper = await mountView(planOf(PROVIDER), [candidate(VIDEO), candidate(GYM), candidate(MUSIC)]);
    await wrapper.get('[aria-label="音楽を解約順に加える"]').trigger("click");
    expect(rowNames(wrapper)).toEqual(["プロバイダ", "音楽"]);
    expect(candidateNames(wrapper)).toEqual(["動画", "ジム"]);
    const added = wrapper.findAll('[aria-label="解約順の一覧"] .plan-row')[1];
    expect(added?.get(".plan-method").text()).toBe("設定から");
    expect(added?.text()).toContain("依存契約: プロバイダ");
    await wrapper.get('[aria-label="プロバイダを解約順から外す"]').trigger("click");
    expect(rowNames(wrapper)).toEqual(["音楽"]);
    expect(candidateNames(wrapper)).toEqual(["プロバイダ", "動画", "ジム"]);
    expect(wrapper.findAll('[aria-label="対象にできる契約"] .plan-row')[0]?.text()).toContain("その他／解約方法: あり");
  });

  it("未保存の変更があるときだけ、「未保存の変更があります」を出し、保存ボタンを有効にする。元に戻せば、消える", async () => {
    const wrapper = await mountView(planOf(PROVIDER, VIDEO), []);
    const save = () => wrapper.get('[aria-label="保存"]');
    expect(wrapper.text()).not.toContain("未保存の変更があります");
    expect(save().attributes("disabled")).toBeDefined();
    await wrapper.get('[aria-label="プロバイダを下へ"]').trigger("click");
    expect(wrapper.text()).toContain("未保存の変更があります");
    expect(save().attributes("disabled")).toBeUndefined();
    await wrapper.get('[aria-label="プロバイダを上へ"]').trigger("click");
    expect(wrapper.text()).not.toContain("未保存の変更があります");
    expect(save().attributes("disabled")).toBeDefined();
  });
});

describe("警告", () => {
  it("依存先が先に解約される並びのとき、警告を出す。並びを直すと、消える", async () => {
    const wrapper = await mountView(planOf(PROVIDER, VIDEO), []);
    const warn = wrapper.get('[aria-label="警告"]');
    expect(warn.text()).toBe("「動画」は「プロバイダ」に依存しています。「プロバイダ」が先に解約される並びです");
    await wrapper.get('[aria-label="動画を上へ"]').trigger("click");
    expect(wrapper.find('[aria-label="警告"]').exists()).toBe(false);
  });

  it("契約を加えたときも、その依存で警告を出す。複数あれば、すべて出す。計画に無い契約への依存は、警告にしない", async () => {
    const wrapper = await mountView(planOf(PROVIDER), [candidate(VIDEO), candidate(MUSIC)]);
    expect(wrapper.find('[aria-label="警告"]').exists()).toBe(false);
    await wrapper.get('[aria-label="動画を解約順に加える"]').trigger("click");
    await wrapper.get('[aria-label="音楽を解約順に加える"]').trigger("click");
    expect(wrapper.findAll(".warning-item").map((w) => w.text())).toEqual([
      "「動画」は「プロバイダ」に依存しています。「プロバイダ」が先に解約される並びです",
      "「音楽」は「プロバイダ」に依存しています。「プロバイダ」が先に解約される並びです",
    ]);
    await wrapper.get('[aria-label="プロバイダを解約順から外す"]').trigger("click");
    expect(wrapper.find('[aria-label="警告"]').exists()).toBe(false);
  });

  it("警告があっても、保存できる（警告の並びのまま、保存の入力を送る）", async () => {
    const wrapper = await mountView(planOf(PROVIDER, GYM), [candidate(VIDEO)]);
    await wrapper.get('[aria-label="動画を解約順に加える"]').trigger("click"); // 依存先（プロバイダ）が先にある並び
    expect(wrapper.find('[aria-label="警告"]').exists()).toBe(true);
    expect(wrapper.get('[aria-label="保存"]').attributes("disabled")).toBeUndefined();
    savePlan.mockResolvedValue(planOf(PROVIDER, GYM, VIDEO));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(savePlan).toHaveBeenCalledWith([1, 3, 2]);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.find('[aria-label="警告"]').exists()).toBe(true); // 保存後も、並びが同じなら警告は続く
  });
});

describe("保存", () => {
  it("並びのとおりに ID を送り、保存後は未保存の表示を消し、「保存しました」を数秒出す", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView(planOf(PROVIDER, VIDEO), [candidate(GYM)]);
    await wrapper.get('[aria-label="ジムを解約順に加える"]').trigger("click");
    await wrapper.get('[aria-label="ジムを上へ"]').trigger("click");
    savePlan.mockResolvedValue(planOf(PROVIDER, GYM, VIDEO));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(savePlan).toHaveBeenCalledWith([1, 3, 2]);
    expect(rowNames(wrapper)).toEqual(["プロバイダ", "ジム", "動画"]);
    expect(wrapper.text()).not.toContain("未保存の変更があります");
    expect(wrapper.get('[aria-label="保存"]').attributes("disabled")).toBeDefined();
    expect(wrapper.get('[role="status"]').text()).toBe("保存しました");
    await vi.advanceTimersByTimeAsync(3100);
    expect(wrapper.text()).not.toContain("保存しました");
  });

  it("空にして保存できる（空配列を送る）", async () => {
    const wrapper = await mountView(planOf(PROVIDER), []);
    await wrapper.get('[aria-label="プロバイダを解約順から外す"]').trigger("click");
    savePlan.mockResolvedValue(planOf());
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(savePlan).toHaveBeenCalledWith([]);
    expect(wrapper.get('[aria-label="解約順の一覧"]').text()).toContain("解約の対象がありません");
  });

  it("保存に失敗したら、一文を出し、編集中の並びは残す（未保存のまま）", async () => {
    const wrapper = await mountView(planOf(PROVIDER, GYM), []);
    await wrapper.get('[aria-label="プロバイダを下へ"]').trigger("click");
    savePlan.mockRejectedValueOnce(new ApiError(400, "入力が不正です"));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("入力が不正です");
    expect(rowNames(wrapper)).toEqual(["ジム", "プロバイダ"]);
    expect(wrapper.text()).toContain("未保存の変更があります");
    savePlan.mockRejectedValueOnce(new Error("boom: internal"));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("保存に失敗しました");
    expect(wrapper.text()).not.toContain("internal");
  });

  it("保存で 401 を受けたら、メッセージを出さずに殻へ通知する", async () => {
    const wrapper = await mountView(planOf(PROVIDER, GYM), []);
    await wrapper.get('[aria-label="プロバイダを下へ"]').trigger("click");
    savePlan.mockRejectedValueOnce(new AuthError(401));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
  });
});

describe("取得の失敗", () => {
  it("解約順の取得に失敗したら、内部理由を含まないメッセージを出す。401 / 403 は殻へ通知する", async () => {
    getPlan.mockRejectedValue(new Error("boom: internal"));
    getCandidates.mockResolvedValue([]);
    listContracts.mockResolvedValue([]);
    const failed = mount(CancellationView);
    await flushPromises();
    expect(failed.get('[role="alert"]').text()).toBe("読み込みに失敗しました");
    expect(failed.text()).not.toContain("internal");

    getPlan.mockRejectedValue(new AuthError(403));
    const denied = mount(CancellationView);
    await flushPromises();
    expect(denied.find('[role="alert"]').exists()).toBe(false);
    expect((denied.emitted("auth-error")?.[0]?.[0] as AuthError).status).toBe(403);
  });

  it("契約の詳細（依存契約など）を取得できなくても、編集はできる（メッセージを出す）", async () => {
    getPlan.mockResolvedValue(planOf(PROVIDER));
    getCandidates.mockResolvedValue([candidate(GYM)]);
    listContracts.mockRejectedValue(new Error("x"));
    const wrapper = mount(CancellationView);
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("契約の詳細を読み込めませんでした");
    await wrapper.get('[aria-label="ジムを解約順に加える"]').trigger("click");
    expect(rowNames(wrapper)).toEqual(["プロバイダ", "ジム"]);
    expect(wrapper.findAll(".plan-method")[1]?.text()).toBe("解約方法: 未入力");
  });
});
