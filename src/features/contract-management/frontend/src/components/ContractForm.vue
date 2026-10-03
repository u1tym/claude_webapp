<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { ApiError, AuthError } from "../api/client";
import { createContract, listContracts, updateContract } from "../api/contracts";
import type { Category, Contract, ContractInput, DatePrecision, FeeCycle, LoginMethod, Status } from "../api/types";
import {
  DATE_PRECISION_LABELS,
  FEE_CYCLE_LABELS,
  LOGIN_METHODS,
  LOGIN_METHOD_LABELS,
  STATUSES,
  contractToInput,
  emptyContractInput,
  hasContractOnlyValues,
  joinContractDate,
  splitContractDate,
  statusLabel,
  validateContractDateParts,
  withoutContractOnlyValues,
} from "../format";
import ConfirmDialog from "./ConfirmDialog.vue";
import Icon from "./Icon.vue";
import Notice from "./Notice.vue";

const props = defineProps<{
  /** 編集する契約。無いときは新規登録 */
  contract?: Contract;
  categories: Category[];
}>();

const emit = defineEmits<{
  /** 保存に成功した（応答の契約を渡す） */
  saved: [contract: Contract, created: boolean];
  cancel: [];
  "auth-error": [error: unknown];
}>();

const NAME_MAX = 200;
const isEdit = computed(() => props.contract !== undefined);

const base: ContractInput = props.contract ? contractToInput(props.contract) : emptyContractInput();
const defaultCategoryId = props.categories.find((c) => c.is_default)?.id ?? null;
const dateParts = splitContractDate(base.contract_date, base.contract_date_precision);

const form = reactive({
  name: base.name,
  has_contract: base.has_contract,
  category_id: (base.category_id ?? defaultCategoryId) as number | null,
  status: base.status as Status,
  homepage: base.homepage ?? "",
  memo: base.memo ?? "",
  login_methods: [...base.login_methods] as LoginMethod[],
  twofa_mail_address: base.twofa_mail_address ?? "",
  twofa_tel_number: base.twofa_tel_number ?? "",
  username: base.username ?? "",
  // 編集のとき、パスワードは空欄で始める（空欄のまま保存すると、保存済みの値は変わらない）
  password: "",
  registered_email: base.registered_email ?? "",
  // 契約を伴う契約だけの項目
  fee_amount: base.fee_amount === null ? "" : String(base.fee_amount),
  fee_cycle: (base.fee_cycle ?? "monthly") as FeeCycle,
  renewal_date: base.renewal_date ?? "",
  date_precision: dateParts.precision as DatePrecision | "",
  date_year: dateParts.year,
  date_month: dateParts.month,
  date_day: dateParts.day,
  trial_end_date: base.trial_end_date ?? "",
  end_date: base.end_date ?? "",
  auto_renewal: (base.auto_renewal === null ? "" : String(base.auto_renewal)) as "" | "true" | "false",
  holder_name: base.holder_name ?? "",
  member_number: base.member_number ?? "",
  cancel_notice_days: base.cancel_notice_days === null ? "" : String(base.cancel_notice_days),
  cancellation_fee: base.cancellation_fee ?? "",
  min_term_months: base.min_term_months === null ? "" : String(base.min_term_months),
  cancellation_method: base.cancellation_method ?? "",
  contact_phone: base.contact_phone ?? "",
  contact_email: base.contact_email ?? "",
  contact_hours: base.contact_hours ?? "",
  depends_on_ids: [...base.depends_on_ids],
  payment_contract_id: base.payment_contract_id as number | null,
});

const showPassword = ref(false);
const errors = reactive({ name: "", fee: "", date: "", notice: "", term: "" });
const formError = ref("");
const saving = ref(false);
const confirmingSwitch = ref(false);
const nameInput = ref<HTMLInputElement | null>(null);

// 依存契約・支払方法の選択肢（本人の削除されていない契約。自分自身は選べない）
const allContracts = ref<Contract[]>([]);
const candidatesError = ref("");
const dependencyFilter = ref("");

const hasMail = computed(() => form.login_methods.includes("2fa_mail"));
const hasTel = computed(() => form.login_methods.includes("2fa_tel"));
const isCancelled = computed(() => form.status === "cancelled");

const otherContracts = computed(() => allContracts.value.filter((c) => c.id !== props.contract?.id));
const dependencyCandidates = computed(() => {
  const word = dependencyFilter.value.trim().toLowerCase();
  return otherContracts.value.filter((c) => word === "" || c.name.toLowerCase().includes(word));
});
// 支払方法に選べるのは、金融機関の区分の契約だけ
const paymentCandidates = computed(() => otherContracts.value.filter((c) => c.category.is_financial));

function toggleMethod(method: LoginMethod, checked: boolean): void {
  if (checked && !form.login_methods.includes(method)) {
    form.login_methods.push(method);
  }
  if (!checked) {
    form.login_methods = form.login_methods.filter((m) => m !== method);
    // 選んでいない方式の送付先は、入力できない（値も消す）
    if (method === "2fa_mail") {
      form.twofa_mail_address = "";
    }
    if (method === "2fa_tel") {
      form.twofa_tel_number = "";
    }
  }
}

function textOrNull(value: string): string | null {
  const text = value.trim();
  return text === "" ? null : text;
}

function wholeNumber(value: string): number | null {
  return /^\d+$/.test(value.trim()) ? Number(value.trim()) : null;
}

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : wholeNumber(value);
}

/** フォームの内容から、「契約を伴う」として API に送る入力を作る（検査は validate で済ませておく）。 */
function buildContractBearingInput(): ContractInput {
  const date = joinContractDate({
    precision: form.date_precision,
    year: form.date_year.trim(),
    month: form.date_month.trim(),
    day: form.date_day.trim(),
  });
  const amount = optionalNumber(form.fee_amount);
  return {
    ...base,
    name: form.name.trim(),
    has_contract: true,
    category_id: form.category_id,
    status: form.status,
    homepage: textOrNull(form.homepage),
    memo: textOrNull(form.memo),
    login_methods: [...form.login_methods],
    twofa_mail_address: hasMail.value ? textOrNull(form.twofa_mail_address) : null,
    twofa_tel_number: hasTel.value ? textOrNull(form.twofa_tel_number) : null,
    username: textOrNull(form.username),
    registered_email: textOrNull(form.registered_email),
    fee_amount: amount,
    fee_cycle: amount === null ? null : form.fee_cycle,
    renewal_date: textOrNull(form.renewal_date),
    contract_date: date.contract_date,
    contract_date_precision: date.contract_date_precision,
    trial_end_date: textOrNull(form.trial_end_date),
    // 契約終了日は、ステータスが解約のときだけ持てる
    end_date: isCancelled.value ? textOrNull(form.end_date) : null,
    auto_renewal: form.auto_renewal === "" ? null : form.auto_renewal === "true",
    holder_name: textOrNull(form.holder_name),
    member_number: textOrNull(form.member_number),
    cancel_notice_days: optionalNumber(form.cancel_notice_days),
    cancellation_fee: textOrNull(form.cancellation_fee),
    min_term_months: optionalNumber(form.min_term_months),
    contact_phone: textOrNull(form.contact_phone),
    contact_email: textOrNull(form.contact_email),
    contact_hours: textOrNull(form.contact_hours),
    cancellation_method: textOrNull(form.cancellation_method),
    depends_on_ids: [...form.depends_on_ids],
    payment_contract_id: form.payment_contract_id ?? null,
  };
}

/** API に送る入力（契約を伴わないときは、契約を伴う契約だけの項目を空にする）。 */
function buildInput(): ContractInput {
  let input = buildContractBearingInput();
  if (!form.has_contract) {
    input = withoutContractOnlyValues(input);
  }
  // パスワードは、入力があるときだけ送る（空欄は「変更しない」「未設定のまま」）
  if (form.password !== "") {
    input.password = form.password;
  }
  return input;
}

function validate(): boolean {
  errors.name = "";
  errors.fee = "";
  errors.date = "";
  errors.notice = "";
  errors.term = "";
  const name = form.name.trim();
  if (name === "") {
    errors.name = "名称を入力してください";
  } else if (name.length > NAME_MAX) {
    errors.name = `名称は ${NAME_MAX} 文字以内で入力してください`;
  }
  if (form.has_contract) {
    if (form.fee_amount.trim() !== "" && wholeNumber(form.fee_amount) === null) {
      errors.fee = "維持費は 0 以上の整数で入力してください";
    }
    errors.date =
      validateContractDateParts({
        precision: form.date_precision,
        year: form.date_year.trim(),
        month: form.date_month.trim(),
        day: form.date_day.trim(),
      }) ?? "";
    if (form.cancel_notice_days.trim() !== "" && wholeNumber(form.cancel_notice_days) === null) {
      errors.notice = "解約の受付期限は 0 以上の整数（日数）で入力してください";
    }
    if (form.min_term_months.trim() !== "" && wholeNumber(form.min_term_months) === null) {
      errors.term = "最低契約期間は 0 以上の整数（月数）で入力してください";
    }
  }
  return Object.values(errors).every((e) => e === "");
}

async function submit(): Promise<void> {
  formError.value = "";
  if (!validate()) {
    return;
  }
  // 契約を伴わないにするとき、消える項目に値が入っていれば、保存の前に確認する
  if (!form.has_contract && hasContractOnlyValues(buildContractBearingInput())) {
    confirmingSwitch.value = true;
    return;
  }
  await save();
}

async function save(): Promise<void> {
  confirmingSwitch.value = false;
  saving.value = true;
  try {
    const input = buildInput();
    const saved = props.contract ? await updateContract(props.contract.id, input) : await createContract(input);
    emit("saved", saved, !props.contract);
  } catch (error) {
    if (error instanceof AuthError) {
      emit("auth-error", error);
    } else if (error instanceof ApiError) {
      // 本文の一文（内部理由を含まない）をそのまま示す
      formError.value = error.message;
    } else {
      formError.value = "保存に失敗しました";
    }
  } finally {
    saving.value = false;
  }
}

async function loadCandidates(): Promise<void> {
  try {
    allContracts.value = await listContracts();
  } catch (error) {
    if (error instanceof AuthError) {
      emit("auth-error", error);
      return;
    }
    candidatesError.value = "依存契約・支払方法の選択肢を読み込めませんでした";
  }
}

onMounted(async () => {
  void loadCandidates();
  await nextTick();
  nameInput.value?.focus();
});
</script>

<template>
  <!-- 背景（オーバーレイ）を押しても閉じない。閉じるのは、ダイアログ内のボタン（キャンセル・保存）だけ -->
  <div class="dialog-overlay">
    <form
      class="dialog dialog-wide dialog-form"
      role="dialog"
      aria-modal="true"
      :aria-label="isEdit ? '契約の編集' : '契約の新規登録'"
      novalidate
      @submit.prevent="submit"
      @keydown.esc.prevent="emit('cancel')"
    >
      <h2 class="detail-title">{{ isEdit ? "契約の編集" : "契約の新規登録" }}</h2>
      <Notice kind="error" :message="formError" />

      <div class="form-body">
        <fieldset class="form-section">
          <legend class="detail-heading">基本</legend>
          <label class="field">
            <span class="field-label">名称（必須）</span>
            <input ref="nameInput" v-model="form.name" type="text" aria-label="名称" autocomplete="off" />
            <span v-if="errors.name" class="field-error" role="alert">{{ errors.name }}</span>
          </label>
          <div class="field">
            <span class="field-label">契約</span>
            <span class="radio-group" role="radiogroup" aria-label="契約の有無">
              <label class="check-label"><input v-model="form.has_contract" type="radio" :value="true" name="has_contract" />契約を伴う</label>
              <label class="check-label"><input v-model="form.has_contract" type="radio" :value="false" name="has_contract" />契約を伴わない</label>
            </span>
          </div>
          <label class="field">
            <span class="field-label">区分</span>
            <select v-model="form.category_id" class="select" aria-label="区分">
              <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">ステータス</span>
            <select v-model="form.status" class="select" aria-label="ステータス">
              <option v-for="s in STATUSES" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">ホームページ</span>
            <input v-model="form.homepage" type="text" aria-label="ホームページ" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">メモ</span>
            <textarea v-model="form.memo" rows="3" aria-label="メモ"></textarea>
          </label>
        </fieldset>

        <fieldset class="form-section">
          <legend class="detail-heading">ログイン</legend>
          <div class="field">
            <span class="field-label">ログイン方法</span>
            <span class="radio-group">
              <label v-for="m in LOGIN_METHODS" :key="m" class="check-label">
                <input
                  type="checkbox"
                  :checked="form.login_methods.includes(m)"
                  :aria-label="LOGIN_METHOD_LABELS[m]"
                  @change="toggleMethod(m, ($event.target as HTMLInputElement).checked)"
                />
                {{ LOGIN_METHOD_LABELS[m] }}
              </label>
            </span>
          </div>
          <label v-if="hasMail" class="field">
            <span class="field-label">2段階認証（メール）の送付先</span>
            <input v-model="form.twofa_mail_address" type="text" aria-label="2段階認証（メール）の送付先" autocomplete="off" />
          </label>
          <label v-if="hasTel" class="field">
            <span class="field-label">2段階認証（TEL）の送付先</span>
            <input v-model="form.twofa_tel_number" type="text" aria-label="2段階認証（TEL）の送付先" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">ユーザ名</span>
            <input v-model="form.username" type="text" aria-label="ユーザ名" autocomplete="off" />
          </label>
          <div class="field">
            <span class="field-label">パスワード</span>
            <span class="password-input">
              <textarea
                v-model="form.password"
                rows="2"
                aria-label="パスワード"
                autocomplete="new-password"
                spellcheck="false"
                :class="{ masked: !showPassword }"
                :placeholder="isEdit ? '変更するときだけ入力' : ''"
              ></textarea>
              <button class="btn-text btn-compact" type="button" :aria-label="showPassword ? 'パスワードを隠す' : 'パスワードを表示'" @click="showPassword = !showPassword">
                {{ showPassword ? "隠す" : "表示" }}
              </button>
            </span>
          </div>
          <label class="field">
            <span class="field-label">登録メールアドレス</span>
            <input v-model="form.registered_email" type="text" aria-label="登録メールアドレス" autocomplete="off" />
          </label>
        </fieldset>

        <!-- 契約を伴う契約だけの項目。契約を伴わないときは出さない -->
        <fieldset v-if="form.has_contract" class="form-section" aria-label="契約">
          <legend class="detail-heading">契約</legend>
          <div class="field">
            <span class="field-label">維持費</span>
            <span class="inline-inputs">
              <input v-model="form.fee_amount" type="text" inputmode="numeric" aria-label="維持費の金額" autocomplete="off" />
              <span class="radio-group" role="radiogroup" aria-label="維持費の周期">
                <label v-for="(label, cycle) in FEE_CYCLE_LABELS" :key="cycle" class="check-label">
                  <input v-model="form.fee_cycle" type="radio" :value="cycle" name="fee_cycle" />{{ label }}
                </label>
              </span>
            </span>
            <span v-if="errors.fee" class="field-error" role="alert">{{ errors.fee }}</span>
          </div>
          <label class="field">
            <span class="field-label">更新日</span>
            <input v-model="form.renewal_date" type="date" aria-label="更新日" />
          </label>
          <div class="field">
            <span class="field-label">契約日</span>
            <span class="inline-inputs">
              <select v-model="form.date_precision" class="select" aria-label="契約日の精度">
                <option value="">指定しない</option>
                <option v-for="(label, precision) in DATE_PRECISION_LABELS" :key="precision" :value="precision">{{ label }}</option>
              </select>
              <template v-if="form.date_precision === 'day' || form.date_precision === 'month' || form.date_precision === 'year'">
                <input v-model="form.date_year" type="text" inputmode="numeric" aria-label="契約日の年" placeholder="年" autocomplete="off" class="input-short" />
                <input v-if="form.date_precision !== 'year'" v-model="form.date_month" type="text" inputmode="numeric" aria-label="契約日の月" placeholder="月" autocomplete="off" class="input-short" />
                <input v-if="form.date_precision === 'day'" v-model="form.date_day" type="text" inputmode="numeric" aria-label="契約日の日" placeholder="日" autocomplete="off" class="input-short" />
              </template>
            </span>
            <span v-if="errors.date" class="field-error" role="alert">{{ errors.date }}</span>
          </div>
          <label class="field">
            <span class="field-label">無料期間の終了日</span>
            <input v-model="form.trial_end_date" type="date" aria-label="無料期間の終了日" />
          </label>
          <label v-if="isCancelled" class="field">
            <span class="field-label">契約終了日</span>
            <input v-model="form.end_date" type="date" aria-label="契約終了日" />
          </label>
          <label class="field">
            <span class="field-label">自動更新</span>
            <select v-model="form.auto_renewal" class="select" aria-label="自動更新">
              <option value="">未設定</option>
              <option value="true">あり</option>
              <option value="false">なし</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">契約者名義</span>
            <input v-model="form.holder_name" type="text" aria-label="契約者名義" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">会員番号・契約番号</span>
            <input v-model="form.member_number" type="text" aria-label="会員番号・契約番号" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">解約の受付期限（更新日の何日前まで）</span>
            <input v-model="form.cancel_notice_days" type="text" inputmode="numeric" aria-label="解約の受付期限（日数）" autocomplete="off" />
            <span v-if="errors.notice" class="field-error" role="alert">{{ errors.notice }}</span>
          </label>
          <label class="field">
            <span class="field-label">解約手数料・違約金</span>
            <input v-model="form.cancellation_fee" type="text" aria-label="解約手数料・違約金" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">最低契約期間（月数）</span>
            <input v-model="form.min_term_months" type="text" inputmode="numeric" aria-label="最低契約期間（月数）" autocomplete="off" />
            <span v-if="errors.term" class="field-error" role="alert">{{ errors.term }}</span>
          </label>
          <label class="field">
            <span class="field-label">解約方法</span>
            <textarea v-model="form.cancellation_method" rows="4" aria-label="解約方法"></textarea>
          </label>
        </fieldset>

        <fieldset v-if="form.has_contract" class="form-section" aria-label="問い合わせ先">
          <legend class="detail-heading">問い合わせ先</legend>
          <label class="field">
            <span class="field-label">電話番号</span>
            <input v-model="form.contact_phone" type="text" aria-label="問い合わせ先の電話番号" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">メールアドレス</span>
            <input v-model="form.contact_email" type="text" aria-label="問い合わせ先のメールアドレス" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">受付時間</span>
            <input v-model="form.contact_hours" type="text" aria-label="問い合わせ先の受付時間" autocomplete="off" />
          </label>
        </fieldset>

        <fieldset v-if="form.has_contract" class="form-section" aria-label="関連">
          <legend class="detail-heading">関連</legend>
          <Notice kind="error" :message="candidatesError" />
          <div class="field">
            <span class="field-label">依存契約</span>
            <span class="picker">
              <input v-model="dependencyFilter" type="search" aria-label="依存契約を絞り込む" placeholder="名称で絞り込む" autocomplete="off" />
              <ul class="picker-list" aria-label="依存契約の選択肢">
                <li v-for="c in dependencyCandidates" :key="c.id">
                  <label class="check-label">
                    <input v-model="form.depends_on_ids" type="checkbox" :value="c.id" :aria-label="`${c.name}を依存契約にする`" />
                    {{ c.name }}<span class="caption">（{{ c.category.name }}）</span>
                  </label>
                </li>
                <li v-if="dependencyCandidates.length === 0" class="caption">選べる契約がありません</li>
              </ul>
            </span>
          </div>
          <div class="field">
            <span class="field-label">支払方法</span>
            <span class="picker">
              <select v-model="form.payment_contract_id" class="select" aria-label="支払方法">
                <option :value="null">選ばない</option>
                <option v-for="c in paymentCandidates" :key="c.id" :value="c.id">{{ c.name }}（{{ c.category.name }}）</option>
              </select>
              <span v-if="paymentCandidates.length === 0" class="caption">金融機関の区分の契約がありません</span>
            </span>
          </div>
        </fieldset>
      </div>

      <div class="dialog-actions">
        <button class="btn-secondary btn-icon" type="button" aria-label="キャンセル" title="キャンセル" @click="emit('cancel')">
          <Icon name="close" />
        </button>
        <button class="btn-primary btn-icon" type="submit" aria-label="保存" title="保存" :disabled="saving">
          <Icon name="check" />
        </button>
      </div>

      <ConfirmDialog
        v-if="confirmingSwitch"
        title="契約を伴わないへの変更"
        message="契約を伴わないに変更すると、契約に関する項目が消えます。保存しますか？"
        note="維持費・更新日・契約日・解約方法・依存契約・支払方法などが消えます。"
        @confirm="save"
        @cancel="confirmingSwitch = false"
      />
    </form>
  </div>
</template>
