<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import {
  AuthError,
  applyAllRoutines,
  applyRoutine,
  createCategory,
  createRoutine,
  createSchedule,
  createUserHoliday,
  deleteCategory,
  deleteRoutine,
  deleteSchedule,
  deleteUserHoliday,
  getCategories,
  getHolidays,
  getPreferences,
  getRoutines,
  getSchedules,
  getUserHolidays,
  savePreferences,
  updateCategory,
  updateCompletion,
  updateRoutine,
  updateSchedule,
  type CategoryItem,
  type HolidayItem,
  type Preferences,
  type RoutineItem,
  type RoutinePayload,
  type ScheduleItem,
  type SchedulePayload,
  type UserHolidayItem,
} from "../api";
import {
  addMonths,
  dateTone,
  monthCells,
  monthLabel,
  monthLabelPadded,
  overlapsDay,
  toIso,
  weekdayHeaders,
  type DayCell,
} from "../calendar";
import { setHolidaySettingsHandler } from "../holiday-settings";
import iconEdit from "../assets/icon-edit.png";
import iconLeft from "../assets/icon-left.png";
import iconNew from "../assets/icon-new.png";
import iconRight from "../assets/icon-right.png";
import iconTrash from "../assets/icon-trash.png";
import { monthLinks, setMonthHandler } from "../month-nav";
import {
  categoryNavBusy,
  categoryNavItems,
  categoryNavShowDeleted,
  setCategoryNavHandlers,
} from "../category-nav";

const emit = defineEmits<{ "auth-error": [unknown] }>();

const ITEM_ROW_PX = 17;
const LEFTOVER_ROW_PX = 20;
const LEFTOVER_HIDE_MS = 1000;

const ROUTINE_MONTHS = [
  { n: 1, label: "Jan" },
  { n: 2, label: "Feb" },
  { n: 3, label: "Mar" },
  { n: 4, label: "Apr" },
  { n: 5, label: "May" },
  { n: 6, label: "Jun" },
  { n: 7, label: "Jul" },
  { n: 8, label: "Aug" },
  { n: 9, label: "Sep" },
  { n: 10, label: "Oct" },
  { n: 11, label: "Nov" },
  { n: 12, label: "Dec" },
];
const ROUTINE_WEEKDAYS = [
  { value: "sunday", label: "Sun" },
  { value: "monday", label: "Mon" },
  { value: "tuesday", label: "Tue" },
  { value: "wednesday", label: "Wed" },
  { value: "thursday", label: "Thu" },
  { value: "friday", label: "Fri" },
  { value: "saturday", label: "Sat" },
] as const;
const ROUTINE_EXCLUSIONS = [
  { value: "holiday", label: "Holiday" },
  ...ROUTINE_WEEKDAYS,
];
const ALL_MONTHS = ROUTINE_MONTHS.map((item) => item.n);

const busy = ref(false);
const ready = ref(false);
const error = ref("");
const success = ref("");
const isMobile = ref(false);
const year = ref(new Date().getFullYear());
const monthIndex = ref(new Date().getMonth());
const selectedIso = ref<string | null>(null);
const leftoverIso = ref<string | null>(null);
const leftoverAnchor = ref<HTMLElement | null>(null);
const leftoverPopEl = ref<HTMLElement | null>(null);
const leftoverPopStyle = ref<Record<string, string>>({});
const gridEl = ref<HTMLElement | null>(null);
const visibleByIso = ref<Record<string, number>>({});
const categoryPanel = ref(false);
const settingsPanel = ref(false);
const dayMenu = ref<{ iso: string; x: number; y: number } | null>(null);
const dayMenuEl = ref<HTMLElement | null>(null);
const dayMenuStyle = ref<Record<string, string>>({});

const prefs = ref<Preferences>({
  week_starts_on: "sunday",
  show_deleted: false,
  hidden_category_ids: [],
});
const categories = ref<CategoryItem[]>([]);
const schedules = ref<ScheduleItem[]>([]);
const nationalHolidays = ref<HolidayItem[]>([]);
const userHolidays = ref<UserHolidayItem[]>([]);

const scheduleOpen = ref(false);
const categoryOpen = ref(false);
const holidayOpen = ref(false);
const confirmKind = ref<"schedule" | "category" | "routine" | null>(null);
const confirmId = ref<number | null>(null);
const formError = ref("");
const routines = ref<RoutineItem[]>([]);
const selectedRoutineId = ref<number | null>(null);
const routineOpen = ref(false);
const applyOpen = ref(false);
const applyMode = ref<"one" | "all">("one");
const applyYear = ref(new Date().getFullYear());
const applyMonthIndex = ref(new Date().getMonth());
const routineForm = ref({
  id: null as number | null,
  title: "",
  detail: "",
  kind: "event" as "event" | "todo",
  category_id: null as number | null,
  occurrence_type: "date" as "date" | "weekday",
  date_rule: "last_day" as "last_day" | "day_of_month",
  day_of_month: 1,
  weekday_rule: "nth" as "nth" | "nth_from_last",
  weekday_n: 1,
  weekday: "sunday" as (typeof ROUTINE_WEEKDAYS)[number]["value"],
  needs_notification: false,
  adjust_excluded: false,
  shift_direction: "earlier" as "earlier" | "later",
  months: [...ALL_MONTHS],
  exclusions: [] as string[],
});

const scheduleForm = ref({
  id: null as number | null,
  kind: "event" as "event" | "todo",
  granularity: "time" as "day" | "time",
  title: "",
  start_date: "",
  end_date: "",
  start_time: "09:00",
  end_time: "10:00",
  category_id: null as number | null,
  location: "",
  detail: "",
  is_completed: false,
  needs_notification: false,
});
const categoryForm = ref({ id: null as number | null, name: "", color: "#4DA3FF" });
const holidayForm = ref({ holiday_date: "", name: "" });

let successTimer = 0;
let leftoverHideTimer = 0;
let gridObserver: ResizeObserver | null = null;
let media: MediaQueryList | null = null;

function onMedia(): void {
  if (media) {
    isMobile.value = media.matches;
  }
}

function flash(message: string): void {
  error.value = "";
  success.value = message;
  window.clearTimeout(successTimer);
  successTimer = window.setTimeout(() => {
    success.value = "";
  }, 3000);
}

function closeLeftover(): void {
  window.clearTimeout(leftoverHideTimer);
  leftoverIso.value = null;
  leftoverAnchor.value = null;
  leftoverPopStyle.value = {};
}

function cancelCloseLeftover(): void {
  window.clearTimeout(leftoverHideTimer);
}

function scheduleCloseLeftover(): void {
  window.clearTimeout(leftoverHideTimer);
  leftoverHideTimer = window.setTimeout(() => {
    closeLeftover();
  }, LEFTOVER_HIDE_MS);
}

function leftoverPopBox(
  placeAbove: boolean,
  maxHeight: number,
  anchorRect: DOMRect,
): Record<string, string> {
  const popLeft = Math.min(
    Math.max(8, anchorRect.right - 240),
    window.innerWidth - 8 - 240,
  );
  if (placeAbove) {
    return {
      top: `${anchorRect.top - 4}px`,
      left: `${popLeft}px`,
      transform: "translateY(-100%)",
      maxHeight: `${maxHeight}px`,
    };
  }
  return {
    top: `${anchorRect.bottom + 4}px`,
    left: `${popLeft}px`,
    transform: "none",
    maxHeight: `${maxHeight}px`,
  };
}

function positionLeftoverPop(measure: boolean): void {
  const anchor = leftoverAnchor.value;
  if (anchor === null) {
    leftoverPopStyle.value = {};
    return;
  }
  const rect = anchor.getBoundingClientRect();
  if (!measure) {
    leftoverPopStyle.value = {
      ...leftoverPopBox(false, 240, rect),
      visibility: "hidden",
    };
    return;
  }
  const spaceBelow = window.innerHeight - rect.bottom - 12;
  const spaceAbove = rect.top - 12;
  const pop = leftoverPopEl.value;
  const contentHeight = pop ? pop.scrollHeight : 240;
  const placeAbove = contentHeight > spaceBelow && spaceAbove > spaceBelow;
  const available = placeAbove ? spaceAbove : spaceBelow;
  leftoverPopStyle.value = leftoverPopBox(placeAbove, Math.max(48, Math.min(240, available)), rect);
}

async function onLeftoverClick(iso: string, event: MouseEvent): Promise<void> {
  event.stopPropagation();
  window.clearTimeout(leftoverHideTimer);
  leftoverIso.value = iso;
  leftoverAnchor.value = event.currentTarget as HTMLElement;
  positionLeftoverPop(false);
  await nextTick();
  positionLeftoverPop(true);
}

function parseHexColor(value: string): [number, number, number] | null {
  const hex = value.trim().replace("#", "");
  if (/^[0-9a-fA-F]{3}$/.test(hex)) {
    return [
      Number.parseInt(hex[0] + hex[0], 16),
      Number.parseInt(hex[1] + hex[1], 16),
      Number.parseInt(hex[2] + hex[2], 16),
    ];
  }
  if (/^[0-9a-fA-F]{6}$/.test(hex)) {
    return [
      Number.parseInt(hex.slice(0, 2), 16),
      Number.parseInt(hex.slice(2, 4), 16),
      Number.parseInt(hex.slice(4, 6), 16),
    ];
  }
  return null;
}

function textOn(background: string): string {
  const rgb = parseHexColor(background);
  if (rgb === null) {
    return "#e8f1ff";
  }
  const [r, g, b] = rgb.map((channel) => {
    const s = channel / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return luminance > 0.45 ? "#070b14" : "#e8f1ff";
}

function handle(errorValue: unknown): boolean {
  if (errorValue instanceof AuthError) {
    emit("auth-error", errorValue);
    return true;
  }
  return false;
}

const cells = computed(() => monthCells(year.value, monthIndex.value, prefs.value.week_starts_on));
const weekRowCount = computed(() => Math.max(1, Math.round(cells.value.length / 7)));
const headers = computed(() => weekdayHeaders(prefs.value.week_starts_on));
const titleText = computed(() => monthLabel(year.value, monthIndex.value));
const applyMonthText = computed(() => monthLabel(applyYear.value, applyMonthIndex.value));
const todayIso = computed(() => toIso(new Date()));
const rangeStart = computed(() => cells.value[0]?.iso ?? "");
const rangeEnd = computed(() => cells.value[cells.value.length - 1]?.iso ?? "");

const listedCategories = computed(() =>
  categories.value.filter((item) => prefs.value.show_deleted || !item.is_deleted),
);
const activeCategories = computed(() => categories.value.filter((item) => !item.is_deleted));

function isHidden(categoryId: number): boolean {
  return prefs.value.hidden_category_ids.includes(categoryId);
}

function isVisibleSchedule(item: ScheduleItem): boolean {
  if (isHidden(item.category_id)) {
    return false;
  }
  const category = categories.value.find((row) => row.id === item.category_id);
  if (category?.is_deleted && !prefs.value.show_deleted) {
    return false;
  }
  return true;
}

function daySchedules(iso: string): ScheduleItem[] {
  return schedules.value.filter((item) => overlapsDay(item.start_date, item.end_date, iso) && isVisibleSchedule(item));
}

function holidayNames(iso: string): string[] {
  const names: string[] = [];
  for (const item of nationalHolidays.value) {
    if (item.date === iso) {
      names.push(item.name);
    }
  }
  for (const item of userHolidays.value) {
    if (item.holiday_date === iso) {
      names.push(item.name);
    }
  }
  return names;
}

function isHoliday(iso: string): boolean {
  return holidayNames(iso).length > 0;
}

function userHolidayOn(iso: string): UserHolidayItem | undefined {
  return userHolidays.value.find((item) => item.holiday_date === iso);
}

function tone(cell: DayCell): "danger" | "primary" | "normal" {
  return dateTone(cell.weekday, isHoliday(cell.iso));
}

function categoryColor(categoryId: number): string {
  return categories.value.find((item) => item.id === categoryId)?.color ?? "#4DA3FF";
}

function itemTone(categoryId: number): { backgroundColor: string; color: string } {
  const backgroundColor = categoryColor(categoryId);
  return { backgroundColor, color: textOn(backgroundColor) };
}

function pcLabel(item: ScheduleItem, iso: string): string {
  if (item.granularity === "time" && item.start_time && item.start_date === iso) {
    return `${item.start_time} ${item.title}`;
  }
  return item.title;
}

function mobileLabel(item: ScheduleItem, iso: string): string {
  if (item.granularity === "time" && item.start_time && item.end_time && item.start_date === iso) {
    return `${item.start_time} ～ ${item.end_time} ${item.title}`;
  }
  return item.title;
}

function dotsFor(iso: string): string[] {
  const seen: number[] = [];
  const colors: string[] = [];
  for (const item of daySchedules(iso)) {
    if (seen.includes(item.category_id)) {
      continue;
    }
    seen.push(item.category_id);
    colors.push(categoryColor(item.category_id));
  }
  return colors;
}

function dayVisibleCount(iso: string): number {
  const total = daySchedules(iso).length;
  const measured = visibleByIso.value[iso];
  if (measured === undefined) {
    return Math.min(3, total);
  }
  return Math.min(measured, total);
}

function dayLeftoverCount(iso: string): number {
  return Math.max(0, daySchedules(iso).length - dayVisibleCount(iso));
}

function updateVisibleCounts(): void {
  const grid = gridEl.value;
  if (grid === null || isMobile.value) {
    visibleByIso.value = {};
    return;
  }
  const nodes = grid.querySelectorAll<HTMLElement>(".cell");
  const dayCells = cells.value;
  if (nodes.length !== dayCells.length) {
    return;
  }
  const sample = grid.querySelector<HTMLElement>(".item-row");
  let rowPx = ITEM_ROW_PX;
  if (sample !== null) {
    const style = window.getComputedStyle(sample);
    rowPx = sample.offsetHeight + Number.parseFloat(style.marginTop);
    if (!Number.isFinite(rowPx) || rowPx <= 0) {
      rowPx = ITEM_ROW_PX;
    }
  }
  const leftoverSample = grid.querySelector<HTMLElement>(".leftover");
  let leftoverPx = LEFTOVER_ROW_PX;
  if (leftoverSample !== null) {
    const style = window.getComputedStyle(leftoverSample);
    leftoverPx = leftoverSample.offsetHeight + Number.parseFloat(style.marginTop);
    if (!Number.isFinite(leftoverPx) || leftoverPx <= 0) {
      leftoverPx = LEFTOVER_ROW_PX;
    }
  }
  const next: Record<string, number> = {};
  for (let index = 0; index < dayCells.length; index += 1) {
    const node = nodes[index];
    const iso = dayCells[index].iso;
    const head = node.querySelector<HTMLElement>(".cell-head");
    const styles = window.getComputedStyle(node);
    const padY = Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom);
    const available = node.clientHeight - padY - (head?.offsetHeight ?? 0);
    const total = daySchedules(iso).length;
    if (total <= 0 || available <= 0) {
      next[iso] = 0;
      continue;
    }
    const withoutLeftover = Math.floor(available / rowPx);
    if (total <= withoutLeftover) {
      next[iso] = total;
    } else {
      next[iso] = Math.max(0, Math.floor((available - leftoverPx) / rowPx));
    }
  }
  if (!visibleCountsEqual(visibleByIso.value, next)) {
    visibleByIso.value = next;
  }
  void tightenIfClipped();
}

async function tightenIfClipped(): Promise<void> {
  await nextTick();
  const grid = gridEl.value;
  if (grid === null || isMobile.value) {
    return;
  }
  const nodes = grid.querySelectorAll<HTMLElement>(".cell");
  const dayCells = cells.value;
  if (nodes.length !== dayCells.length) {
    return;
  }
  const adjusted = { ...visibleByIso.value };
  let changed = false;
  for (let index = 0; index < dayCells.length; index += 1) {
    const itemsEl = nodes[index].querySelector<HTMLElement>(".cell-items");
    const iso = dayCells[index].iso;
    if (itemsEl === null) {
      continue;
    }
    const shown = adjusted[iso] ?? 0;
    if (shown > 0 && itemsEl.scrollHeight > itemsEl.clientHeight + 1) {
      const reduce = Math.max(1, Math.ceil((itemsEl.scrollHeight - itemsEl.clientHeight) / ITEM_ROW_PX));
      adjusted[iso] = Math.max(0, shown - reduce);
      changed = true;
    }
  }
  if (changed && !visibleCountsEqual(visibleByIso.value, adjusted)) {
    visibleByIso.value = adjusted;
  }
}

function visibleCountsEqual(left: Record<string, number>, right: Record<string, number>): boolean {
  const keys = Object.keys(right);
  if (Object.keys(left).length !== keys.length) {
    return false;
  }
  return keys.every((key) => left[key] === right[key]);
}

const leftoverItems = computed(() => {
  if (leftoverIso.value === null) {
    return [];
  }
  return daySchedules(leftoverIso.value).slice(dayVisibleCount(leftoverIso.value));
});

async function loadAll(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    const [nextPrefs, nextCategories] = await Promise.all([getPreferences(), getCategories(true)]);
    prefs.value = nextPrefs;
    categories.value = nextCategories;
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
    ready.value = true;
  }
}

async function loadMonth(): Promise<void> {
  const start = rangeStart.value;
  const end = rangeEnd.value;
  if (start === "" || end === "") {
    return;
  }
  schedules.value = await getSchedules(start, end);
  nationalHolidays.value = await getHolidays(start, end);
  userHolidays.value = await getUserHolidays(start, end);
}

async function persistPrefs(next: Preferences): Promise<void> {
  const saved = await savePreferences(next);
  if (saved === "invalid") {
    error.value = "Invalid input";
    return;
  }
  prefs.value = saved;
}

async function changeWeek(value: string): Promise<void> {
  if (value !== "sunday" && value !== "monday") {
    return;
  }
  if (value === prefs.value.week_starts_on) {
    return;
  }
  busy.value = true;
  try {
    await persistPrefs({ ...prefs.value, week_starts_on: value });
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

async function toggleHiddenCategory(categoryId: number): Promise<void> {
  const current = new Set(prefs.value.hidden_category_ids);
  if (current.has(categoryId)) {
    current.delete(categoryId);
  } else {
    current.add(categoryId);
  }
  busy.value = true;
  try {
    await persistPrefs({ ...prefs.value, hidden_category_ids: [...current] });
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

async function toggleShowDeleted(): Promise<void> {
  busy.value = true;
  try {
    await persistPrefs({ ...prefs.value, show_deleted: !prefs.value.show_deleted });
    categories.value = await getCategories(true);
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

function shiftMonth(delta: number): void {
  const next = addMonths(year.value, monthIndex.value, delta);
  year.value = next.year;
  monthIndex.value = next.monthIndex;
  void reloadMonth();
}

function goToMonth(nextYear: number, nextMonthIndex: number): void {
  year.value = nextYear;
  monthIndex.value = nextMonthIndex;
  void reloadMonth();
}

async function reloadMonth(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

function openPicker(event: Event): void {
  const input = event.currentTarget as HTMLInputElement;
  if (input.disabled) {
    return;
  }
  const picker = input as HTMLInputElement & { showPicker?: () => void };
  if (typeof picker.showPicker === "function") {
    try {
      picker.showPicker();
    } catch {
      return;
    }
  }
}

function openAdd(iso: string): void {
  closeLeftover();
  const first = activeCategories.value[0];
  scheduleForm.value = {
    id: null,
    kind: "event",
    granularity: "time",
    title: "",
    start_date: iso,
    end_date: iso,
    start_time: "09:00",
    end_time: "10:00",
    category_id: first ? first.id : null,
    location: "",
    detail: "",
    is_completed: false,
    needs_notification: false,
  };
  formError.value = "";
  scheduleOpen.value = true;
}

function openEdit(item: ScheduleItem): void {
  closeLeftover();
  scheduleForm.value = {
    id: item.id,
    kind: item.kind,
    granularity: item.granularity,
    title: item.title,
    start_date: item.start_date,
    end_date: item.end_date,
    start_time: item.start_time ?? "09:00",
    end_time: item.end_time ?? "10:00",
    category_id: activeCategories.value.some((row) => row.id === item.category_id)
      ? item.category_id
      : null,
    location: item.location ?? "",
    detail: item.detail ?? "",
    is_completed: item.is_completed === true,
    needs_notification: item.needs_notification,
  };
  formError.value = "";
  scheduleOpen.value = true;
}

function onCellClick(iso: string): void {
  closeLeftover();
  closeDayMenu();
  if (isMobile.value) {
    selectedIso.value = iso;
    return;
  }
  openAdd(iso);
}

function openFab(): void {
  openAdd(selectedIso.value ?? toIso(new Date()));
}

function rangeValid(): boolean {
  const form = scheduleForm.value;
  if (form.end_date < form.start_date) {
    return false;
  }
  if (form.end_date > form.start_date || form.granularity === "day") {
    return true;
  }
  return form.end_time >= form.start_time;
}

function payload(): SchedulePayload | null {
  const form = scheduleForm.value;
  if (form.title.trim() === "") {
    return null;
  }
  if (form.category_id === null) {
    formError.value = "Add a category first";
    return null;
  }
  if (!rangeValid()) {
    return null;
  }
  const body: SchedulePayload = {
    title: form.title.trim(),
    kind: form.kind,
    granularity: form.granularity,
    start_date: form.start_date,
    end_date: form.end_date,
    category_id: form.category_id,
    needs_notification: form.needs_notification,
  };
  if (form.location.trim() !== "") {
    body.location = form.location.trim();
  }
  if (form.detail.trim() !== "") {
    body.detail = form.detail.trim();
  }
  if (form.granularity === "time") {
    body.start_time = form.start_time.slice(0, 5);
    body.end_time = form.end_time.slice(0, 5);
  }
  return body;
}

async function saveSchedule(): Promise<void> {
  const body = payload();
  if (body === null) {
    return;
  }
  busy.value = true;
  formError.value = "";
  try {
    const form = scheduleForm.value;
    const result =
      form.id === null ? await createSchedule(body) : await updateSchedule(form.id, body);
    if (result === "invalid") {
      formError.value = "Invalid input";
      return;
    }
    if (result === "missing") {
      formError.value = "Not found";
      return;
    }
    if (form.id !== null && form.kind === "todo" && result.is_completed !== form.is_completed) {
      const completion = await updateCompletion(form.id, form.is_completed);
      if (completion === "missing" || completion === "conflict") {
        formError.value = "Could not save";
        return;
      }
    }
    scheduleOpen.value = false;
    flash("Saved");
    await loadMonth();
    categories.value = await getCategories(true);
  } catch (caught) {
    if (!handle(caught)) {
      formError.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

async function toggleTodo(item: ScheduleItem, event: Event): Promise<void> {
  event.stopPropagation();
  if (item.kind !== "todo") {
    return;
  }
  busy.value = true;
  try {
    const result = await updateCompletion(item.id, item.is_completed !== true);
    if (result === "missing" || result === "conflict") {
      error.value = "Could not save";
      return;
    }
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

function askDelete(kind: "schedule" | "category" | "routine", id: number): void {
  confirmKind.value = kind;
  confirmId.value = id;
}

async function confirmDelete(): Promise<void> {
  if (confirmKind.value === null || confirmId.value === null) {
    return;
  }
  busy.value = true;
  try {
    if (confirmKind.value === "schedule") {
      const result = await deleteSchedule(confirmId.value);
      if (result === "missing") {
        error.value = "Not found";
      } else {
        scheduleOpen.value = false;
        flash("Deleted");
        await loadMonth();
      }
    } else if (confirmKind.value === "category") {
      const result = await deleteCategory(confirmId.value);
      if (result === "missing") {
        error.value = "Not found";
      } else {
        flash("Deleted");
        categories.value = await getCategories(true);
        await loadMonth();
      }
    } else if (confirmKind.value === "routine") {
      const result = await deleteRoutine(confirmId.value);
      if (result === "missing") {
        error.value = "Not found";
      } else {
        flash("Deleted");
      }
      await loadRoutines();
    }
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    confirmKind.value = null;
    confirmId.value = null;
    busy.value = false;
  }
}

async function loadRoutines(): Promise<void> {
  routines.value = await getRoutines();
  if (
    selectedRoutineId.value !== null &&
    !routines.value.some((item) => item.id === selectedRoutineId.value)
  ) {
    selectedRoutineId.value = null;
  }
}

async function openSettings(): Promise<void> {
  closeLeftover();
  closeDayMenu();
  selectedRoutineId.value = null;
  settingsPanel.value = true;
  try {
    await loadRoutines();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  }
}

function shiftApplyMonth(delta: number): void {
  const next = addMonths(applyYear.value, applyMonthIndex.value, delta);
  applyYear.value = next.year;
  applyMonthIndex.value = next.monthIndex;
}

function emptyRoutineForm(): typeof routineForm.value {
  const first = activeCategories.value[0];
  return {
    id: null,
    title: "",
    detail: "",
    kind: "event",
    category_id: first ? first.id : null,
    occurrence_type: "date",
    date_rule: "last_day",
    day_of_month: 1,
    weekday_rule: "nth",
    weekday_n: 1,
    weekday: "sunday",
    needs_notification: false,
    adjust_excluded: false,
    shift_direction: "earlier",
    months: [...ALL_MONTHS],
    exclusions: [],
  };
}

function openRoutineAdd(): void {
  routineForm.value = emptyRoutineForm();
  formError.value = "";
  routineOpen.value = true;
}

function openRoutineEdit(item: RoutineItem, event: Event): void {
  event.stopPropagation();
  const categoryOk = activeCategories.value.some((row) => row.id === item.category_id);
  routineForm.value = {
    id: item.id,
    title: item.title,
    detail: item.detail ?? "",
    kind: item.kind,
    category_id: categoryOk ? item.category_id : null,
    occurrence_type: item.occurrence_type,
    date_rule: item.date_rule ?? "last_day",
    day_of_month: item.day_of_month ?? 1,
    weekday_rule: item.weekday_rule ?? "nth",
    weekday_n: item.weekday_n ?? 1,
    weekday: item.weekday ?? "sunday",
    needs_notification: item.needs_notification,
    adjust_excluded: item.adjust_excluded,
    shift_direction: item.shift_direction ?? "earlier",
    months: [...item.months],
    exclusions: [...item.exclusions],
  };
  formError.value = "";
  routineOpen.value = true;
}

function openApplyDialog(mode: "one" | "all"): void {
  if (mode === "one" && selectedRoutineId.value === null) {
    return;
  }
  applyMode.value = mode;
  applyYear.value = year.value;
  applyMonthIndex.value = monthIndex.value;
  applyOpen.value = true;
}

function toggleRoutineMonth(month: number): void {
  const current = routineForm.value.months;
  routineForm.value.months = current.includes(month)
    ? current.filter((item) => item !== month)
    : [...current, month].sort((left, right) => left - right);
}

function toggleRoutineExclusion(value: string): void {
  const current = routineForm.value.exclusions;
  routineForm.value.exclusions = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
}

function routinePayload(): RoutinePayload | null {
  const form = routineForm.value;
  if (form.title.trim() === "") {
    return null;
  }
  if (form.category_id === null) {
    formError.value = "Add a category first";
    return null;
  }
  if (form.months.length === 0) {
    return null;
  }
  const body: RoutinePayload = {
    title: form.title.trim(),
    kind: form.kind,
    category_id: form.category_id,
    occurrence_type: form.occurrence_type,
    adjust_excluded: form.adjust_excluded,
    needs_notification: form.needs_notification,
    months: [...form.months].sort((left, right) => left - right),
    exclusions: [],
  };
  if (form.detail.trim() !== "") {
    body.detail = form.detail.trim();
  }
  if (form.occurrence_type === "date") {
    body.date_rule = form.date_rule;
    if (form.date_rule === "day_of_month") {
      if (!Number.isInteger(form.day_of_month) || form.day_of_month < 1 || form.day_of_month > 31) {
        return null;
      }
      body.day_of_month = form.day_of_month;
    }
  } else {
    if (!Number.isInteger(form.weekday_n) || form.weekday_n < 1 || form.weekday_n > 5) {
      return null;
    }
    body.weekday_rule = form.weekday_rule;
    body.weekday_n = form.weekday_n;
    body.weekday = form.weekday;
  }
  if (form.adjust_excluded) {
    if (form.exclusions.length === 0) {
      return null;
    }
    body.exclusions = [...form.exclusions];
    body.shift_direction = form.shift_direction;
  }
  return body;
}

async function saveRoutine(): Promise<void> {
  const body = routinePayload();
  if (body === null) {
    return;
  }
  busy.value = true;
  formError.value = "";
  try {
    const form = routineForm.value;
    const result =
      form.id === null ? await createRoutine(body) : await updateRoutine(form.id, body);
    if (result === "invalid") {
      formError.value = "Invalid input";
      return;
    }
    if (result === "missing") {
      formError.value = "Not found";
      return;
    }
    routineOpen.value = false;
    flash("Saved");
    await loadRoutines();
  } catch (caught) {
    if (!handle(caught)) {
      formError.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

async function confirmApply(): Promise<void> {
  if (applyMode.value === "one") {
    await applySelectedRoutine();
  } else {
    await applyEveryRoutine();
  }
}

async function applySelectedRoutine(): Promise<void> {
  if (selectedRoutineId.value === null) {
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const result = await applyRoutine(
      selectedRoutineId.value,
      applyYear.value,
      applyMonthIndex.value + 1,
    );
    if (result === "invalid") {
      error.value = "Invalid input";
      return;
    }
    if (result === "missing") {
      error.value = "Not found";
      applyOpen.value = false;
      await loadRoutines();
      return;
    }
    applyOpen.value = false;
    flash("Saved");
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

async function applyEveryRoutine(): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    const result = await applyAllRoutines(applyYear.value, applyMonthIndex.value + 1);
    if (result === "invalid") {
      error.value = "Invalid input";
      return;
    }
    applyOpen.value = false;
    flash("Saved");
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

function openCategoryAdd(): void {
  categoryForm.value = { id: null, name: "", color: "#4DA3FF" };
  formError.value = "";
  categoryOpen.value = true;
}

function openCategoryEdit(item: CategoryItem, event: Event): void {
  event.stopPropagation();
  categoryForm.value = { id: item.id, name: item.name, color: item.color };
  formError.value = "";
  categoryOpen.value = true;
}

function openCategoryEditById(id: number, event: Event): void {
  const item = categories.value.find((row) => row.id === id);
  if (!item || item.is_deleted) {
    return;
  }
  openCategoryEdit(item, event);
}

async function saveCategory(): Promise<void> {
  const name = categoryForm.value.name.trim();
  if (name === "") {
    return;
  }
  busy.value = true;
  formError.value = "";
  try {
    const result =
      categoryForm.value.id === null
        ? await createCategory(name, categoryForm.value.color)
        : await updateCategory(categoryForm.value.id, name, categoryForm.value.color);
    if (result === "invalid") {
      formError.value = "Invalid input";
      return;
    }
    if (result === "conflict") {
      formError.value = "Could not save";
      return;
    }
    if (result === "missing") {
      formError.value = "Not found";
      return;
    }
    categoryOpen.value = false;
    flash("Saved");
    categories.value = await getCategories(true);
  } catch (caught) {
    if (!handle(caught)) {
      formError.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

function closeDayMenu(): void {
  dayMenu.value = null;
  dayMenuStyle.value = {};
}

function placeDayMenu(x: number, y: number): void {
  const menu = dayMenuEl.value;
  const width = menu?.offsetWidth ?? 180;
  const height = menu?.offsetHeight ?? 44;
  const left = Math.min(x, window.innerWidth - width - 8);
  const top = Math.min(y, window.innerHeight - height - 8);
  dayMenuStyle.value = {
    left: `${Math.max(8, left)}px`,
    top: `${Math.max(8, top)}px`,
  };
}

function onCellContextMenu(iso: string, event: MouseEvent): void {
  event.preventDefault();
  event.stopPropagation();
  closeLeftover();
  dayMenu.value = { iso, x: event.clientX, y: event.clientY };
  void nextTick(() => {
    placeDayMenu(event.clientX, event.clientY);
  });
}

function onWindowCloseDayMenu(event: Event): void {
  if (dayMenu.value === null) {
    return;
  }
  const target = event.target;
  if (target instanceof Node && dayMenuEl.value?.contains(target)) {
    return;
  }
  const onCell = target instanceof Element && target.closest(".cell") !== null;
  closeDayMenu();
  if (event.type === "contextmenu" && onCell) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
}

function onWindowKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    closeDayMenu();
  }
}

function openHolidayAdd(): void {
  const iso = dayMenu.value?.iso;
  closeDayMenu();
  if (iso === undefined) {
    return;
  }
  holidayForm.value = { holiday_date: iso, name: "" };
  formError.value = "";
  holidayOpen.value = true;
}

async function removeHoliday(): Promise<void> {
  const iso = dayMenu.value?.iso;
  closeDayMenu();
  if (iso === undefined) {
    return;
  }
  const item = userHolidayOn(iso);
  if (item === undefined) {
    return;
  }
  busy.value = true;
  try {
    const result = await deleteUserHoliday(item.id);
    if (result === "missing") {
      error.value = "Not found";
      return;
    }
    flash("Deleted");
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      error.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

async function saveHoliday(): Promise<void> {
  const name = holidayForm.value.name.trim();
  if (name === "" || holidayForm.value.holiday_date === "") {
    return;
  }
  busy.value = true;
  formError.value = "";
  try {
    const result = await createUserHoliday(holidayForm.value.holiday_date, name);
    if (result === "invalid") {
      formError.value = "Invalid input";
      return;
    }
    if (result === "conflict") {
      formError.value = "Could not save";
      return;
    }
    holidayOpen.value = false;
    flash("Saved");
    await loadMonth();
  } catch (caught) {
    if (!handle(caught)) {
      formError.value = "Server error";
    }
  } finally {
    busy.value = false;
  }
}

const selectedDetail = computed(() => {
  if (selectedIso.value === null) {
    return [];
  }
  return daySchedules(selectedIso.value);
});

const selectedTone = computed(() => {
  if (selectedIso.value === null) {
    return "normal" as const;
  }
  const weekday = parseInt(selectedIso.value.slice(8), 10);
  const date = new Date(
    Number(selectedIso.value.slice(0, 4)),
    Number(selectedIso.value.slice(5, 7)) - 1,
    weekday,
  );
  return dateTone(date.getDay(), isHoliday(selectedIso.value));
});

function syncMonthLinks(): void {
  monthLinks.value = [-2, -1, 0, 1, 2].map((delta) => {
    const next = addMonths(year.value, monthIndex.value, delta);
    return {
      year: next.year,
      monthIndex: next.monthIndex,
      label: monthLabelPadded(next.year, next.monthIndex),
      current: delta === 0,
    };
  });
}

function syncCategoryNav(): void {
  categoryNavShowDeleted.value = prefs.value.show_deleted;
  categoryNavBusy.value = busy.value;
  categoryNavItems.value = listedCategories.value.map((item) => ({
    id: item.id,
    name: item.name,
    color: item.color,
    isDeleted: item.is_deleted,
    hidden: isHidden(item.id),
  }));
}

watch([year, monthIndex], syncMonthLinks, { immediate: true });
watch([listedCategories, prefs, busy], syncCategoryNav, { immediate: true });
watch(gridEl, (el) => {
  gridObserver?.disconnect();
  gridObserver = null;
  if (el === null) {
    return;
  }
  gridObserver = new ResizeObserver(() => {
    updateVisibleCounts();
  });
  gridObserver.observe(el);
  updateVisibleCounts();
});
watch([cells, schedules, isMobile], async () => {
  await nextTick();
  updateVisibleCounts();
});

onMounted(async () => {
  media = window.matchMedia("(max-width: 767px)");
  onMedia();
  media.addEventListener("change", onMedia);
  setMonthHandler(goToMonth);
  setCategoryNavHandlers({
    toggle: (id) => {
      void toggleHiddenCategory(id);
    },
    edit: openCategoryEditById,
    remove: (id) => {
      askDelete("category", id);
    },
    add: openCategoryAdd,
    toggleShowDeleted: () => {
      void toggleShowDeleted();
    },
    openMobile: () => {
      closeLeftover();
      categoryPanel.value = true;
    },
  });
  setHolidaySettingsHandler(() => {
    void openSettings();
  });
  window.addEventListener("click", onWindowCloseDayMenu, true);
  window.addEventListener("contextmenu", onWindowCloseDayMenu, true);
  window.addEventListener("keydown", onWindowKeydown);
  await loadAll();
});

onUnmounted(() => {
  setMonthHandler(null);
  setCategoryNavHandlers(null);
  setHolidaySettingsHandler(null);
  monthLinks.value = [];
  categoryNavItems.value = [];
  media?.removeEventListener("change", onMedia);
  window.removeEventListener("click", onWindowCloseDayMenu, true);
  window.removeEventListener("contextmenu", onWindowCloseDayMenu, true);
  window.removeEventListener("keydown", onWindowKeydown);
  gridObserver?.disconnect();
  window.clearTimeout(successTimer);
  window.clearTimeout(leftoverHideTimer);
});
</script>

<template>
  <div class="page">
    <div v-if="!ready" class="loading">Loading…</div>
    <template v-else>
      <div class="toolbar">
        <button class="btn-text btn-icon" type="button" aria-label="Prev" :disabled="busy" @click="shiftMonth(-1)">
          <img class="month-nav-icon" :src="iconLeft" alt="" />
        </button>
        <h2 class="month-title">{{ titleText }}</h2>
        <button class="btn-text btn-icon" type="button" aria-label="Next" :disabled="busy" @click="shiftMonth(1)">
          <img class="month-nav-icon" :src="iconRight" alt="" />
        </button>
      </div>
      <div class="body">
        <section class="calendar-wrap">
          <div v-if="isMobile" class="month-bar">
            <button
              v-for="item in monthLinks"
              :key="`${item.year}-${item.monthIndex}`"
              class="month-bar-item"
              :class="{ 'is-current': item.current }"
              type="button"
              @click="goToMonth(item.year, item.monthIndex)"
            >
              {{ item.label }}
            </button>
          </div>
          <div ref="gridEl" class="grid" :style="{ '--week-rows': String(weekRowCount) }">
            <div
              v-for="head in headers"
              :key="head.label"
              class="weekday"
              :class="{ 'tone-primary': head.kind === 'sat', 'tone-danger': head.kind === 'sun' }"
            >
              {{ head.label }}
            </div>
            <div
              v-for="cell in cells"
              :key="cell.iso"
              class="cell"
              :class="{
                'out-month': !cell.inMonth,
                selected: selectedIso === cell.iso,
                'is-today': cell.iso === todayIso,
              }"
              @click="onCellClick(cell.iso)"
              @contextmenu="onCellContextMenu(cell.iso, $event)"
            >
              <div class="cell-head">
                <div class="cell-date" :class="`tone-${tone(cell)}`">
                  {{ Number(cell.iso.slice(8)) }}
                </div>
                <div v-if="holidayNames(cell.iso).length" class="holiday-names">
                  {{ holidayNames(cell.iso).join(" ") }}
                </div>
              </div>
              <template v-if="!isMobile">
                <div class="cell-items">
                  <button
                    v-for="item in daySchedules(cell.iso).slice(0, dayVisibleCount(cell.iso))"
                    :key="item.id"
                    class="item-row"
                    type="button"
                    :style="itemTone(item.category_id)"
                    :class="{ done: item.kind === 'todo' && item.is_completed }"
                    @click.stop="openEdit(item)"
                  >
                    <input
                      v-if="item.kind === 'todo'"
                      type="checkbox"
                      :checked="item.is_completed === true"
                      :disabled="busy"
                      @click="toggleTodo(item, $event)"
                    />
                    <span>{{ pcLabel(item, cell.iso) }}</span>
                  </button>
                </div>
                <button
                  v-if="dayLeftoverCount(cell.iso) > 0"
                  class="leftover caption"
                  type="button"
                  @click.stop="onLeftoverClick(cell.iso, $event)"
                  @mouseenter="cancelCloseLeftover"
                  @mouseleave="scheduleCloseLeftover"
                >
                  ＋{{ dayLeftoverCount(cell.iso) }}
                </button>
              </template>
              <div v-else class="dots">
                <span v-for="(color, index) in dotsFor(cell.iso)" :key="index" class="dot" :style="{ background: color }"></span>
              </div>
            </div>
          </div>
          <div class="status-line">
            <p v-if="error" class="msg-error">{{ error }}</p>
            <p v-else-if="success" class="msg-success">{{ success }}</p>
          </div>
          <div v-if="isMobile && selectedIso" class="detail">
            <h3 :class="`tone-${selectedTone}`">
              {{ selectedIso }}
              <span v-if="holidayNames(selectedIso).length" class="caption">
                {{ holidayNames(selectedIso).join(" ") }}
              </span>
            </h3>
            <div class="detail-list">
              <p v-if="selectedDetail.length === 0" class="caption">No data</p>
              <button
                v-for="item in selectedDetail"
                :key="item.id"
                class="item-row"
                type="button"
                :style="itemTone(item.category_id)"
                :class="{ done: item.kind === 'todo' && item.is_completed }"
                @click="openEdit(item)"
              >
                <span>{{ item.kind === "todo" ? "TODO " : "" }}{{ mobileLabel(item, selectedIso) }}</span>
              </button>
            </div>
          </div>
        </section>
      </div>
      <button v-if="isMobile" class="fab btn-primary" type="button" :disabled="busy" @click="openFab">＋</button>
    </template>

    <Teleport to="body">
      <div
        v-if="dayMenu"
        ref="dayMenuEl"
        class="day-menu"
        :style="dayMenuStyle"
        role="menu"
        @contextmenu.prevent
      >
        <button
          v-if="userHolidayOn(dayMenu.iso) === undefined"
          class="day-menu-item"
          type="button"
          :disabled="busy"
          role="menuitem"
          @click.stop="openHolidayAdd"
        >
          Add as holiday
        </button>
        <button
          v-else
          class="day-menu-item"
          type="button"
          :disabled="busy"
          role="menuitem"
          @click.stop="removeHoliday"
        >
          Remove holiday
        </button>
      </div>
    </Teleport>
    <Teleport to="body">
      <div
        v-if="leftoverIso && leftoverItems.length"
        ref="leftoverPopEl"
        class="leftover-pop"
        :style="leftoverPopStyle"
        @mouseenter="cancelCloseLeftover"
        @mouseleave="scheduleCloseLeftover"
        @contextmenu.prevent
      >
        <button
          v-for="item in leftoverItems"
          :key="item.id"
          class="item-row"
          type="button"
          :style="itemTone(item.category_id)"
          :class="{ done: item.kind === 'todo' && item.is_completed }"
          @click.stop="openEdit(item)"
        >
          <input
            v-if="item.kind === 'todo'"
            type="checkbox"
            :checked="item.is_completed === true"
            :disabled="busy"
            @click="toggleTodo(item, $event)"
          />
          <span>{{ leftoverIso ? pcLabel(item, leftoverIso) : item.title }}</span>
        </button>
      </div>
    </Teleport>

    <div v-if="categoryPanel" class="overlay">
      <div class="modal">
        <h2>Categories</h2>
        <p v-if="listedCategories.length === 0" class="caption">No data</p>
        <ul class="plain-list">
          <li
            v-for="item in listedCategories"
            :key="item.id"
            class="cat-row"
            :class="{ muted: isHidden(item.id) }"
            @click="toggleHiddenCategory(item.id)"
          >
            <span class="swatch" :style="{ background: item.color }"></span>
            <span>{{ item.name }}{{ item.is_deleted ? " (deleted)" : "" }}</span>
            <span v-if="!item.is_deleted" class="row-actions">
              <button
                class="btn-text btn-icon-sm"
                type="button"
                aria-label="Edit"
                @click="openCategoryEdit(item, $event)"
              >
                <img class="row-icon" :src="iconEdit" alt="" />
              </button>
              <button
                class="btn-text btn-icon-sm"
                type="button"
                aria-label="Delete"
                @click.stop="askDelete('category', item.id)"
              >
                <img class="row-icon" :src="iconTrash" alt="" />
              </button>
            </span>
          </li>
        </ul>
        <button class="btn-text" type="button" :disabled="busy" @click="toggleShowDeleted">
          {{ prefs.show_deleted ? "Hide deleted" : "Show deleted" }}
        </button>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="openCategoryAdd">New</button>
          <button class="btn-secondary" type="button" @click="categoryPanel = false">Close</button>
        </div>
      </div>
    </div>

    <div v-if="settingsPanel" class="overlay">
      <div class="modal settings-modal">
        <h2>Settings</h2>
        <div class="settings-week">
          <p class="caption">Week starts</p>
          <div class="settings-week-btns">
            <button
              class="btn-secondary"
              :class="{ 'is-week-current': prefs.week_starts_on === 'sunday' }"
              type="button"
              :disabled="busy"
              @click="changeWeek('sunday')"
            >
              Starts Sunday
            </button>
            <button
              class="btn-secondary"
              :class="{ 'is-week-current': prefs.week_starts_on === 'monday' }"
              type="button"
              :disabled="busy"
              @click="changeWeek('monday')"
            >
              Starts Monday
            </button>
          </div>
        </div>
        <div class="settings-routines">
          <div class="section-head">
            <h3>Routines</h3>
            <button class="btn-text btn-icon" type="button" aria-label="New" :disabled="busy" @click="openRoutineAdd">
              <img class="header-icon" :src="iconNew" alt="" />
            </button>
          </div>
          <div class="apply-actions">
            <button
              class="btn-primary"
              type="button"
              :disabled="busy || selectedRoutineId === null"
              @click="openApplyDialog('one')"
            >
              Apply
            </button>
            <button class="btn-secondary" type="button" :disabled="busy" @click="openApplyDialog('all')">
              Apply all
            </button>
          </div>
          <p v-if="routines.length === 0" class="caption">No data</p>
          <ul v-else class="plain-list routine-list">
            <li
              v-for="item in routines"
              :key="item.id"
              class="cat-row"
              :class="{ 'is-current': selectedRoutineId === item.id }"
              @click="selectedRoutineId = item.id"
            >
              <span class="row-title">{{ item.title }}</span>
              <span class="row-actions">
                <button
                  class="btn-text btn-icon-sm"
                  type="button"
                  aria-label="Edit"
                  :disabled="busy"
                  @click="openRoutineEdit(item, $event)"
                >
                  <img class="row-icon" :src="iconEdit" alt="" />
                </button>
                <button
                  class="btn-text btn-icon-sm"
                  type="button"
                  aria-label="Delete"
                  :disabled="busy"
                  @click.stop="askDelete('routine', item.id)"
                >
                  <img class="row-icon" :src="iconTrash" alt="" />
                </button>
              </span>
            </li>
          </ul>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" type="button" @click="settingsPanel = false">Close</button>
        </div>
      </div>
    </div>

    <div v-if="scheduleOpen" class="overlay">
      <div class="modal modal-wide">
        <h2>{{ scheduleForm.id === null ? "New" : "Edit" }}</h2>
        <p v-if="formError" class="msg-error">{{ formError }}</p>
        <div class="form-grid">
          <input v-model="scheduleForm.title" class="field" placeholder="Title" :disabled="busy" />
          <label class="check-row">
            <input
              type="checkbox"
              :checked="scheduleForm.granularity === 'day'"
              :disabled="busy"
              @change="scheduleForm.granularity = ($event.target as HTMLInputElement).checked ? 'day' : 'time'"
            />
            All-day
          </label>
          <div class="range-row">
            <div class="range-side">
              <input
                v-model="scheduleForm.start_date"
                class="field field-date"
                type="date"
                :disabled="busy"
                @click="openPicker"
              />
              <input
                v-if="scheduleForm.granularity === 'time'"
                v-model="scheduleForm.start_time"
                class="field field-time"
                type="time"
                :disabled="busy"
              />
            </div>
            <span class="range-sep">～</span>
            <div class="range-side">
              <input
                v-model="scheduleForm.end_date"
                class="field field-date"
                type="date"
                :disabled="busy"
                @click="openPicker"
              />
              <input
                v-if="scheduleForm.granularity === 'time'"
                v-model="scheduleForm.end_time"
                class="field field-time"
                type="time"
                :disabled="busy"
              />
            </div>
          </div>
          <select v-model="scheduleForm.category_id" class="field" :disabled="busy">
            <option :value="null">Category</option>
            <option v-for="item in activeCategories" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
          <select v-model="scheduleForm.kind" class="field" :disabled="busy">
            <option value="event">Event</option>
            <option value="todo">TODO</option>
          </select>
          <label class="check-row">
            <input v-model="scheduleForm.needs_notification" type="checkbox" :disabled="busy" />
            Notify
          </label>
          <input v-model="scheduleForm.location" class="field" placeholder="Location" :disabled="busy" />
          <textarea v-model="scheduleForm.detail" class="field" placeholder="Details" :disabled="busy"></textarea>
          <select
            v-if="scheduleForm.id !== null && scheduleForm.kind === 'todo'"
            v-model="scheduleForm.is_completed"
            class="field"
            :disabled="busy"
          >
            <option :value="false">Open</option>
            <option :value="true">Done</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="saveSchedule">Save</button>
          <button class="btn-secondary" type="button" :disabled="busy" @click="scheduleOpen = false">Cancel</button>
          <button
            v-if="scheduleForm.id !== null"
            class="btn-text"
            type="button"
            :disabled="busy"
            @click="askDelete('schedule', scheduleForm.id)"
          >
            Delete
          </button>
        </div>
      </div>
    </div>

    <div v-if="categoryOpen" class="overlay">
      <div class="modal">
        <h2>{{ categoryForm.id === null ? "New" : "Edit" }}</h2>
        <p v-if="formError" class="msg-error">{{ formError }}</p>
        <div class="form-grid">
          <input v-model="categoryForm.name" class="field" placeholder="Name" :disabled="busy" />
          <input v-model="categoryForm.color" class="field" type="color" :disabled="busy" />
        </div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="saveCategory">Save</button>
          <button class="btn-secondary" type="button" :disabled="busy" @click="categoryOpen = false">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="holidayOpen" class="overlay">
      <div class="modal">
        <h2>Add holiday</h2>
        <p v-if="formError" class="msg-error">{{ formError }}</p>
        <div class="form-grid">
          <p class="caption">{{ holidayForm.holiday_date }}</p>
          <input v-model="holidayForm.name" class="field" placeholder="Name" :disabled="busy" />
        </div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="saveHoliday">Save</button>
          <button class="btn-secondary" type="button" :disabled="busy" @click="holidayOpen = false">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="routineOpen" class="overlay">
      <div class="modal modal-wide">
        <h2>{{ routineForm.id === null ? "New routine" : "Edit routine" }}</h2>
        <p v-if="formError" class="msg-error">{{ formError }}</p>
        <div class="form-grid">
          <input v-model="routineForm.title" class="field" placeholder="Title" :disabled="busy" />
          <select v-model="routineForm.category_id" class="field" :disabled="busy">
            <option :value="null">Category</option>
            <option v-for="item in activeCategories" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
          <select v-model="routineForm.kind" class="field" :disabled="busy">
            <option value="event">Event</option>
            <option value="todo">TODO</option>
          </select>
          <label class="check-row">
            <input v-model="routineForm.needs_notification" type="checkbox" :disabled="busy" />
            Notify
          </label>
          <select v-model="routineForm.occurrence_type" class="field" :disabled="busy">
            <option value="date">By date</option>
            <option value="weekday">By weekday</option>
          </select>
          <template v-if="routineForm.occurrence_type === 'date'">
            <select v-model="routineForm.date_rule" class="field" :disabled="busy">
              <option value="last_day">Last day of month</option>
              <option value="day_of_month">Day of month</option>
            </select>
            <input
              v-if="routineForm.date_rule === 'day_of_month'"
              v-model.number="routineForm.day_of_month"
              class="field"
              type="number"
              min="1"
              max="31"
              :disabled="busy"
            />
          </template>
          <template v-else>
            <select v-model="routineForm.weekday_rule" class="field" :disabled="busy">
              <option value="nth">Nth weekday</option>
              <option value="nth_from_last">Nth from last weekday</option>
            </select>
            <input
              v-model.number="routineForm.weekday_n"
              class="field"
              type="number"
              min="1"
              max="5"
              :disabled="busy"
            />
            <select v-model="routineForm.weekday" class="field" :disabled="busy">
              <option v-for="item in ROUTINE_WEEKDAYS" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </template>
          <div class="check-grid">
            <label v-for="item in ROUTINE_MONTHS" :key="item.n" class="check-row">
              <input
                type="checkbox"
                :checked="routineForm.months.includes(item.n)"
                :disabled="busy"
                @change="toggleRoutineMonth(item.n)"
              />
              {{ item.label }}
            </label>
          </div>
          <label class="check-row">
            <input v-model="routineForm.adjust_excluded" type="checkbox" :disabled="busy" />
            Adjust excluded days
          </label>
          <template v-if="routineForm.adjust_excluded">
            <div class="check-grid">
              <label v-for="item in ROUTINE_EXCLUSIONS" :key="item.value" class="check-row">
                <input
                  type="checkbox"
                  :checked="routineForm.exclusions.includes(item.value)"
                  :disabled="busy"
                  @change="toggleRoutineExclusion(item.value)"
                />
                {{ item.label }}
              </label>
            </div>
            <select v-model="routineForm.shift_direction" class="field" :disabled="busy">
              <option value="earlier">Shift earlier</option>
              <option value="later">Shift later</option>
            </select>
          </template>
          <textarea v-model="routineForm.detail" class="field" placeholder="Details" :disabled="busy"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="saveRoutine">Save</button>
          <button class="btn-secondary" type="button" :disabled="busy" @click="routineOpen = false">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="applyOpen" class="overlay">
      <div class="modal">
        <h2>{{ applyMode === "all" ? "Apply all" : "Apply" }}</h2>
        <div class="apply-month-row">
          <button
            class="btn-text btn-icon"
            type="button"
            aria-label="Prev"
            :disabled="busy"
            @click="shiftApplyMonth(-1)"
          >
            <img class="row-icon" :src="iconLeft" alt="" />
          </button>
          <span class="apply-month-label">{{ applyMonthText }}</span>
          <button
            class="btn-text btn-icon"
            type="button"
            aria-label="Next"
            :disabled="busy"
            @click="shiftApplyMonth(1)"
          >
            <img class="row-icon" :src="iconRight" alt="" />
          </button>
        </div>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="confirmApply">Apply</button>
          <button class="btn-secondary" type="button" :disabled="busy" @click="applyOpen = false">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="confirmKind" class="overlay">
      <div class="modal">
        <h2>Delete</h2>
        <p>Delete this?</p>
        <div class="modal-actions">
          <button class="btn-primary" type="button" :disabled="busy" @click="confirmDelete">Delete</button>
          <button class="btn-secondary" type="button" :disabled="busy" @click="confirmKind = null">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: calc(var(--space) * 3);
  min-height: 0;
  overflow: hidden;
  position: relative;
}

.loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.toolbar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space);
  margin-bottom: calc(var(--space) * 2);
}

.toolbar .btn-icon {
  width: var(--tap);
  min-width: var(--tap);
  padding: 0;
  justify-content: center;
}

.month-title {
  margin: 0;
  font-size: var(--font-size-title);
  letter-spacing: 0.02em;
  font-weight: 500;
  text-align: center;
  min-width: 12ch;
}

.month-nav-icon {
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.month-bar {
  display: none;
}

.body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.calendar-wrap,
.detail,
.plain-list {
  min-height: 0;
}

.calendar-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  grid-template-rows: auto repeat(var(--week-rows, 5), minmax(0, 1fr));
  border: 1px solid var(--color-border);
  min-height: 0;
}

.weekday,
.cell {
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space);
}

.weekday {
  background: var(--color-surface);
  text-align: center;
  font-size: 14px;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.cell {
  position: relative;
  overflow: hidden;
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  min-height: 0;
  user-select: none;
}

.cell.out-month {
  opacity: 0.55;
}

.cell.selected {
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.cell.is-today {
  box-shadow: inset 0 0 0 2px var(--color-primary);
}

.cell.is-today.selected {
  box-shadow: inset 0 0 0 2px var(--color-primary);
}

.cell-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space);
  flex: none;
}

.cell-items {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.cell-date {
  font-weight: 600;
  flex: none;
}

.holiday-names {
  color: var(--color-danger);
  font-size: 12px;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  text-align: left;
  border: 0;
  border-radius: 2px;
  padding: 0 4px;
  min-height: 16px;
  font-size: 12px;
  line-height: 1.2;
  margin-top: 1px;
  overflow: hidden;
  cursor: pointer;
}

.item-row span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-row input {
  flex: none;
  width: 12px;
  height: 12px;
  margin: 0;
}

.item-row.done span {
  text-decoration: line-through;
}

.leftover {
  flex: none;
  align-self: flex-end;
  margin: 2px 0 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  font: inherit;
  color: var(--color-text-muted);
  line-height: 1.2;
}

.leftover-pop {
  position: fixed;
  width: 240px;
  max-height: 240px;
  overflow: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius);
  padding: var(--space);
  color: var(--color-text);
  z-index: 15;
}

.day-menu {
  position: fixed;
  z-index: 18;
  min-width: 180px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space);
}

.day-menu-item {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: var(--tap);
  padding: 0 var(--space);
  border: 0;
  border-radius: var(--radius);
  background: transparent;
  color: var(--color-text);
  text-align: left;
}

.day-menu-item:hover:not(:disabled) {
  color: var(--color-primary);
}

.status-line {
  flex: none;
  height: calc(var(--space) * 3);
  display: flex;
  align-items: center;
  margin-top: var(--space);
  overflow: hidden;
}

.status-line .msg-error,
.status-line .msg-success {
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dots {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: var(--space);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.detail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 36%;
  overflow: hidden;
  margin-top: calc(var(--space) * 2);
  padding-top: var(--space);
  border-top: 1px solid var(--color-border);
}

.detail-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

.fab {
  position: absolute;
  right: calc(var(--space) * 3);
  bottom: calc(var(--space) * 3);
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  padding: 0;
  z-index: 6;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space);
  margin-bottom: var(--space);
}

.section-head h3,
.detail h3 {
  margin: 0;
  flex: none;
}

.modal h3 {
  margin: 0 0 calc(var(--space) * 2);
  font-size: var(--font-size);
  font-weight: 500;
}

.settings-week {
  margin-bottom: calc(var(--space) * 2);
  flex: none;
}

.settings-week .caption {
  margin: 0 0 var(--space);
}

.settings-week-btns {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space);
}

.settings-week-btns .btn-secondary {
  flex: 1;
}

.is-week-current {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.settings-modal {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
}

.settings-modal > h2,
.settings-modal > .modal-actions {
  flex: none;
}

.settings-routines {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.apply-month-row {
  display: flex;
  align-items: center;
  gap: var(--space);
  margin-bottom: var(--space);
}

.apply-month-label {
  flex: 1;
  text-align: center;
}

.apply-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space);
  margin-bottom: var(--space);
}

.routine-list {
  flex: 1;
  min-height: 8rem;
  overflow-x: hidden;
  overflow-y: auto;
}

.row-title {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cat-row.is-current {
  color: var(--color-primary);
}

.check-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space);
}

.plain-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.cat-row {
  display: flex;
  align-items: center;
  gap: var(--space);
  min-height: var(--tap);
  min-width: 0;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
}

.row-actions {
  margin-left: auto;
  display: flex;
}

.row-icon {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.swatch {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  flex: none;
}

.tone-primary {
  color: var(--color-primary);
}

.tone-danger {
  color: var(--color-danger);
}

@media (max-width: 767px) {
  .page {
    padding: var(--space);
    padding-bottom: 0;
  }

  .toolbar {
    margin-bottom: 0;
  }

  .month-bar {
    display: flex;
    flex: none;
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-bottom: 0;
    background: var(--color-surface);
  }

  .month-bar-item {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1 0 auto;
    min-height: 28px;
    padding: 0 var(--space);
    border: 0;
    background: transparent;
    color: var(--color-text-muted);
    font-size: 14px;
  }

  .month-bar-item.is-current {
    color: var(--color-primary);
    box-shadow: inset 0 -3px 0 var(--color-primary);
  }

  .check-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .grid {
    flex: none;
    border-top: 0;
    grid-template-rows: auto repeat(var(--week-rows, 5), minmax(var(--tap), auto));
  }

  .cell {
    min-height: var(--tap);
  }

  .detail {
    flex: 1;
    max-height: none;
    margin-top: calc(var(--space) * 2);
  }

  .detail-list {
    padding-bottom: calc(var(--tap) + var(--space) * 3);
  }

  .fab {
    bottom: calc(var(--space) * 2);
  }
}
</style>
