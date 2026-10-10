"""Semantic parity with the last JabRef export (site commit 717c912)."""
import html
import os
import re
import subprocess

import pytest

BASE = "717c912"
SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Repairs the 717c912 bib needs before bibtexparser accepts it; each applies once.
# Brinkman2021a had a second, identical year field.
BRINKMAN_DUP = "  month     =  mar,\n  year      =  2022,\n}"
# Paiva2010a's editor list ended in a trailing comma.
PAIVA_COMMA = "Petros Xanthopoulos,}"
# Exact link differences (new vs old) the generator makes on purpose.
# Keys not listed must have identical link URL sets.
# Sagodi2024a: the url2 field is now rendered (the old layout ignored it).
# The seven "removed" keys: the old page listed the same resource twice, once
# from eprint/doi (https form) and once from the raw url field (http form);
# the generator dedupes on a normalized URL and keeps the first (https) link.
EXPECTED_LINK_DIFFS = {
    "Sagodi2024a": {"added": {"https://papers.neurips.cc/paper_files/paper/2024/hash/"
                              "7b78a2a7360d5a9ad750834dc5a33bfb-Abstract-Conference.html"},
                    "removed": set()},
    "Dowling2026a": {"added": set(), "removed": {"http://arxiv.org/abs/2605.31163"}},
    "Park2026a": {"added": set(), "removed": {"http://arxiv.org/abs/2604.23903"}},
    "Sagodi2026b": {"added": set(), "removed": {"http://arxiv.org/abs/2602.08640"}},
    "Sagodi2025b": {"added": set(), "removed": {"http://arxiv.org/abs/2507.05505"}},
    "Dowling2021b": {"added": set(), "removed": {"http://arxiv.org/abs/2107.07098"}},
    "Zhao2019a": {"added": set(), "removed": {"http://dx.doi.org/10.1109/TPAMI.2022.3153225"}},
    "Paiva2007a": {"added": set(), "removed": {"http://dx.doi.org/10.1109/IJCNN.2007.4371236"}},
}
# Same for titles: key -> (old, new) with the reason in a comment.
EXPECTED_TITLE_DIFFS = {}


def _git_show(path):
    return subprocess.run(["git", "-C", SITE, "show", f"{BASE}:{path}"],
                          check=True, capture_output=True, text=True).stdout


def _norm(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


@pytest.fixture(scope="module")
def old_and_new(bp, tmp_path_factory):
    bib = _git_show("bib_export/catniplab.bib")
    assert bib.count(BRINKMAN_DUP) == 1
    bib = bib.replace(BRINKMAN_DUP, "  month     =  mar,\n}")
    assert bib.count(PAIVA_COMMA) == 1
    bib = bib.replace(PAIVA_COMMA, "Petros Xanthopoulos}")
    d = tmp_path_factory.mktemp("parity")
    (d / "old.bib").write_text(bib, encoding="utf-8")
    new = {e["key"]: e for e in bp.build(str(d / "old.bib"), str(d / "none"), str(d / "none"))}
    rows = re.findall(r'<tr id="([^"]+)" class="entry">(.*?)</tr>', _git_show("publications.html"), re.S)
    old = {}
    for key, body in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        old[key] = {"title": _norm(cells[1]), "year": _norm(cells[2]),
                    "links": set(re.findall(r'href="([^"]+)"', cells[5]))}
    return old, new


def test_same_keys(old_and_new):
    old, new = old_and_new
    assert set(old) == set(new) and len(new) == 173


def test_same_years(old_and_new):
    old, new = old_and_new
    diffs = {k: (o["year"], new[k]["year_label"]) for k, o in old.items()
             if (o["year"] if o["year"] not in ("", "?") else "n.d.") != new[k]["year_label"]}
    assert diffs == {}


def test_same_titles(old_and_new):
    old, new = old_and_new
    diffs = {k: (o["title"], new[k]["title"]) for k, o in old.items()
             if o["title"] != new[k]["title"]}
    assert diffs == EXPECTED_TITLE_DIFFS


def test_same_links(old_and_new):
    old, new = old_and_new
    diffs = {}
    for k, o in old.items():
        urls = {l["url"] for l in new[k]["links"]}
        d = {"added": urls - o["links"], "removed": o["links"] - urls}
        if d != EXPECTED_LINK_DIFFS.get(k, {"added": set(), "removed": set()}):
            diffs[k] = d
    assert diffs == {}
    for k in EXPECTED_LINK_DIFFS:
        assert k in old
