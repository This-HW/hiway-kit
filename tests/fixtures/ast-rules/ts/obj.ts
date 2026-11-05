import { legacyFormat } from "./legacy.ts";

export const fmt = { legacyFormat: (v: number): string => "obj:" + v };

export function objShow(): string {
  return fmt.legacyFormat(1) + "|" + legacyFormat(2);
}
