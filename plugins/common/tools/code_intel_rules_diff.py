"""Unified diff child for code_intel_rules (stdlib only; run as `python -I -S -B`).

Isolated mode means no sibling imports: this file must stay self-contained.
argv[1] is a JSON manifest written by the parent in its private temp dir:
{"files": [{"path": rel, "before": abs, "after": abs}, ...]}. Lines split on
LF only; CR, form feed and U+2028 stay inside a line. Output is one ASCII JSON
object on stdout: {"diffs": [{"path", "diff"}]} (rc0) or {"error", "path"}
(rc3 for non-UTF-8 input). The parent bounds time and output.
"""
import difflib
import json
import re
import sys

LINE = re.compile(r"[^\n]*\n|[^\n]+\Z")
NO_NEWLINE = "\\ No newline at end of file\n"


def lines(text):
    return LINE.findall(text)


def unified(path, before, after):
    out = []
    for line in difflib.unified_diff(lines(before), lines(after), fromfile="a/" + path, tofile="b/" + path):
        # Only a file's real last line can lack LF after LF-only splitting.
        out.append(line if line.endswith("\n") else line + "\n" + NO_NEWLINE)
    return "".join(out)


def main():
    with open(sys.argv[1], "rb") as handle:
        manifest = json.loads(handle.read().decode("utf-8"))
    diffs = []
    for item in manifest["files"]:
        texts = []
        for key in ("before", "after"):
            with open(item[key], "rb") as handle:
                data = handle.read()
            try:
                texts.append(data.decode("utf-8"))
            except UnicodeDecodeError:
                sys.stdout.write(json.dumps({"error": "not_utf8", "path": item["path"]}))
                return 3
        diffs.append({"path": item["path"], "diff": unified(item["path"], *texts)})
    sys.stdout.write(json.dumps({"diffs": diffs}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
