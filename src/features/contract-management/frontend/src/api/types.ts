// api-design.md の応答・要求の型。any は使わない。

export type Status = "active" | "paused" | "cancelled";
export type FeeCycle = "yearly" | "monthly";
export type LoginMethod = "password" | "passkey" | "2fa_mail" | "2fa_tel";
export type DatePrecision = "day" | "month" | "year" | "unknown";

export type Category = {
  id: number;
  name: string;
  is_default: boolean;
  is_financial: boolean;
};

export type CategoryInput = {
  name: string;
  is_financial: boolean;
};

export type ContractRef = { id: number; name: string };

/** 契約の表現（Contract）。パスワードの値は含まれない（has_password / password_unset だけ）。 */
export type Contract = {
  id: number;
  name: string;
  has_contract: boolean;
  category: { id: number; name: string; is_financial: boolean };
  status: Status;
  homepage: string | null;
  memo: string | null;
  login_methods: LoginMethod[];
  twofa_mail_address: string | null;
  twofa_tel_number: string | null;
  username: string | null;
  has_password: boolean;
  password_unset: boolean;
  registered_email: string | null;
  fee_amount: number | null;
  fee_cycle: FeeCycle | null;
  renewal_date: string | null;
  contract_date: string | null;
  contract_date_precision: DatePrecision | null;
  trial_end_date: string | null;
  end_date: string | null;
  auto_renewal: boolean | null;
  holder_name: string | null;
  member_number: string | null;
  cancel_notice_days: number | null;
  cancellation_fee: string | null;
  min_term_months: number | null;
  contact_phone: string | null;
  contact_email: string | null;
  contact_hours: string | null;
  cancellation_method: string | null;
  depends_on: ContractRef[];
  payment_contract: ContractRef | null;
  depended_by: ContractRef[];
  payment_for: ContractRef[];
};

/** 契約の入力（登録・更新）。PATCH は password 以外の全項目を送る。password は、変更するときだけ指定する。 */
export type ContractInput = {
  name: string;
  has_contract: boolean;
  category_id: number | null;
  status: Status;
  homepage: string | null;
  memo: string | null;
  login_methods: LoginMethod[];
  twofa_mail_address: string | null;
  twofa_tel_number: string | null;
  username: string | null;
  password?: string;
  registered_email: string | null;
  fee_amount: number | null;
  fee_cycle: FeeCycle | null;
  renewal_date: string | null;
  contract_date: string | null;
  contract_date_precision: DatePrecision | null;
  trial_end_date: string | null;
  end_date: string | null;
  auto_renewal: boolean | null;
  holder_name: string | null;
  member_number: string | null;
  cancel_notice_days: number | null;
  cancellation_fee: string | null;
  min_term_months: number | null;
  contact_phone: string | null;
  contact_email: string | null;
  contact_hours: string | null;
  cancellation_method: string | null;
  depends_on_ids: number[];
  payment_contract_id: number | null;
};

export type ContractFilters = {
  keyword?: string;
  category_id?: number | null;
  status?: Status | "";
  has_contract?: boolean | null;
  password_unset?: boolean;
};

export type AccountItem = {
  id: number;
  name: string;
  username: string | null;
  homepage: string | null;
  has_password: boolean;
  password_unset: boolean;
};

export type PlanItem = {
  position: number;
  contract_id: number;
  name: string;
  cancellation_method: string | null;
  depends_on: ContractRef[];
};

export type PlanWarning = {
  contract_id: number;
  name: string;
  depends_on_contract_id: number;
  depends_on_name: string;
};

export type Plan = {
  items: PlanItem[];
  warnings: PlanWarning[];
};

export type PlanCandidate = {
  id: number;
  name: string;
  category_name: string;
  has_cancellation_method: boolean;
};
