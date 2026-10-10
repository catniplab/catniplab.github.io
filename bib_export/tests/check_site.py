#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""Structural checks on the built /publications.html. Exits 1 on any failure.

Usage: python check_site.py SITE_OUT DATA_JSON SITE_SRC
"""
import gzip
import json
import os
import re
import sys
from html.parser import HTMLParser

BUDGET_RAW = 800_000
BUDGET_GZIP = 160_000
BUDGET_JS = 9 * 1024
BUDGET_SCSS = 7 * 1024
ALLOWED_HREF = ("http://", "https://", "/", "#", "?", "mailto:")


class HostileFixtureCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.found = False
        self.unsafe = False
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "li" and ("id", "HostileFixture") in attrs:
            self.inside = self.found = True
        if self.inside:
            self.unsafe |= tag not in {"li", "p", "span", "strong", "i", "a", "details", "summary", "pre"}
            self.unsafe |= any(name.startswith("on") or name == "data-pub-fixture-xss" for name, _ in attrs)

    def handle_endtag(self, tag):
        if tag == "li":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.text.append(data)


def main(out_dir, data_path, src_dir):
    with open(os.path.join(out_dir, "publications.html"), encoding="utf-8") as fh:
        page = fh.read()
    with open(data_path, encoding="utf-8") as fh:
        data = json.load(fh)
    problems = []
    all_ids = re.findall(r'\sid="([^"]+)"', page)
    dupes = sorted({i for i in all_ids if all_ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate ids: {dupes[:10]}")
    pub_ids = re.findall(r'<li id="([^"]+)" class="pub"', page)
    keys = {e["key"] for e in data}
    if "HostileFixture" in keys:
        guard = HostileFixtureCheck()
        guard.feed(page)
        guard.close()
        if not guard.found or guard.unsafe or not all(
                f'data-pub-fixture-xss="{field}"' in "".join(guard.text)
                for field in ("title", "author", "journal", "note", "abstract")):
            problems.append("hostile fixture markup was rendered as HTML or its literal text was lost")
    if set(pub_ids) != keys:
        problems.append(f"entry ids differ from data: missing {sorted(keys - set(pub_ids))[:10]}, "
                        f"extra {sorted(set(pub_ids) - keys)[:10]}")
    n_abs_page = len(re.findall(r'class="pub" data-kind="abstract"', page))
    n_abs_data = sum(e["kind"] == "abstract" for e in data)
    if n_abs_page != n_abs_data:
        problems.append(f"abstract entries: page {n_abs_page}, data {n_abs_data}")
    bad = [h for h in re.findall(r'href="([^"]*)"', page)
           if h.startswith("//") or not h.startswith(ALLOWED_HREF)]
    if bad:
        problems.append(f"disallowed hrefs: {bad[:10]}")
    raw = page.encode("utf-8")
    gz = len(gzip.compress(raw))
    if len(raw) > BUDGET_RAW or gz > BUDGET_GZIP:
        problems.append(f"page size {len(raw)} raw / {gz} gzip over budget")
    js_path = os.path.join(out_dir, "js", "publications.js")
    js = os.path.getsize(js_path) if os.path.isfile(js_path) else None
    if js is None:
        problems.append("js/publications.js missing")
    elif js > BUDGET_JS:
        problems.append(f"publications.js is {js} bytes")
    scss = os.path.getsize(os.path.join(src_dir, "_sass", "_publications.scss"))
    if scss > BUDGET_SCSS:
        problems.append(f"_publications.scss is {scss} bytes")
    print(f"publications.html: {len(pub_ids)} entries, {len(raw)} bytes raw, {gz} gzip; js {js} bytes")
    for p in problems:
        print("FAIL", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
