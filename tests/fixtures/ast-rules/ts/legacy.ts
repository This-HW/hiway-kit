export const counter = { calls: 0 };

export function legacyFormat(v: number, unit: string = "ms"): string {
  counter.calls++;
  return `${v}${unit}`;
}
