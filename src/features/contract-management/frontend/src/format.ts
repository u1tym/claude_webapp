// 表示名・表示形式・入力の補助（ui-design.md）。画面の文言をここに集める。

import type { Contract, ContractInput, DatePrecision, FeeCycle, LoginMethod, Status } from "./api/types";

export const STATUS_LABELS: Record<Status, string> = {
  active: "有効",
  paused: "休止中",
  cancelled: "解約",
};

export const FEE_CYCLE_LABELS: Record<FeeCycle, string> = {
  monthly: "月額",
  yearly: "年間",
};

export const LOGIN_METHOD_LABELS: Record<LoginMethod, string> = {
  password: "ユーザ名とパスワード",
  passkey: "パスキー",
  "2fa_mail": "2段階認証（メール）",
  "2fa_tel": "2段階認証（TEL）",
};

export const DATE_PRECISION_LABELS: Record<DatePrecision, string> = {
  day: "年月日",
  month: "年月",
  year: "年",
  unknown: "不明",
};

export const STATUSES: Status[] = ["active", "paused", "cancelled"];
export const LOGIN_METHODS: LoginMethod[] = ["password", "passkey", "2fa_mail", "2fa_tel"];

/** 設定されていない項目の表示 */
export const EMPTY = "-";

export function statusLabel(status: Status): string {
  return STATUS_LABELS[status];
}

export function loginMethodsLabel(methods: LoginMethod[]): string {
  return methods.length === 0 ? EMPTY : methods.map((m) => LOGIN_METHOD_LABELS[m]).join("、");
}

/** 維持費。例: 「月額 990 円」「年間 12,000 円」。無いときは「-」。 */
export function formatFee(amount: number | null, cycle: FeeCycle | null): string {
  if (amount === null || cycle === null) {
    return EMPTY;
  }
  return `${FEE_CYCLE_LABELS[cycle]} ${amount.toLocaleString("ja-JP")} 円`;
}

/** `YYYY-MM-DD` を「2026年11月5日」にする。無いときは「-」。 */
export function formatIsoDate(value: string | null): string {
  if (value === null) {
    return EMPTY;
  }
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (m === null) {
    return value;
  }
  return `${Number(m[1])}年${Number(m[2])}月${Number(m[3])}日`;
}

/** 契約日。精度に応じて「2020年4月3日」「2020年4月」「2020年」。精度が不明のときは「不明」、契約日を持たないときは「-」。 */
export function formatContractDate(value: string | null, precision: DatePrecision | null): string {
  if (precision === "unknown") {
    return "不明";
  }
  if (value === null || precision === null) {
    return EMPTY;
  }
  const parts = value.split("-").map(Number);
  if (precision === "day") {
    return `${parts[0]}年${parts[1]}月${parts[2]}日`;
  }
  if (precision === "month") {
    return `${parts[0]}年${parts[1]}月`;
  }
  return `${parts[0]}年`;
}

/** ブラウザのローカル日付（日本時間）を「2026年10月3日」にする。toISOString は UTC のため、使わない。 */
export function formatLocalDate(date: Date): string {
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

export function formatAutoRenewal(value: boolean | null): string {
  if (value === null) {
    return "未設定";
  }
  return value ? "あり" : "なし";
}

/** 解約の受付期限（更新日の何日前までか） */
export function formatNoticeDays(days: number | null): string {
  return days === null ? EMPTY : `更新日の ${days} 日前まで`;
}

/** 最低契約期間 */
export function formatMinTerm(months: number | null): string {
  return months === null ? EMPTY : `${months} か月`;
}

/** リンクにしてよい URL（http / https）だけを返す。それ以外（javascript: など）は null。 */
export function safeHttpUrl(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  const text = value.trim();
  return /^https?:\/\//i.test(text) ? text : null;
}

export function orDash(value: string | null): string {
  return value === null || value === "" ? EMPTY : value;
}

// ---- 契約日の入力（精度に応じて、年月日・年月・年を入力する） ----

export type ContractDateParts = {
  precision: DatePrecision | "";
  year: string;
  month: string;
  day: string;
};

export function emptyDateParts(): ContractDateParts {
  return { precision: "", year: "", month: "", day: "" };
}

/** API の契約日（精度に応じた形式の文字列）を、入力欄の値に分ける。 */
export function splitContractDate(value: string | null, precision: DatePrecision | null): ContractDateParts {
  const parts = emptyDateParts();
  if (precision === null) {
    return parts;
  }
  parts.precision = precision;
  if (value !== null && precision !== "unknown") {
    const [year = "", month = "", day = ""] = value.split("-");
    parts.year = year;
    parts.month = precision === "year" ? "" : String(Number(month));
    parts.day = precision === "day" ? String(Number(day)) : "";
  }
  return parts;
}

/** 入力欄の値の検査。問題があれば、メッセージを返す（無ければ null）。精度が「不明」または未選択のときは、日付の入力を求めない。 */
export function validateContractDateParts(parts: ContractDateParts): string | null {
  if (parts.precision === "" || parts.precision === "unknown") {
    return null;
  }
  if (!/^\d{4}$/.test(parts.year)) {
    return "契約日の年は 4 桁で入力してください";
  }
  if (parts.precision === "year") {
    return null;
  }
  const month = Number(parts.month);
  if (!/^\d{1,2}$/.test(parts.month) || month < 1 || month > 12) {
    return "契約日の月は 1〜12 で入力してください";
  }
  if (parts.precision === "month") {
    return null;
  }
  const day = Number(parts.day);
  const last = new Date(Number(parts.year), month, 0).getDate();
  if (!/^\d{1,2}$/.test(parts.day) || day < 1 || day > last) {
    return "契約日の日が正しくありません";
  }
  return null;
}

/** 入力欄の値を、API に送る形（契約日と精度）にする。検査を通ったものだけを渡す。 */
export function joinContractDate(parts: ContractDateParts): {
  contract_date: string | null;
  contract_date_precision: DatePrecision | null;
} {
  if (parts.precision === "") {
    return { contract_date: null, contract_date_precision: null };
  }
  if (parts.precision === "unknown") {
    return { contract_date: null, contract_date_precision: "unknown" };
  }
  const mm = parts.month.padStart(2, "0");
  const dd = parts.day.padStart(2, "0");
  const text =
    parts.precision === "year" ? parts.year : parts.precision === "month" ? `${parts.year}-${mm}` : `${parts.year}-${mm}-${dd}`;
  return { contract_date: text, contract_date_precision: parts.precision };
}

// ---- 契約の入力（登録・編集フォーム） ----

/** 新規登録の既定値。区分は未指定（サーバが「その他」にする）、ステータスは有効、契約を伴う。 */
export function emptyContractInput(): ContractInput {
  return {
    name: "",
    has_contract: true,
    category_id: null,
    status: "active",
    homepage: null,
    memo: null,
    login_methods: [],
    twofa_mail_address: null,
    twofa_tel_number: null,
    username: null,
    registered_email: null,
    fee_amount: null,
    fee_cycle: null,
    renewal_date: null,
    contract_date: null,
    contract_date_precision: null,
    trial_end_date: null,
    end_date: null,
    auto_renewal: null,
    holder_name: null,
    member_number: null,
    cancel_notice_days: null,
    cancellation_fee: null,
    min_term_months: null,
    contact_phone: null,
    contact_email: null,
    contact_hours: null,
    cancellation_method: null,
    depends_on_ids: [],
    payment_contract_id: null,
  };
}

/** 編集フォームの初期値。PATCH は password 以外の全項目を送るので、現在の値をすべて入れる。password は含めない。 */
export function contractToInput(c: Contract): ContractInput {
  return {
    name: c.name,
    has_contract: c.has_contract,
    category_id: c.category.id,
    status: c.status,
    homepage: c.homepage,
    memo: c.memo,
    login_methods: [...c.login_methods],
    twofa_mail_address: c.twofa_mail_address,
    twofa_tel_number: c.twofa_tel_number,
    username: c.username,
    registered_email: c.registered_email,
    fee_amount: c.fee_amount,
    fee_cycle: c.fee_cycle,
    renewal_date: c.renewal_date,
    contract_date: c.contract_date,
    contract_date_precision: c.contract_date_precision,
    trial_end_date: c.trial_end_date,
    end_date: c.end_date,
    auto_renewal: c.auto_renewal,
    holder_name: c.holder_name,
    member_number: c.member_number,
    cancel_notice_days: c.cancel_notice_days,
    cancellation_fee: c.cancellation_fee,
    min_term_months: c.min_term_months,
    contact_phone: c.contact_phone,
    contact_email: c.contact_email,
    contact_hours: c.contact_hours,
    cancellation_method: c.cancellation_method,
    depends_on_ids: c.depends_on.map((d) => d.id),
    payment_contract_id: c.payment_contract?.id ?? null,
  };
}

/** 契約を伴わない契約が持たない項目（契約を伴わないに切り替えると、消える） */
export const CONTRACT_ONLY_KEYS = [
  "fee_amount",
  "fee_cycle",
  "renewal_date",
  "contract_date",
  "contract_date_precision",
  "trial_end_date",
  "end_date",
  "auto_renewal",
  "holder_name",
  "member_number",
  "cancel_notice_days",
  "cancellation_fee",
  "min_term_months",
  "contact_phone",
  "contact_email",
  "contact_hours",
  "cancellation_method",
  "depends_on_ids",
  "payment_contract_id",
] as const satisfies readonly (keyof ContractInput)[];

/** 契約を伴わないに切り替えたとき、消える項目に値が入っているか（保存時の確認に使う）。 */
export function hasContractOnlyValues(input: ContractInput): boolean {
  return CONTRACT_ONLY_KEYS.some((key) => {
    const value = input[key];
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return value !== null && value !== "";
  });
}

/** 契約を伴わない契約として送る入力にする（契約を伴う契約だけの項目を空にし、契約終了日の条件も外す）。 */
export function withoutContractOnlyValues(input: ContractInput): ContractInput {
  return {
    ...input,
    has_contract: false,
    fee_amount: null,
    fee_cycle: null,
    renewal_date: null,
    contract_date: null,
    contract_date_precision: null,
    trial_end_date: null,
    end_date: null,
    auto_renewal: null,
    holder_name: null,
    member_number: null,
    cancel_notice_days: null,
    cancellation_fee: null,
    min_term_months: null,
    contact_phone: null,
    contact_email: null,
    contact_hours: null,
    cancellation_method: null,
    depends_on_ids: [],
    payment_contract_id: null,
  };
}
