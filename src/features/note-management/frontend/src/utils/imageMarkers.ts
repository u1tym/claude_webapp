import type { Marker } from "../types";

export const MAX_MARKERS = 100;

export function newMarkerId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** 番号マーカーの番号は、使われていない最小の番号（1 から）。 */
export function nextMarkerNumber(markers: Marker[]): number {
  const used = new Set(markers.filter((m) => m.kind === "number" && m.number !== undefined).map((m) => m.number));
  let n = 1;
  while (used.has(n)) {
    n += 1;
  }
  return n;
}

export function markerLabel(marker: Marker): string {
  return marker.kind === "house" ? "家" : String(marker.number ?? "");
}

export function cloneMarkers(markers: Marker[]): Marker[] {
  return markers.map((m) => ({ ...m }));
}
