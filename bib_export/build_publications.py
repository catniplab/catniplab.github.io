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


# --- dates, links, venue ------------------------------------------------------

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
URL_HOST_LABELS = {"openreview.net": "OpenReview", "neurips.cc": "NeurIPS"}


def year_of(key, f):
    raw = f.get("year", "").strip()
    if raw.isdigit():
        return int(raw)
    warn(f"{key}: year {raw!r} is not a number; shown as n.d.")
    return None


def month_of(f):
    raw = f.get("month", "").strip().lower()
    if raw.isdigit() and 1 <= int(raw) <= 12:
        return int(raw)
    return MONTHS.index(raw[:3]) + 1 if raw[:3] in MONTHS else None


def normalize_doi(doi):
    return re.sub(r"^(doi:\s*|https?://(dx\.)?doi\.org/)", "", doi.strip(), flags=re.I)


def checked_url(key, url):
    """Undo BibTeX escapes and allow only http(s) or site-relative URLs."""
    url = url.strip()
    for esc, ch in (("\\_", "_"), ("\\%", "%"), ("\\&", "&"), ("\\#", "#")):
        url = url.replace(esc, ch)
    if url.startswith("/") and not url.startswith("//"):
        return url
    p = urlparse(url)
    if p.scheme in ("http", "https") and p.netloc:
        return url
    raise BibError(f"{key}: URL must be http(s) or site-relative, got {url!r}")


def url_label(url):
    p = urlparse(url)
    if p.path.lower().endswith((".pdf", "/pdf")):
        return "PDF"
    return URL_HOST_LABELS.get(p.netloc.lower().removeprefix("www."), "Link")


def eprint_link(key, f):
    """(label, url) for the eprint, or None. Never invented from archivePrefix alone."""
    eid = f.get("eprint", "").strip()
    prefix = f.get("archiveprefix", "").strip() or "arXiv"
    if not eid:
        if f.get("archiveprefix"):
            warn(f"{key}: archivePrefix without eprint; no preprint link")
        return None
    if prefix.lower() == "arxiv":
        return ("arXiv", f"https://arxiv.org/abs/{eid}")
    if prefix.lower() == "biorxiv":
        return ("bioRxiv", f"https://www.biorxiv.org/content/10.1101/{eid}")
    raise BibError(f"{key}: unknown archivePrefix {prefix!r}")


def links_of(key, f):
    """Display-ordered links; the first occurrence of a URL wins."""
    raw = []
    if f.get("pdf"):
        raw.append(("PDF", "/publications/" + f["pdf"].strip()))
    ep = eprint_link(key, f)
    if ep:
        raw.append(ep)
    if f.get("doi"):
        raw.append(("DOI", "https://doi.org/" + normalize_doi(f["doi"])))
    for field in ("url", "url2"):
        if f.get(field):
            url = checked_url(key, f[field])
            raw.append((url_label(url), url))
    for field, label in (("code", "Code"), ("data", "Data"), ("youtube", "Video")):
        if f.get(field):
            raw.append((label, f[field]))
    out, seen = [], set()
    for label, url in raw:
        url = checked_url(key, url)
        if url not in seen:
            seen.add(url)
            out.append({"label": label, "url": url})
    return out


def venue_html(kind, entry_type, f):
    """Short venue line for the list (not a citation)."""
    def h(name):
        return tex_to_html(f.get(name, ""))
    number = h("number") or h("issue")
    if kind == "journal":
        vol = h("volume")
        parts = [h("journal"), vol + (f"({number})" if number and vol else number), h("pages")]
    elif kind in ("conference", "abstract"):
        parts = [h("booktitle") or h("howpublished") or h("journal"), h("pages")]
    elif kind == "thesis":
        degree = "Doctoral dissertation" if entry_type.lower() == "phdthesis" else "Master's thesis"
        parts = [html.escape(degree), h("school") or h("publisher")]
    elif kind == "chapter":
        book = h("booktitle")
        parts = ["In " + book if book else ("Chapter " + h("chapter") if h("chapter") else ""),
                 h("publisher")]
    elif kind == "book":
        parts = [h("publisher")]
    elif kind == "patent":
        parts = [h("journal"), h("number")]
    else:
        parts = [h("howpublished") or h("booktitle") or h("journal")]
    return ", ".join(p for p in parts if p)


def entry_json(entry):
    f = fields_of(entry)
    key = entry.key
    kind = kind_of(key, entry.entry_type, f)
    year = year_of(key, f)
    return {
        "key": key,
        "kind": kind,
        "kind_name": KIND_NAMES[kind],
        "year": year,
        "month": month_of(f),
        "year_label": str(year) if year else "n.d.",
        "authors": persons(f.get("author", "")),
        "title": tex_to_text(f.get("title", "")),
        "title_html": tex_to_html(f.get("title", "")),
        "venue_html": venue_html(kind, entry.entry_type, f),
        "note_html": tex_to_html(f.get("note", "")),
        "abstract_html": tex_to_html(f.get("abstract", "")),
        "links": links_of(key, f),
    }


def build(bib_path, labels_path, roster_path):
    return [entry_json(e) for e in parse_bib(bib_path)]
