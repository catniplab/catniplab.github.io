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
from urllib.parse import unquote, urlparse

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
_BARE_SPECIAL = re.compile(r"(?<!\\)([%&])")
# Control characters that pylatexenc passes through untouched;
# they mark italics across the decode and become <i> after HTML escaping.
_I_OPEN, _I_CLOSE = "\x02", "\x03"


def _decode(tex, keep_italics):
    # A bare % would start a LaTeX comment; a bare & is the alignment character and would be dropped.
    tex = _BARE_SPECIAL.sub(r"\\\1", tex)
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
MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december"]
URL_HOST_LABELS = {"openreview.net": "OpenReview", "neurips.cc": "NeurIPS"}


def year_of(key, f):
    raw = f.get("year", "").strip()
    if re.fullmatch(r"[0-9]+", raw):  # not str.isdigit(): that accepts Unicode digits int() rejects
        return int(raw)
    warn(f"{key}: " + (f"year {raw!r} is not a number" if raw else "missing year") + "; shown as n.d.")
    return None


def month_of(f):
    raw = f.get("month", "").strip().lower()
    if re.fullmatch(r"[0-9]+", raw) and 1 <= int(raw) <= 12:
        return int(raw)
    for names in (MONTHS, MONTH_NAMES):
        if raw in names:
            return names.index(raw) + 1
    return None


def normalize_doi(doi):
    return re.sub(r"^(doi:\s*|https?://(dx\.)?doi\.org/)", "", doi.strip(), flags=re.I)


def checked_url(key, url):
    """Undo BibTeX escapes and allow only http(s) or site-relative URLs."""
    url = url.strip()
    for esc, ch in (("\\_", "_"), ("\\%", "%"), ("\\&", "&"), ("\\#", "#")):
        url = url.replace(esc, ch)
    if re.search(r"[\x00-\x1f\x7f\\]", url):  # browsers read /\ as //
        raise BibError(f"{key}: URL contains a backslash or control character: {url!r}")
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
    eid = re.sub(r"^arxiv:\s*", "", f.get("eprint", "").strip(), flags=re.I)
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


def dedupe_key(url):
    """Equal for DOI / arXiv-abs / plain URLs that differ only in scheme, host case, version."""
    p = urlparse(url)
    host = p.netloc.lower()
    if p.scheme in ("http", "https"):
        if host in ("doi.org", "dx.doi.org"):
            return "doi:" + unquote(p.path.lstrip("/")).lower()
        if host in ("arxiv.org", "www.arxiv.org") and p.path.startswith("/abs/"):
            return "arxiv:" + re.sub(r"v\d+$", "", p.path[5:]).lower()
    return f"{host}{p.path}?{p.query}#{p.fragment}"


def links_of(key, f):
    """Display-ordered links; the first occurrence of a (normalized) URL wins."""
    raw = []
    if f.get("pdf"):
        name = f["pdf"].strip()
        if re.search(r"[/\\]|\.\.", name):
            raise BibError(f"{key}: pdf must be a bare file name, got {name!r}")
        raw.append(("PDF", "/publications/" + name))
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
        dk = dedupe_key(url)
        if dk not in seen:
            seen.add(dk)
            out.append({"label": label, "url": url})
    return out


def venue_html(key, kind, entry_type, f):
    """Short venue line for the list (not a citation)."""
    def h(name):
        return tex_to_html(f.get(name, ""))
    number = h("number") or h("issue")
    link = eprint_link(key, f) if kind == "preprint" else None
    if link:
        # the archive, not the stale journal text ("ArXiv e-prints")
        label, _ = link
        eid = re.sub(r"^arxiv:\s*", "", f["eprint"].strip(), flags=re.I)
        return html.escape(f"arXiv:{eid}" if label == "arXiv" else label)
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


# --- APA 7 references ---------------------------------------------------------

# Fields left out of the copied BibTeX: JabRef bookkeeping and site-only fields.
BIBTEX_DROP = {"owner", "timestamp", "pubtype", "themes", "tags", "selected"}
BIBTEX_ORDER = ["author", "title", "journal", "booktitle", "editor", "chapter", "school",
                "publisher", "howpublished", "year", "month", "volume", "number", "issue",
                "pages", "note", "doi", "url", "url2", "eprint", "archiveprefix",
                "primaryclass", "abstract"]


def apa_authors(names):
    """APA 7 author list from already-escaped 'Family, I.' strings."""
    if len(names) <= 1:
        return "".join(names)
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def authors_html(authors):
    """Every author, APA-style separators, lab members wrapped in <strong>."""
    names = [f'<strong class="member">{html.escape(a["display"])}</strong>' if a["member"]
             else html.escape(a["display"]) for a in authors]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + ", &amp; " + names[-1]


def _end(s):
    """Close a reference element with a period unless it already ends in . ? !
    An empty element stays empty so it is dropped from the reference."""
    s = s.rstrip()
    if not s:
        return ""
    return s if re.sub(r"</?i>", "", s).endswith((".", "?", "!")) else s + "."


def _strip_period(s):
    return s[:-1] if s.endswith(".") else s


def _ital(s):
    return f"<i>{s}</i>" if s else ""


def _editors_apa(f):
    eds = persons(f.get("editor", ""))
    names = [html.escape((" ".join(_initials(g) for g in e["given"].split()) + " " + e["family"]
                           + (" " + e["jr"] if e["jr"] else "")).strip()) for e in eds]
    if not names:
        return ""
    joined = names[0] if len(names) == 1 else (
        f"{names[0]} & {names[1]}" if len(names) == 2 else ", ".join(names[:-1]) + ", & " + names[-1])
    return f"{joined} ({'Eds.' if len(names) > 1 else 'Ed.'}),"


def _in_book(f, book, pages):
    """'In E. Editor (Ed.), *Book* (pp. x)' or '' when there is no book title."""
    if not book:
        return ""
    eds = _editors_apa(f)
    src = "In " + (eds + " " if eds else "") + _ital(book)
    return src + (f" (pp. {pages})" if pages else "")


def _apa_link(key, kind, f):
    """DOI first, then a preprint DOI, then the URL."""
    if f.get("doi"):
        return checked_url(key, "https://doi.org/" + normalize_doi(f["doi"]))
    eid = re.sub(r"^arxiv:\s*", "", f.get("eprint", "").strip(), flags=re.I)
    prefix = (f.get("archiveprefix", "").strip() or "arXiv").lower()
    if kind == "preprint" and eid and prefix in ("arxiv", "biorxiv"):
        return (f"https://doi.org/10.48550/arXiv.{eid}" if prefix == "arxiv"
                else f"https://doi.org/10.1101/{eid}")
    url = f.get("url", "").strip()
    return checked_url(key, url) if url else ""


def apa_html(key, kind, entry_type, f, authors, year, month):
    def h(name):
        return tex_to_html(f.get(name, ""))
    if f.get("eprint") and (f.get("archiveprefix", "").strip() or "arXiv").lower() not in ("arxiv", "biorxiv"):
        raise BibError(f"{key}: unknown archivePrefix {f.get('archiveprefix', '').strip()!r}")
    title = h("title")
    when = str(year) if year else "n.d."
    if re.search(r"\bin press\b", f.get("note", ""), re.I):
        when = "in press"
    elif kind == "abstract" and month and year:
        when += ", " + MONTH_NAMES[month - 1].capitalize()
        day = f.get("day", "").strip()
        if re.fullmatch(r"[0-9]{1,2}", day) and 1 <= int(day) <= 31:
            when += " " + str(int(day))
    date = f"({when})."
    number = h("number") or h("issue")
    pages = re.sub(r"(?<=[0-9])-(?=[0-9])", "\u2013", h("pages"))  # 10-20 -> en dash
    publisher = h("publisher")
    italic_title = _ital(title)

    if kind == "journal":
        title_part = _end(title)
        vol = h("volume")
        segs = [_ital(h("journal")) + (f"({number})" if number and not vol else ""),
                (_ital(vol) + (f"({number})" if number else "")) if vol else "",
                (pages if re.search(r"[-\u2013]", pages) else f"Article {pages}") if pages else ""]
        rest = [_end(", ".join(x for x in segs if x))]
    elif kind == "conference":
        title_part = _end(title)
        # Some older entries keep the proceedings title in `journal` (e.g. Paiva2008c).
        rest = [_end(_in_book(f, h("booktitle") or h("journal"), pages)), _end(publisher)]
    elif kind == "abstract":
        label = "Poster presentation" if "poster" in f.get("note", "").lower() else "Conference abstract"
        title_part = f"{_ital(_strip_period(title))} [{label}]."
        venue = ", ".join(x for x in (h("booktitle") or h("howpublished") or h("journal"),
                                      h("address") or h("location")) if x)
        rest = [_end(venue)]
    elif kind == "preprint":
        title_part = _end(italic_title)
        archive = {"arxiv": "arXiv", "biorxiv": "bioRxiv"}.get(
            (f.get("archiveprefix", "").strip() or "arXiv").lower()) if f.get("eprint") else ""
        rest = [_end(archive)]
    elif kind == "manuscript":
        title_part = f"{_ital(_strip_period(title))} [Unpublished manuscript]."
        rest = []
    elif kind == "thesis":
        masters = entry_type.lower() != "phdthesis"
        degree = "master&#x27;s thesis" if masters else "doctoral dissertation"
        school = h("school")
        if publisher or f.get("url"):
            label = degree.capitalize() + (", " + school if school else "")
            rest = [_end(publisher)]
        else:
            label = "Unpublished " + degree
            rest = [_end(school)]
        title_part = f"{_ital(_strip_period(title))} [{label}]."
    elif kind == "chapter":
        title_part = _end(title)
        if not h("booktitle"):
            warn(f"{key}: chapter without booktitle")
        rest = [_end(_in_book(f, h("booktitle"), pages)), _end(publisher)]
    elif kind == "book":
        title_part = _end(italic_title)
        rest = [_end(publisher)]
    elif kind == "patent":
        num = h("number").replace(":", " ")
        what = "U.S. Patent Application Publication" if re.search(r"A\d$", num) else "U.S. Patent"
        title_part = (f"{_ital(_strip_period(title))} ({what} No. {num})." if num
                      else _end(italic_title))
        rest = [_end(h("journal") or "U.S. Patent and Trademark Office")]
    else:
        title_part = _end(italic_title)
        rest = [_end(h("howpublished"))]

    link = _apa_link(key, kind, f)
    names = [html.escape(a["display"]) for a in authors]
    head = [_end(apa_authors(names)), date, title_part] if names else [title_part, date]
    return " ".join(x for x in head + rest + [html.escape(link)] if x)


def bibtex_of(entry):
    """The entry as BibTeX for copying: original TeX, whitespace collapsed, fixed field order."""
    fields = {k.lower(): " ".join(str(v.value).split()) for k, v in entry.fields_dict.items()}
    order = [k for k in BIBTEX_ORDER if k in fields] + sorted(k for k in fields if k not in BIBTEX_ORDER)
    lines = [f"@{entry.entry_type}{{{entry.key},"]
    for k in order:
        v = fields[k]
        if k in BIBTEX_DROP or k.startswith("_") or not v:
            continue
        bare = (k == "month" and v.lower() in MONTHS) or (k == "year" and re.fullmatch(r"[0-9]+", v))
        lines.append(f"  {k} = {v if bare else '{' + v + '}'},")
    lines.append("}")
    return "\n".join(lines)


# --- labels and roster --------------------------------------------------------

# Letters that NFKD does not decompose; mapped so 'Sok\u00f3\u0142' folds to 'sokol'.
_FOLD = str.maketrans({"\u0142": "l", "\u0141": "L", "\u00f8": "o", "\u00d8": "O",
                       "\u0111": "d", "\u0110": "D", "\u00df": "ss"})
_KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def fold(s):
    """Accent- and case-insensitive key for name matching."""
    s = unicodedata.normalize("NFKD", s.translate(_FOLD))
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def load_labels(path):
    """-> ({theme id: name}, {tag id: (facet id, name)}); empty when the file is absent."""
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    themes, tags = {}, {}

    def check(id_):
        if not isinstance(id_, str) or not _KEBAB.fullmatch(id_):
            raise BibError(f"{path}: label id {id_!r} must be kebab-case")

    for t in data.get("themes", []):
        check(t["id"])
        if t["id"] in themes:
            raise BibError(f"{path}: label id {t['id']!r} defined twice")
        themes[t["id"]] = t["name"]
    for facet in data.get("facets", []):
        check(facet["id"])
        for t in facet.get("tags", []):
            check(t["id"])
            if t["id"] in tags or t["id"] in themes:
                raise BibError(f"{path}: label id {t['id']!r} defined twice")
            tags[t["id"]] = (facet["id"], t["name"])
    return themes, tags


def _ids(value):
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def labels_of(key, f, themes, tags):
    th, tg = _ids(f.get("themes")), _ids(f.get("tags"))
    labels = []
    for t in th:
        if t not in themes:
            raise BibError(f"{key}: unknown theme {t!r}")
        labels.append({"group": "theme", "id": t, "name": themes[t]})
    for t in tg:
        if t not in tags:
            raise BibError(f"{key}: unknown tag {t!r}")
        labels.append({"group": tags[t][0], "id": t, "name": tags[t][1]})
    return th, tg, labels


def selected_of(key, f):
    v = f.get("selected", "false").strip().lower()
    if v not in ("true", "false"):
        raise BibError(f"{key}: selected must be true or false, got {v!r}")
    return v == "true"


def load_roster(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _given_words(given):
    """Folded given-name words, initials reduced to one letter: 'I. Memming' -> ['i', 'memming']."""
    return fold(given).replace(".", " ").replace("-", " ").split()


def roster_index(roster):
    """{folded family name: [given-name word lists]} for every member and alias."""
    index = {}
    for m in roster:
        for n in [m] + list(m.get("aliases", [])):
            index.setdefault(fold(n["family"]), []).append(_given_words(n["given"]))
    return index


def is_member(author, index):
    """Same family name, and the author's first given word matches any of the
    member's given words: exactly, or as an initial ('I.' ~ 'Il', 'Memming' ~
    'Il Memming', but 'Mijung' !~ 'Il Memming')."""
    words = _given_words(author["given"])
    if not author["family"] or not words:
        return False
    g = words[0]
    for member_words in index.get(fold(author["family"]), []):
        for r in member_words:
            if g[0] == r[0] and (len(g) == 1 or len(r) == 1 or g == r):
                return True
    return False


def entry_json(entry, themes, tags, members):
    f = fields_of(entry)
    key = entry.key
    kind = kind_of(key, entry.entry_type, f)
    year = year_of(key, f)
    month = month_of(f)
    authors = persons(f.get("author", ""))
    for a in authors:
        a["member"] = is_member(a, members)
    th, tg, labels = labels_of(key, f, themes, tags)
    apa = apa_html(key, kind, entry.entry_type, f, authors, year, month)
    return {
        "key": key,
        "kind": kind,
        "kind_name": KIND_NAMES[kind],
        "year": year,
        "month": month,
        "year_label": str(year) if year else "n.d.",
        "authors": authors,
        "authors_html": authors_html(authors),
        "title": tex_to_text(f.get("title", "")),
        "title_html": tex_to_html(f.get("title", "")),
        "venue_html": venue_html(key, kind, entry.entry_type, f),
        "note_html": tex_to_html(f.get("note", "")),
        "abstract_html": tex_to_html(f.get("abstract", "")),
        "links": links_of(key, f),
        "themes": th,
        "tags": tg,
        "labels": labels,
        "selected": selected_of(key, f),
        "apa_html": apa,
        "apa_text": html.unescape(re.sub(r"</?i>", "", apa)),
        "bibtex": bibtex_of(entry),
    }


def build(bib_path, labels_path, roster_path):
    themes, tags = load_labels(labels_path)
    members = roster_index(load_roster(roster_path))
    entries = [entry_json(e, themes, tags, members) for e in parse_bib(bib_path)]
    entries.sort(key=lambda e: (e["year"] is None, -(e["year"] or 0),
                                e["month"] is None, -(e["month"] or 0), e["key"]))
    return entries


def write_json(entries, out_path):
    """Atomic write: the old file survives any failure before os.replace."""
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, out_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render catniplab.bib into _data/publications.json.")
    ap.add_argument("--bib", default=DEFAULT_BIB)
    ap.add_argument("--labels", default=DEFAULT_LABELS)
    ap.add_argument("--roster", default=DEFAULT_ROSTER)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    try:
        entries = build(args.bib, args.labels, args.roster)
    except BibError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    write_json(entries, args.out)
    counts = {}
    for e in entries:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    summary = ", ".join(f"{k} {n}" for k, n in sorted(counts.items()))
    print(f"wrote {len(entries)} entries to {args.out} ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
