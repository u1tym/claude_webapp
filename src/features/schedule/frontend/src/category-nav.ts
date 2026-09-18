import { ref } from "vue";

export type CategoryNavItem = {
  id: number;
  name: string;
  color: string;
  isDeleted: boolean;
  hidden: boolean;
};

export const categoryNavItems = ref<CategoryNavItem[]>([]);
export const categoryNavShowDeleted = ref(false);
export const categoryNavBusy = ref(false);

type CategoryNavHandlers = {
  toggle: (id: number) => void;
  edit: (id: number, event: Event) => void;
  remove: (id: number) => void;
  add: () => void;
  toggleShowDeleted: () => void;
  openMobile: () => void;
};

let handlers: CategoryNavHandlers | null = null;

export function setCategoryNavHandlers(next: CategoryNavHandlers | null): void {
  handlers = next;
}

export function toggleCategoryNav(id: number): void {
  handlers?.toggle(id);
}

export function editCategoryNav(id: number, event: Event): void {
  handlers?.edit(id, event);
}

export function removeCategoryNav(id: number): void {
  handlers?.remove(id);
}

export function addCategoryNav(): void {
  handlers?.add();
}

export function toggleCategoryNavDeleted(): void {
  handlers?.toggleShowDeleted();
}

export function openCategoryNavMobile(): void {
  handlers?.openMobile();
}
