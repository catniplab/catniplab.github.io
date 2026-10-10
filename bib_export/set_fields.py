#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["bibtexparser>=2.1", "pylatexenc>=2.10", "pyyaml>=6.0"]
# ///
"""Insert or replace single-line fields in catniplab.bib without reformatting it.

Usage: uv run bib_export/set_fields.py CHANGES.csv [--bib PATH]
CHANGES.csv columns: key,field,value,format  (format: tex = value is TeX already,
text = plain text to escape).

Fields are located with bibtexparser (Entry.start_line, Field.start_line; both
0-based line indices into the file), never by scanning lines, so a field-looking
line inside another field's multi-line value is never touched. The edited text
is built in memory, written to a temporary file next to the bib and parsed with
build_publications.parse_bib; every other field of every entry must be
unchanged and each requested field must hold the requested value. Only then the
temporary file replaces the bib. On any failure the bib is left untouched.
"""
import argparse
import csv
import importlib.util
import os
import shutil
import sys
import tempfile

import bibtexparser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BIB = os.path.join(SCRIPT_DIR, "catniplab.bib")
_SPECIALS = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "%": r"\%",
             "&": r"\&", "#": r"\#", "_": r"\_", "$": r"\$"}


def latex_escape_text(s):
    """Plain text -> TeX-safe text."""
    return "".join(_SPECIALS.get(ch, ch) for ch in s)


def set_field(lines, key, field, value):
    """Set `field` of entry `key` in place in `lines` (list of lines with newlines)."""
    lib = bibtexparser.parse_string("".join(lines))
    hits = [e for e in lib.entries if e.key == key]
    if len(hits) != 1:
        raise SystemExit(f"{key}: no entry with this key" if not hits
                         else f"{key}: {len(hits)} entries share this key")
    entry = hits[0]
    end = entry.start_line + entry.raw.count("\n")  # line holding the closing brace
    new = f"  {field} = {{{value}}},\n"
    fields = entry.fields
    for n, f in enumerate(fields):
        if f.key.lower() != field.lower():
            continue
        if sum(g.start_line == f.start_line for g in fields) > 1 or entry.start_line == f.start_line:
            raise SystemExit(f"{key}: field {field} shares a line; edit it by hand")
        stop = fields[n + 1].start_line if n + 1 < len(fields) else end
        if f.start_line == end:
            raise SystemExit(f"{key}: field {field} shares the closing line; edit it by hand")
        body = [i for i in range(f.start_line, stop) if lines[i].strip()]
        if len(body) != 1:
            raise SystemExit(f"{key}: field {field} spans lines; edit it by hand")
        lines[f.start_line] = new
        return
    if lines[end].strip() != "}" or not fields or fields[-1].start_line == end:
        raise SystemExit(f"{key}: closing brace is not on its own line; edit it by hand")
    j = end - 1
    while not lines[j].strip():
        j -= 1
    if not lines[j].rstrip().endswith(","):
        lines[j] = lines[j].rstrip("\n").rstrip() + ",\n"
    lines.insert(end, new)


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "build_publications", os.path.join(SCRIPT_DIR, "build_publications.py"))
    bp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bp)
    return bp


def _verify(bp, old_path, new_path, wanted):
    """Every field except the requested (key, field) pairs is unchanged; those hold the new values."""
    old = {e.key: bp.fields_of(e) for e in bp.parse_bib(old_path)}
    new = {e.key: bp.fields_of(e) for e in bp.parse_bib(new_path)}
    if old.keys() != new.keys():
        raise ValueError("set of entry keys changed")
    for key, fs in new.items():
        touched = {f for (k, f) in wanted if k == key}
        rest_old = {f: v for f, v in old[key].items() if f not in touched}
        rest_new = {f: v for f, v in fs.items() if f not in touched}
        if rest_old != rest_new:
            raise ValueError(f"{key}: fields other than the requested ones changed")
    for (key, field), value in wanted.items():
        if new[key].get(field) != value:
            raise ValueError(f"{key}.{field}: stored value differs from the requested one")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Set single-line fields in catniplab.bib.")
    ap.add_argument("changes")
    ap.add_argument("--bib", default=DEFAULT_BIB)
    args = ap.parse_args(argv)
    with open(args.bib, encoding="utf-8", newline="") as fh:
        lines = fh.read().splitlines(keepends=True)
    with open(args.changes, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    wanted = {}
    for r in rows:
        value = r["value"] if r.get("format", "tex") == "tex" else latex_escape_text(r["value"])
        value = " ".join(value.split())
        set_field(lines, r["key"], r["field"], value)
        wanted[(r["key"], r["field"].lower())] = value
    bp = _load_generator()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(args.bib)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(lines))
        _verify(bp, args.bib, tmp, wanted)
        shutil.copymode(args.bib, tmp)  # mkstemp creates 0600; keep the bib's own mode
        os.replace(tmp, args.bib)
    except Exception as err:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"error: {err}; bib left untouched", file=sys.stderr)
        return 1
    print(f"set {len(rows)} field(s) in {args.bib}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
