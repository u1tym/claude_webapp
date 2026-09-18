export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_EXPENSE_MANAGEMENT_URL;
  return `${base.replace(/\/$/, "")}${path}`;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(apiUrl(path), {
    ...init,
    headers,
    credentials: "include",
  });
}

function throwIfAuthFailed(res: Response): void {
  if (res.status === 401) {
    throw new Error("unauth");
  }
  if (res.status === 403) {
    throw new Error("forbidden");
  }
}

export type Settings = {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
};

export type BudgetPeriod = {
  id: number;
  title: string;
  start_date: string;
  end_date: string;
};

export type BudgetItem = {
  id: number;
  budget_period_id: number;
  name: string;
  amount: string;
  display_order: number;
};

export type ExclusionItem = {
  exclusion_kind: string;
};

export type PaymentMethod = {
  id: number;
  name: string;
  closing_day: number;
  closing_day_shift_direction: string | null;
  closing_day_exclusions: ExclusionItem[];
  payment_month_offset: number;
  payment_day: number;
  payment_day_shift_direction: string | null;
  payment_day_exclusions: ExclusionItem[];
  display_order: number;
};

export type Expense = {
  id: number;
  usage_date: string;
  budget_item_id: number;
  purpose: string;
  amount: string;
  payment_method_id: number;
  memo: string | null;
  payment_date: string;
  created_at: string;
};

export type UsageDateReportItem = {
  budget_item_id: number;
  name: string;
  budget_amount: string;
  actual_amount: string;
  difference: string;
};

export type UsageDateReport = {
  budget_period: BudgetPeriod;
  items: UsageDateReportItem[];
};

export type PaymentMonthReportItem = {
  budget_item_id: number;
  name: string;
  actual_amount: string;
};

export async function getSettings(): Promise<Settings> {
  const res = await apiFetch("/settings");
  if (!res.ok) {
    throw new Error("settings");
  }
  return (await res.json()) as Settings;
}

export async function getBudgetPeriods(): Promise<BudgetPeriod[]> {
  const res = await apiFetch("/budget-periods");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("budget-periods");
  }
  return ((await res.json()) as { items: BudgetPeriod[] }).items;
}

export async function createBudgetPeriod(
  title: string,
  startDate: string,
  endDate: string,
): Promise<BudgetPeriod | "invalid"> {
  const res = await apiFetch("/budget-periods", {
    method: "POST",
    body: JSON.stringify({ title, start_date: startDate, end_date: endDate }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as BudgetPeriod;
  }
  if (res.status === 400) {
    return "invalid";
  }
  throw new Error("budget-periods");
}

export async function duplicateBudgetPeriod(
  sourceBudgetPeriodId: number,
  title: string,
  startDate: string,
  endDate: string,
): Promise<(BudgetPeriod & { budget_items: BudgetItem[] }) | "invalid" | "missing"> {
  const res = await apiFetch(`/budget-periods/${sourceBudgetPeriodId}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ title, start_date: startDate, end_date: endDate }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as BudgetPeriod & { budget_items: BudgetItem[] };
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("budget-periods");
}

export async function getBudgetItems(budgetPeriodId: number): Promise<BudgetItem[]> {
  const res = await apiFetch(`/budget-items?budget_period_id=${budgetPeriodId}`);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("budget-items");
  }
  return ((await res.json()) as { items: BudgetItem[] }).items;
}

export async function createBudgetItem(
  budgetPeriodId: number,
  name: string,
  amount: string,
  displayOrder: number,
): Promise<BudgetItem | "invalid"> {
  const res = await apiFetch("/budget-items", {
    method: "POST",
    body: JSON.stringify({
      budget_period_id: budgetPeriodId,
      name,
      amount,
      display_order: displayOrder,
    }),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as BudgetItem;
  }
  if (res.status === 400) {
    return "invalid";
  }
  throw new Error("budget-items");
}

export async function updateBudgetItem(
  budgetItemId: number,
  name: string,
  amount: string,
  displayOrder: number,
): Promise<BudgetItem | "invalid" | "missing"> {
  const res = await apiFetch(`/budget-items/${budgetItemId}`, {
    method: "PATCH",
    body: JSON.stringify({ name, amount, display_order: displayOrder }),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as BudgetItem;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("budget-items");
}

export async function deleteBudgetItem(budgetItemId: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/budget-items/${budgetItemId}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("budget-items");
}

export async function getPaymentMethods(): Promise<PaymentMethod[]> {
  const res = await apiFetch("/payment-methods");
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("payment-methods");
  }
  return ((await res.json()) as { items: PaymentMethod[] }).items;
}

export type PaymentMethodInput = {
  name: string;
  closing_day: number;
  closing_day_shift_direction?: string | null;
  closing_day_exclusions?: ExclusionItem[];
  payment_month_offset?: number | null;
  payment_day?: number | null;
  payment_day_shift_direction?: string | null;
  payment_day_exclusions?: ExclusionItem[];
  display_order: number;
};

export async function createPaymentMethod(
  input: PaymentMethodInput,
): Promise<PaymentMethod | "invalid"> {
  const res = await apiFetch("/payment-methods", {
    method: "POST",
    body: JSON.stringify(input),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as PaymentMethod;
  }
  if (res.status === 400) {
    return "invalid";
  }
  throw new Error("payment-methods");
}

export async function updatePaymentMethod(
  paymentMethodId: number,
  input: PaymentMethodInput,
): Promise<PaymentMethod | "invalid" | "missing"> {
  const res = await apiFetch(`/payment-methods/${paymentMethodId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as PaymentMethod;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("payment-methods");
}

export async function deletePaymentMethod(paymentMethodId: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/payment-methods/${paymentMethodId}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("payment-methods");
}

export async function getEstimatedPaymentDate(
  paymentMethodId: number,
  usageDate: string,
): Promise<string | "missing"> {
  const res = await apiFetch(
    `/payment-methods/${paymentMethodId}/estimated-payment-date?usage_date=${usageDate}`,
  );
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return ((await res.json()) as { payment_date: string }).payment_date;
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("estimated-payment-date");
}

export async function getExpenses(startDate: string, endDate: string): Promise<Expense[]> {
  const res = await apiFetch(`/expenses?start_date=${startDate}&end_date=${endDate}`);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("expenses");
  }
  return ((await res.json()) as { items: Expense[] }).items;
}

export type ExpenseInput = {
  usage_date: string;
  budget_item_id: number;
  purpose: string;
  amount: string;
  payment_method_id: number;
  memo: string | null;
  payment_date: string;
};

export async function createExpense(input: ExpenseInput): Promise<Expense | "invalid"> {
  const res = await apiFetch("/expenses", {
    method: "POST",
    body: JSON.stringify(input),
  });
  throwIfAuthFailed(res);
  if (res.status === 201) {
    return (await res.json()) as Expense;
  }
  if (res.status === 400) {
    return "invalid";
  }
  throw new Error("expenses");
}

export async function updateExpense(
  expenseId: number,
  input: ExpenseInput,
): Promise<Expense | "invalid" | "missing"> {
  const res = await apiFetch(`/expenses/${expenseId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  throwIfAuthFailed(res);
  if (res.status === 200) {
    return (await res.json()) as Expense;
  }
  if (res.status === 400) {
    return "invalid";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("expenses");
}

export async function deleteExpense(expenseId: number): Promise<"ok" | "missing"> {
  const res = await apiFetch(`/expenses/${expenseId}`, { method: "DELETE" });
  throwIfAuthFailed(res);
  if (res.status === 204) {
    return "ok";
  }
  if (res.status === 404) {
    return "missing";
  }
  throw new Error("expenses");
}

export async function getUsageDateReport(budgetPeriodId: number): Promise<UsageDateReport> {
  const res = await apiFetch(`/reports/usage-date?budget_period_id=${budgetPeriodId}`);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("reports");
  }
  return (await res.json()) as UsageDateReport;
}

export async function getPaymentMonthReport(yearMonth: string): Promise<PaymentMonthReportItem[]> {
  const res = await apiFetch(`/reports/payment-month?year_month=${yearMonth}`);
  throwIfAuthFailed(res);
  if (!res.ok) {
    throw new Error("reports");
  }
  return ((await res.json()) as { items: PaymentMonthReportItem[] }).items;
}
