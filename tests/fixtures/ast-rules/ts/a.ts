import { legacyFormat } from "./legacy.ts";

// legacyFormat(1) in a comment must stay
export const label: string = "legacyFormat(2)";
export const tpl: string = `use legacyFormat(3) carefully`;

export function show(): string[] {
  return [legacyFormat(10), legacyFormat(20, "s")];
}
