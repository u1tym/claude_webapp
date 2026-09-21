// api-design.md の共通のオブジェクトに対応する型。

export interface Settings {
  login_url: string;
  menu_url: string;
  icon_system: string;
  icon_back: string;
}

export interface Folder {
  id: number;
  parent_id: number | null;
  name: string;
  sort_order: number;
  is_deleted: boolean;
  ancestor_deleted: boolean;
}

export interface FileSummary {
  id: number;
  folder_id: number;
  title: string;
  sort_order: number;
  is_deleted: boolean;
  ancestor_deleted: boolean;
}

export interface ItemsResponse {
  parent: { id: number; name: string; is_deleted: boolean; ancestor_deleted: boolean } | null;
  folders: Folder[];
  files: FileSummary[];
}

export type PartType = "text" | "md" | "tex" | "url" | "action" | "checklist" | "jpeg" | "png" | "binary";

export type MarkerKind = "house" | "number";

export interface Marker {
  id: string;
  kind: MarkerKind;
  x: number;
  y: number;
  text: string;
  number?: number;
}

export interface Revision {
  id: number;
  revision_number: number;
  type: PartType;
  filename: string;
  byte_size: number;
  created_at: string;
}

export interface Part {
  id: number;
  sort_order: number;
  type: PartType;
  is_deleted: boolean;
  data: string;
  byte_size: number;
  filename: string;
  title: string;
  markers: Marker[];
  image_scale: number;
  checklist_id: number | null;
  revisions: Revision[];
}

export interface FileDetail {
  id: number;
  folder: { id: number; name: string };
  title: string;
  is_deleted: boolean;
  ancestor_deleted: boolean;
  parts: Part[];
}

export interface PartCreateBody {
  type: PartType;
  data?: string;
  filename?: string;
  title?: string;
  markers?: Marker[];
  image_scale?: number;
}

export type PartUpdateBody = Partial<PartCreateBody>;

export interface ChecklistItem {
  id: number;
  title: string;
  is_checked: boolean;
}

export interface ChecklistCategory {
  id: number;
  name: string;
  is_unnamed: boolean;
  items: ChecklistItem[];
}

export interface Checklist {
  checklist_id: number;
  title: string;
  categories: ChecklistCategory[];
}

/** 行動予定の本文（type が action のときの data を、JSON として読んだもの）。 */
export interface ActionPoint {
  place: string;
  time?: string;
  arrive?: string;
  depart?: string;
}

export interface ActionLeg {
  memo: string;
  note: string;
}

export interface ActionPlan {
  points: ActionPoint[];
  legs: ActionLeg[];
}

/** 印刷（PDF 出力）用に組み立てた 1 ファイル分 */
export interface PrintFile {
  fileId: number;
  folderName: string;
  title: string;
  parts: Part[];
}
