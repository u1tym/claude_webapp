type HolidaySettingsHandler = () => void;

let handler: HolidaySettingsHandler | null = null;

export function setHolidaySettingsHandler(next: HolidaySettingsHandler | null): void {
  handler = next;
}

export function openHolidaySettings(): void {
  handler?.();
}
