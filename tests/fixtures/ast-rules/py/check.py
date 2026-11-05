"""Executable answer check. argv[1] in {original, migrated}.
rc 0 pass | 10 value mismatch | 11 legacy still called (migrated) / not called (original) | 12 import/runtime error | 13 usage"""
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else ""
if mode not in ("original", "migrated"):
    sys.exit(13)
try:
    import legacy
    from app import a, b, shadow
    got = {"one": a.one(), "two": a.two(), "kw": a.kw(), "multi": a.multi(),
           "nested": a.nested(), "b": b.use(), "shadow": shadow.use(), "msg": a.MSG}
except Exception as exc:  # noqa: BLE001
    print(f"ERROR {type(exc).__name__}: {exc}")
    sys.exit(12)
want = {"one": 2, "two": 12, "kw": 30, "multi": 56, "nested": 6, "b": 111,
        "shadow": -5, "msg": "call old_api(9) here"}
print("got", sorted(got.items()))
print("legacy.CALLS", legacy.CALLS)
if got != want:
    print("MISMATCH", {k: (got[k], want[k]) for k in want if got[k] != want[k]})
    sys.exit(10)
if mode == "migrated" and legacy.CALLS != 0:
    sys.exit(11)
if mode == "original" and legacy.CALLS == 0:
    sys.exit(11)
print("PASS", mode)
