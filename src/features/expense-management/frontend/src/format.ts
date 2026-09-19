export function formatAmount(value: string): string {
  const negative = value.startsWith("-");
  const raw = negative ? value.slice(1) : value;
  const [intPart, fracPart] = raw.split(".");
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const formatted = fracPart !== undefined ? `${withCommas}.${fracPart}` : withCommas;
  return negative ? `-${formatted}` : formatted;
}
