import { ref } from "vue";

export type MonthLink = {
  year: number;
  monthIndex: number;
  label: string;
  current: boolean;
};

export const monthLinks = ref<MonthLink[]>([]);

type MonthHandler = (year: number, monthIndex: number) => void;

let monthHandler: MonthHandler | null = null;

export function setMonthHandler(handler: MonthHandler | null): void {
  monthHandler = handler;
}

export function selectMonth(year: number, monthIndex: number): void {
  monthHandler?.(year, monthIndex);
}
