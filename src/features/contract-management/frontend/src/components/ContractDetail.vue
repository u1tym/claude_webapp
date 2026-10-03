<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { getContractPassword } from "../api/contracts";
import { AuthError } from "../api/client";
import type { Contract } from "../api/types";
import {
  EMPTY,
  formatAutoRenewal,
  formatContractDate,
  formatFee,
  formatIsoDate,
  formatMinTerm,
  formatNoticeDays,
  loginMethodsLabel,
  orDash,
  safeHttpUrl,
  statusLabel,
} from "../format";
import CopyButton from "./CopyButton.vue";
import Icon from "./Icon.vue";
import Notice from "./Notice.vue";
import PasswordField from "./PasswordField.vue";

const props = defineProps<{ contract: Contract }>();

const emit = defineEmits<{
  close: [];
  edit: [];
  delete: [];
  /** 関連する契約の名称を選んだ（その契約の詳細に切り替える） */
  open: [id: number];
  /** 値の取得・コピーの失敗（AuthError を含む）。画面が処理する */
  error: [error: unknown];
}>();

const closeButton = ref<HTMLButtonElement | null>(null);

// ログインの項目: パスワードを使う契約か、パスワードを持っている契約だけに、パスワードの欄を出す
const showsPassword = computed(() => props.contract.has_password || props.contract.password_unset);
const hasFullContract = computed(() => props.contract.has_contract);
// 契約を伴わない契約でも、他の契約から参照されているとき（例: 支払方法のカード）は、その逆引きを出す
const showsRelated = computed(
  () => hasFullContract.value || props.contract.depended_by.length > 0 || props.contract.payment_for.length > 0,
);
const homepageUrl = computed(() => safeHttpUrl(props.contract.homepage));

function fetchPassword(): Promise<string | null> {
  return getContractPassword(props.contract.id);
}

// 値の取得・コピーの失敗。401 / 403 は殻へ通知し、そのほかは、ダイアログ内に一文を出す
const actionError = ref("");

function onChildError(error: unknown): void {
  if (error instanceof AuthError) {
    emit("error", error);
    return;
  }
  actionError.value = "操作に失敗しました";
}

onMounted(async () => {
  await nextTick();
  closeButton.value?.focus();
});
</script>

<template>
  <!-- 背景（オーバーレイ）を押しても閉じない。閉じるのは、ダイアログ内のボタンと Esc だけ -->
  <div class="dialog-overlay">
    <div class="dialog dialog-wide" role="dialog" aria-modal="true" :aria-label="`${contract.name}の詳細`" @keydown.esc.prevent="emit('close')">
      <header class="detail-header">
        <h2 class="detail-title">{{ contract.name }}</h2>
        <button ref="closeButton" class="btn-secondary btn-icon" type="button" aria-label="閉じる" title="閉じる" @click="emit('close')">
          <Icon name="close" />
        </button>
      </header>

      <Notice kind="error" :message="actionError" />

      <div class="detail-body">
        <section class="detail-section" aria-label="基本">
          <h3 class="detail-heading">基本</h3>
          <dl class="detail-list">
            <div class="detail-row"><dt>契約</dt><dd>{{ contract.has_contract ? "契約を伴う" : "契約を伴わない" }}</dd></div>
            <div class="detail-row"><dt>区分</dt><dd>{{ contract.category.name }}</dd></div>
            <div class="detail-row"><dt>ステータス</dt><dd>{{ statusLabel(contract.status) }}</dd></div>
            <div v-if="homepageUrl" class="detail-row">
              <dt>ホームページ</dt>
              <dd><a :href="homepageUrl" target="_blank" rel="noopener noreferrer">{{ contract.homepage }}</a></dd>
            </div>
            <div v-if="contract.memo" class="detail-row"><dt>メモ</dt><dd class="pre">{{ contract.memo }}</dd></div>
          </dl>
        </section>

        <section class="detail-section" aria-label="ログイン">
          <h3 class="detail-heading">ログイン</h3>
          <dl class="detail-list">
            <div class="detail-row"><dt>ログイン方法</dt><dd>{{ loginMethodsLabel(contract.login_methods) }}</dd></div>
            <div v-if="contract.twofa_mail_address" class="detail-row">
              <dt>2段階認証（メール）の送付先</dt><dd>{{ contract.twofa_mail_address }}</dd>
            </div>
            <div v-if="contract.twofa_tel_number" class="detail-row">
              <dt>2段階認証（TEL）の送付先</dt><dd>{{ contract.twofa_tel_number }}</dd>
            </div>
            <div class="detail-row">
              <dt>ユーザ名</dt>
              <dd>
                <template v-if="contract.username">
                  <span class="cell-text">{{ contract.username }}</span>
                  <CopyButton :value="contract.username" label="ユーザ名をコピー" @error="onChildError" />
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
            <div class="detail-row">
              <dt>パスワード</dt>
              <dd>
                <PasswordField v-if="showsPassword" :has-password="contract.has_password" :fetch-password="fetchPassword" @error="onChildError" />
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
            <div class="detail-row">
              <dt>登録メールアドレス</dt>
              <dd>
                <template v-if="contract.registered_email">
                  <span class="cell-text">{{ contract.registered_email }}</span>
                  <CopyButton :value="contract.registered_email" label="登録メールアドレスをコピー" @error="onChildError" />
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
          </dl>
        </section>

        <section v-if="hasFullContract" class="detail-section" aria-label="契約">
          <h3 class="detail-heading">契約</h3>
          <dl class="detail-list">
            <div class="detail-row"><dt>維持費</dt><dd>{{ formatFee(contract.fee_amount, contract.fee_cycle) }}</dd></div>
            <div class="detail-row"><dt>更新日</dt><dd>{{ formatIsoDate(contract.renewal_date) }}</dd></div>
            <div class="detail-row">
              <dt>契約日</dt><dd>{{ formatContractDate(contract.contract_date, contract.contract_date_precision) }}</dd>
            </div>
            <div class="detail-row"><dt>無料期間の終了日</dt><dd>{{ formatIsoDate(contract.trial_end_date) }}</dd></div>
            <div class="detail-row"><dt>契約終了日</dt><dd>{{ formatIsoDate(contract.end_date) }}</dd></div>
            <div class="detail-row"><dt>自動更新</dt><dd>{{ formatAutoRenewal(contract.auto_renewal) }}</dd></div>
            <div class="detail-row"><dt>契約者名義</dt><dd>{{ orDash(contract.holder_name) }}</dd></div>
            <div class="detail-row">
              <dt>会員番号・契約番号</dt>
              <dd>
                <template v-if="contract.member_number">
                  <span class="cell-text">{{ contract.member_number }}</span>
                  <CopyButton :value="contract.member_number" label="会員番号・契約番号をコピー" @error="onChildError" />
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
            <div class="detail-row"><dt>解約の受付期限</dt><dd>{{ formatNoticeDays(contract.cancel_notice_days) }}</dd></div>
            <div class="detail-row"><dt>解約手数料・違約金</dt><dd>{{ orDash(contract.cancellation_fee) }}</dd></div>
            <div class="detail-row"><dt>最低契約期間</dt><dd>{{ formatMinTerm(contract.min_term_months) }}</dd></div>
            <div class="detail-row"><dt>解約方法</dt><dd class="pre">{{ orDash(contract.cancellation_method) }}</dd></div>
          </dl>
        </section>

        <section v-if="hasFullContract" class="detail-section" aria-label="問い合わせ先">
          <h3 class="detail-heading">問い合わせ先</h3>
          <dl class="detail-list">
            <div class="detail-row">
              <dt>電話番号</dt>
              <dd>
                <template v-if="contract.contact_phone">
                  <span class="cell-text">{{ contract.contact_phone }}</span>
                  <CopyButton :value="contract.contact_phone" label="電話番号をコピー" @error="onChildError" />
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
            <div class="detail-row">
              <dt>メールアドレス</dt>
              <dd>
                <template v-if="contract.contact_email">
                  <span class="cell-text">{{ contract.contact_email }}</span>
                  <CopyButton :value="contract.contact_email" label="問い合わせ先のメールアドレスをコピー" @error="onChildError" />
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
            <div class="detail-row"><dt>受付時間</dt><dd>{{ orDash(contract.contact_hours) }}</dd></div>
          </dl>
        </section>

        <section v-if="showsRelated" class="detail-section" aria-label="関連">
          <h3 class="detail-heading">関連</h3>
          <dl class="detail-list">
            <template v-if="hasFullContract">
              <div class="detail-row">
                <dt>依存契約</dt>
                <dd>
                  <template v-if="contract.depends_on.length">
                    <button v-for="r in contract.depends_on" :key="r.id" class="link-button" type="button" @click="emit('open', r.id)">{{ r.name }}</button>
                  </template>
                  <template v-else>{{ EMPTY }}</template>
                </dd>
              </div>
              <div class="detail-row">
                <dt>支払方法</dt>
                <dd>
                  <button v-if="contract.payment_contract" class="link-button" type="button" @click="emit('open', contract.payment_contract.id)">
                    {{ contract.payment_contract.name }}
                  </button>
                  <template v-else>{{ EMPTY }}</template>
                </dd>
              </div>
            </template>
            <div class="detail-row">
              <dt>この契約に依存している契約</dt>
              <dd>
                <template v-if="contract.depended_by.length">
                  <button v-for="r in contract.depended_by" :key="r.id" class="link-button" type="button" @click="emit('open', r.id)">{{ r.name }}</button>
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
            <div class="detail-row">
              <dt>この契約を支払方法としている契約</dt>
              <dd>
                <template v-if="contract.payment_for.length">
                  <button v-for="r in contract.payment_for" :key="r.id" class="link-button" type="button" @click="emit('open', r.id)">{{ r.name }}</button>
                </template>
                <template v-else>{{ EMPTY }}</template>
              </dd>
            </div>
          </dl>
        </section>
      </div>

      <footer class="dialog-actions">
        <button class="btn-secondary btn-icon" type="button" aria-label="削除" title="削除" @click="emit('delete')">
          <Icon name="delete" />
        </button>
        <button class="btn-primary btn-icon" type="button" aria-label="編集" title="編集" @click="emit('edit')">
          <Icon name="edit" />
        </button>
      </footer>
    </div>
  </div>
</template>
