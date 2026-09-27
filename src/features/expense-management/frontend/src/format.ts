/** Sums decimal-string amounts using integer cents (BigInt) to avoid floating-point error. */
export function sumAmounts(values: string[]): string {
  let totalCents = 0n;
  for (const value of values) {
    const negative = value.startsWith("-");
    const raw = negative ? value.slice(1) : value;
    const [intPart, fracPart = ""] = raw.split(".");
    const cents = BigInt(intPart) * 100n + BigInt((fracPart + "00").slice(0, 2));
    totalCents += negative ? -cents : cents;
  }
  const negative = totalCents < 0n;
  const abs = negative ? -totalCents : totalCents;
  const fracPart = (abs % 100n).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${abs / 100n}.${fracPart}`;
}

export function formatAmount(value: string): string {
  const negative = value.startsWith("-");
  const raw = negative ? value.slice(1) : value;
  const [intPart, fracPart] = raw.split(".");
  // Displayed as an integer: round to the nearest yen using BigInt so large
  // amounts are not subject to floating-point rounding error.
  const roundedUp = fracPart !== undefined && fracPart.length > 0 && Number(fracPart[0]) >= 5;
  const digits = roundedUp ? String(BigInt(intPart) + 1n) : intPart;
  const withCommas = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return negative ? `-${withCommas}` : withCommas;
}

/** Converts an API decimal-string amount (e.g. "980.00") to a plain integer string for an editable
 *  amount field (e.g. "980"), rounding to the nearest yen. Amounts are never negative here. */
export function toIntegerAmount(value: string): string {
  const [intPart, fracPart] = value.split(".");
  const roundedUp = fracPart !== undefined && fracPart.length > 0 && Number(fracPart[0]) >= 5;
  return roundedUp ? String(BigInt(intPart) + 1n) : intPart;
}

/** Converts a plain integer string from an amount field back to the API's decimal-string format
 *  (e.g. "980" -> "980.00"). */
export function toApiAmount(value: string): string {
  return `${value}.00`;
}
