function legacyFormat(v: number): string {
  return "shadow:" + v;
}

export function shadowShow(): string {
  return legacyFormat(7);
}
