export type WeekStart = "sunday" | "monday";

const MONTHS_FULL = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export type DayCell = {
  iso: string;
  inMonth: boolean;
  weekday: number;
};

export function toIso(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseIso(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function monthLabel(year: number, monthIndex: number): string {
  return `${MONTHS_FULL[monthIndex]} ${year}`;
}

export function monthLabelPadded(year: number, monthIndex: number): string {
  return `${MONTHS_SHORT[monthIndex]} ${year}`;
}

export function addMonths(year: number, monthIndex: number, delta: number): { year: number; monthIndex: number } {
  const date = new Date(year, monthIndex + delta, 1);
  return { year: date.getFullYear(), monthIndex: date.getMonth() };
}

export function weekdayHeaders(weekStartsOn: WeekStart): { label: string; kind: "sat" | "sun" | "other" }[] {
  const names =
    weekStartsOn === "sunday"
      ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
      : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return names.map((label) => ({
    label,
    kind: label === "Sat" ? "sat" : label === "Sun" ? "sun" : "other",
  }));
}

export function monthCells(year: number, monthIndex: number, weekStartsOn: WeekStart): DayCell[] {
  const first = new Date(year, monthIndex, 1);
  const last = new Date(year, monthIndex + 1, 0);
  const offset = weekStartsOn === "sunday" ? first.getDay() : (first.getDay() + 6) % 7;
  const start = new Date(year, monthIndex, 1 - offset);
  const lastPos = weekStartsOn === "sunday" ? last.getDay() : (last.getDay() + 6) % 7;
  const trailing = 6 - lastPos;
  const total = offset + last.getDate() + trailing;
  const cells: DayCell[] = [];
  for (let index = 0; index < total; index += 1) {
    const current = new Date(start);
    current.setDate(start.getDate() + index);
    cells.push({
      iso: toIso(current),
      inMonth: current.getMonth() === monthIndex,
      weekday: current.getDay(),
    });
  }
  return cells;
}

export function dateTone(weekday: number, isHoliday: boolean): "danger" | "primary" | "normal" {
  if (isHoliday || weekday === 0) {
    return "danger";
  }
  if (weekday === 6) {
    return "primary";
  }
  return "normal";
}

export function overlapsDay(startDate: string, endDate: string, iso: string): boolean {
  return startDate <= iso && endDate >= iso;
}
