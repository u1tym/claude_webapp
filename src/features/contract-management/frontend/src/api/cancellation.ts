import { apiFetch, ensureOk } from "./client";
import type { Plan, PlanCandidate } from "./types";

/** 解約順（解約の対象を解約する順に）と、警告。PDF 出力もこの応答を使う（パスワードなどは含まれない）。 */
export async function getPlan(): Promise<Plan> {
  const res = await ensureOk(await apiFetch("/cancellation-plan"));
  return (await res.json()) as Plan;
}

/** 解約の対象にできて、まだ解約順に入っていない契約。 */
export async function getCandidates(): Promise<PlanCandidate[]> {
  const res = await ensureOk(await apiFetch("/cancellation-plan/candidates"));
  return ((await res.json()) as { items: PlanCandidate[] }).items;
}

/** 解約順を、指定した順に置き換えて保存する。 */
export async function savePlan(contractIds: number[]): Promise<Plan> {
  const res = await ensureOk(
    await apiFetch("/cancellation-plan", { method: "PUT", body: JSON.stringify({ contract_ids: contractIds }) }),
  );
  return (await res.json()) as Plan;
}
