export function formatV2(v: number, opts: { unit?: string } = {}): string {
  return `${v}${opts.unit ?? "ms"}`;
}
