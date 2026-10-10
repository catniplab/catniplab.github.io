#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["bibtexparser>=2.1", "pylatexenc>=2.10", "pyyaml>=6.0"]
# ///
"""Render bib_export/catniplab.bib into _data/publications.json for the lab site.

Replaces the old JabRef export. Usage:
    uv run bib_export/build_publications.py [--bib P] [--labels P] [--roster P] [--out P]
Exits 1 on any validation error and then leaves the output file untouched.
"""
import argparse
import html
import json
import os
import re
import sys
import unicodedata
from urllib.parse import urlparse

import bibtexparser
import yaml
from bibtexparser.middlewares.names import (parse_single_name_into_parts,
                                            split_multiple_persons_names)
from pylatexenc.latex2text import LatexNodes2Text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_BIB = os.path.join(SCRIPT_DIR, "catniplab.bib")
DEFAULT_LABELS = os.path.join(SITE_ROOT, "_data", "publication_labels.yml")
DEFAULT_ROSTER = os.path.join(SITE_ROOT, "_data", "lab_members.json")
DEFAULT_OUT = os.path.join(SITE_ROOT, "_data", "publications.json")

KIND_NAMES = {
    "journal": "Journal article", "conference": "Conference paper",
    "preprint": "Preprint", "manuscript": "Manuscript", "thesis": "Thesis",
    "chapter": "Book chapter", "book": "Book",
    "abstract": "Conference abstract", "patent": "Patent", "other": "Other",
}
PUBTYPES = {"abstract", "patent", "manuscript", "other"}


class BibError(Exception):
    """Invalid input; the message names the entry or the line."""


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


# --- text: LaTeX -> Unicode, HTML-escaped ------------------------------------

_L2T = LatexNodes2Text()
# One level of nested braces is allowed inside the italic argument.
_ARG = r"((?:[^{}]|\{[^{}]*\})*)"
_ITALIC = re.compile(r"\{\\(?:it|em|itshape)\s+" + _ARG + r"\}|\\(?:textit|emph)\{" + _ARG + r"\}")
_BARE_PERCENT = re.compile(r"(?<!\\)%")
# Control characters that pylatexenc passes through untouched;
# they mark italics across the decode and become <i> after HTML escaping.
_I_OPEN, _I_CLOSE = "\x02", "\x03"


def _decode(tex, keep_italics):
    tex = _BARE_PERCENT.sub(r"\\%", tex)  # a bare % would start a LaTeX comment
    if keep_italics:
        tex = _ITALIC.sub(lambda m: _I_OPEN + (m.group(1) or m.group(2) or "") + _I_CLOSE, tex)
    text = unicodedata.normalize("NFC", _L2T.latex_to_text(tex))
    return " ".join(text.split())  # also turns ~ (non-breaking space) into a space


def tex_to_text(tex):
    """Plain Unicode text: accents decoded, braces dropped, whitespace collapsed."""
    return _decode(tex or "", keep_italics=False)


def tex_to_html(tex):
    """HTML-escaped Unicode. The only markup emitted is <i> from \\it, \\textit, \\emph."""
    text = html.escape(_decode(tex or "", keep_italics=True), quote=True)
    return text.replace(_I_OPEN, "<i>").replace(_I_CLOSE, "</i>")


# --- names -------------------------------------------------------------------

def _initials(given):
    """'Jean-Pierre' -> 'J.-P.', 'G.' -> 'G.'"""
    return "-".join(part[0] + "." for part in given.split("-") if part)


def person(raw):
    """One BibTeX name -> dict with decoded parts and 'Family, I. I.' display."""
    parts = parse_single_name_into_parts(raw)
    given = [tex_to_text(p) for p in parts.first]
    von = " ".join(tex_to_text(p) for p in parts.von)
    last = " ".join(tex_to_text(p) for p in parts.last)
    jr = " ".join(tex_to_text(p) for p in parts.jr)
    family = f"{von} {last}".strip()
    display = family
    initials = " ".join(_initials(g) for g in given if g)
    if initials:
        display += ", " + initials
    if jr:
        display += ", " + jr
    return {"family": family, "von": von, "given": " ".join(given), "jr": jr,
            "display": display, "member": False}


def persons(value):
    value = " ".join((value or "").split())
    if not value:
        return []
    try:
        return [person(n) for n in split_multiple_persons_names(value)]
    except Exception as err:  # bibtexparser raises assorted types on malformed lists
        raise BibError(f"cannot parse names {value!r}: {err}") from err


# --- kinds -------------------------------------------------------------------

def kind_of(key, entry_type, f):
    pubtype = f.get("pubtype", "").strip().lower()
    if pubtype:
        if pubtype not in PUBTYPES:
            raise BibError(f"{key}: unknown pubtype {pubtype!r} (allowed: {sorted(PUBTYPES)})")
        return pubtype
    t = entry_type.lower()
    if t == "article":
        return "journal"
    if t in ("inproceedings", "conference"):
        return "conference"
    if t == "unpublished":
        return "preprint" if f.get("eprint") or f.get("url") else "manuscript"
    if t in ("phdthesis", "mastersthesis"):
        return "thesis"
    if t in ("inbook", "incollection"):
        return "chapter"
    if t == "book":
        return "book"
    return "other"


# --- parsing -----------------------------------------------------------------

_ENTRY_HEADER = re.compile(r"^\s*@(?!comment\b|string\b|preamble\b)\w+\s*[{(]", re.I | re.M)
_SAFE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:.+-]*")


def parse_bib(path):
    """Parse the bib; any block bibtexparser could not parse is a hard error."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lib = bibtexparser.parse_string(text)
    if lib.failed_blocks:
        b = lib.failed_blocks[0]
        line = getattr(b, "start_line", None)
        where = f"line {line + 1}" if isinstance(line, int) else "unknown line"
        raise BibError(f"{path}: {len(lib.failed_blocks)} block(s) failed to parse; "
                       f"first at {where}: {type(b).__name__} {getattr(b, 'key', '')}".rstrip())
    expected = len(_ENTRY_HEADER.findall(text))
    if expected != len(lib.entries):
        raise BibError(f"{path}: {expected} entry headers but {len(lib.entries)} parsed entries")
    for e in lib.entries:
        if not _SAFE_KEY.fullmatch(e.key):
            raise BibError(f"{e.key!r}: bib key must match [A-Za-z0-9_:.+-]")
    return lib.entries


def fields_of(entry):
    """Field values keyed by lower-cased name (the bib mixes archivePrefix/archiveprefix)."""
    return {k.lower(): str(v.value) for k, v in entry.fields_dict.items()}


def entry_json(entry):
    f = fields_of(entry)
    key = entry.key
    kind = kind_of(key, entry.entry_type, f)
    return {
        "key": key,
        "kind": kind,
        "kind_name": KIND_NAMES[kind],
        "authors": persons(f.get("author", "")),
        "title": tex_to_text(f.get("title", "")),
        "title_html": tex_to_html(f.get("title", "")),
    }


def build(bib_path, labels_path, roster_path):
    return [entry_json(e) for e in parse_bib(bib_path)]
