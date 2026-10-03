import { describe, expect, it } from "vitest";
import type { Contract } from "../src/api/types";
import {
  CONTRACT_ONLY_KEYS,
  contractToInput,
  emptyContractInput,
  emptyDateParts,
  formatAutoRenewal,
  formatContractDate,
  formatFee,
  formatIsoDate,
  formatMinTerm,
  formatNoticeDays,
  hasContractOnlyValues,
  joinContractDate,
  loginMethodsLabel,
  orDash,
  splitContractDate,
  statusLabel,
  validateContractDateParts,
  withoutContractOnlyValues,
} from "../src/format";

describe("表示名", () => {
  it("ステータス・ログイン方法", () => {
    expect(statusLabel("active")).toBe("有効");
    expect(statusLabel("paused")).toBe("休止中");
    expect(statusLabel("cancelled")).toBe("解約");
    expect(loginMethodsLabel([])).toBe("-");
    expect(loginMethodsLabel(["password", "2fa_mail", "2fa_tel", "passkey"])).toBe(
      "ユーザ名とパスワード、2段階認証（メール）、2段階認証（TEL）、パスキー",
    );
  });

  it("維持費は「月額 990 円」「年間 12,000 円」。無いときは「-」", () => {
    expect(formatFee(990, "monthly")).toBe("月額 990 円");
    expect(formatFee(12000, "yearly")).toBe("年間 12,000 円");
    expect(formatFee(0, "yearly")).toBe("年間 0 円");
    expect(formatFee(null, null)).toBe("-");
    expect(formatFee(100, null)).toBe("-");
  });

  it("日付・自動更新・解約の受付期限・最低契約期間・空の値", () => {
    expect(formatIsoDate("2026-11-05")).toBe("2026年11月5日");
    expect(formatIsoDate(null)).toBe("-");
    expect(formatAutoRenewal(true)).toBe("あり");
    expect(formatAutoRenewal(false)).toBe("なし");
    expect(formatAutoRenewal(null)).toBe("未設定");
    expect(formatNoticeDays(7)).toBe("更新日の 7 日前まで");
    expect(formatNoticeDays(0)).toBe("更新日の 0 日前まで");
    expect(formatNoticeDays(null)).toBe("-");
    expect(formatMinTerm(12)).toBe("12 か月");
    expect(formatMinTerm(null)).toBe("-");
    expect(orDash(null)).toBe("-");
    expect(orDash("")).toBe("-");
    expect(orDash("あ")).toBe("あ");
  });

  it("契約日は精度に応じた形式。不明は「不明」、持たないときは「-」", () => {
    expect(formatContractDate("2020-04-03", "day")).toBe("2020年4月3日");
    expect(formatContractDate("2020-04", "month")).toBe("2020年4月");
    expect(formatContractDate("2020", "year")).toBe("2020年");
    expect(formatContractDate(null, "unknown")).toBe("不明");
    expect(formatContractDate(null, null)).toBe("-");
  });
});

describe("契約日の入力", () => {
  it("API の値を入力欄に分け、入力欄の値を API の形にする（往復で同じ）", () => {
    for (const [value, precision] of [
      ["2020-04-03", "day"],
      ["2020-04", "month"],
      ["2020", "year"],
      [null, "unknown"],
      [null, null],
    ] as const) {
      const parts = splitContractDate(value, precision);
      expect(joinContractDate(parts)).toEqual({ contract_date: value, contract_date_precision: precision });
    }
    expect(splitContractDate("2020-04-03", "day")).toEqual({ precision: "day", year: "2020", month: "4", day: "3" });
    expect(splitContractDate("2020-04", "month")).toEqual({ precision: "month", year: "2020", month: "4", day: "" });
  });

  it("1 桁の月・日は 0 を補って送る", () => {
    expect(joinContractDate({ precision: "day", year: "2020", month: "4", day: "3" }).contract_date).toBe("2020-04-03");
    expect(joinContractDate({ precision: "month", year: "2020", month: "9", day: "" }).contract_date).toBe("2020-09");
  });

  it("入力の検査（精度が不明・未選択のときは日付を求めない）", () => {
    expect(validateContractDateParts(emptyDateParts())).toBeNull();
    expect(validateContractDateParts({ precision: "unknown", year: "", month: "", day: "" })).toBeNull();
    expect(validateContractDateParts({ precision: "year", year: "2020", month: "", day: "" })).toBeNull();
    expect(validateContractDateParts({ precision: "year", year: "20", month: "", day: "" })).toMatch(/年/);
    expect(validateContractDateParts({ precision: "month", year: "2020", month: "13", day: "" })).toMatch(/月/);
    expect(validateContractDateParts({ precision: "month", year: "2020", month: "", day: "" })).toMatch(/月/);
    expect(validateContractDateParts({ precision: "month", year: "2020", month: "12", day: "" })).toBeNull();
    expect(validateContractDateParts({ precision: "day", year: "2020", month: "2", day: "30" })).toMatch(/日/);
    expect(validateContractDateParts({ precision: "day", year: "2024", month: "2", day: "29" })).toBeNull();
    expect(validateContractDateParts({ precision: "day", year: "2023", month: "2", day: "29" })).toMatch(/日/);
    expect(validateContractDateParts({ precision: "day", year: "2020", month: "4", day: "" })).toMatch(/日/);
  });
});

function sample(): Contract {
  return {
    id: 1, name: "動画", has_contract: true, category: { id: 3, name: "動画配信", is_financial: false }, status: "paused",
    homepage: "https://e.com", memo: null, login_methods: ["password", "2fa_mail"], twofa_mail_address: "m@e.com",
    twofa_tel_number: null, username: "taro", has_password: true, password_unset: false, registered_email: "r@e.com",
    fee_amount: 990, fee_cycle: "monthly", renewal_date: "2026-11-05", contract_date: "2020-04",
    contract_date_precision: "month", trial_end_date: null, end_date: null, auto_renewal: true, holder_name: "山田",
    member_number: "A-1", cancel_notice_days: 7, cancellation_fee: "なし", min_term_months: 12, contact_phone: "0120",
    contact_email: "s@e.com", contact_hours: "平日", cancellation_method: "マイページ",
    depends_on: [{ id: 8, name: "プロバイダ" }, { id: 9, name: "回線" }], payment_contract: { id: 5, name: "Aカード" },
    depended_by: [{ id: 20, name: "音楽" }], payment_for: [],
  };
}

describe("契約の入力", () => {
  it("新規登録の既定値は、契約を伴う・有効・区分は未指定", () => {
    const input = emptyContractInput();
    expect(input).toMatchObject({ name: "", has_contract: true, status: "active", category_id: null, login_methods: [], depends_on_ids: [] });
    expect("password" in input).toBe(false);
    expect(hasContractOnlyValues(input)).toBe(false);
  });

  it("編集フォームの初期値は、現在の値をすべて入れる（パスワードは含めない）", () => {
    const input = contractToInput(sample());
    expect(input.category_id).toBe(3);
    expect(input.depends_on_ids).toEqual([8, 9]);
    expect(input.payment_contract_id).toBe(5);
    expect(input.login_methods).toEqual(["password", "2fa_mail"]);
    expect("password" in input).toBe(false);
    // 元の契約を変えない（配列を共有しない）
    input.login_methods.push("passkey");
    expect(sample().login_methods).toEqual(["password", "2fa_mail"]);
  });

  it("契約を伴う契約だけの項目に値があるかを判定する", () => {
    expect(hasContractOnlyValues(contractToInput(sample()))).toBe(true);
    for (const key of CONTRACT_ONLY_KEYS) {
      const input = emptyContractInput();
      expect(hasContractOnlyValues(input)).toBe(false);
      const value: unknown = key === "depends_on_ids" ? [1] : key === "auto_renewal" ? false : key.endsWith("_months") || key.endsWith("_days") || key === "fee_amount" || key === "payment_contract_id" ? 0 : "x";
      (input as Record<string, unknown>)[key] = value;
      expect(hasContractOnlyValues(input), key).toBe(true);
    }
  });

  it("契約を伴わないとして送る入力は、契約の項目をすべて空にし、ほかの項目は残す", () => {
    const input = withoutContractOnlyValues(contractToInput(sample()));
    expect(input.has_contract).toBe(false);
    expect(hasContractOnlyValues(input)).toBe(false);
    expect(input.depends_on_ids).toEqual([]);
    expect(input).toMatchObject({ name: "動画", status: "paused", username: "taro", category_id: 3, homepage: "https://e.com", login_methods: ["password", "2fa_mail"], twofa_mail_address: "m@e.com" });
  });
});
