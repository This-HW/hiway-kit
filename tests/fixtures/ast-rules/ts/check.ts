// Executable answer check. argv[2] in {original, migrated}.
// rc 0 pass | 10 value mismatch | 11 legacy usage wrong for mode | 12 import/runtime error | 13 usage
const mode = process.argv[2] ?? "";
if (mode !== "original" && mode !== "migrated") process.exit(13);
let got: Record<string, unknown>;
let counter: { calls: number };
try {
  const legacy = await import("./legacy.ts");
  const a = await import("./a.ts");
  const o = await import("./obj.ts");
  const s = await import("./shadow.ts");
  counter = legacy.counter;
  got = { show: a.show().join(","), label: a.label, tpl: a.tpl, obj: o.objShow(), shadow: s.shadowShow() };
} catch (e) {
  console.log("ERROR", String(e));
  process.exit(12);
}
const want = { show: "10ms,20s", label: "legacyFormat(2)", tpl: "use legacyFormat(3) carefully", obj: "obj:1|2ms", shadow: "shadow:7" };
console.log("got", JSON.stringify(got), "calls", counter.calls);
if (JSON.stringify(got) !== JSON.stringify(want)) { console.log("MISMATCH"); process.exit(10); }
if (mode === "migrated" && counter.calls !== 0) process.exit(11);
if (mode === "original" && counter.calls === 0) process.exit(11);
console.log("PASS", mode);
