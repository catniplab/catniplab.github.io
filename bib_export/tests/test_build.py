"""Unit tests for build_publications.py. Non-ASCII expectations use \\u escapes."""
import pytest


# --- text pipeline ---------------------------------------------------------

def test_tex_to_html_decodes_escapes_and_keeps_italics(bp):
    tex = r"{H}ilbert spaces \& $1/n$ {\it in vivo} 50\% <b>"
    assert bp.tex_to_html(tex) == "Hilbert spaces &amp; 1/n <i>in vivo</i> 50% &lt;b&gt;"


def test_textit_and_emph_become_italics(bp):
    assert bp.tex_to_html(r"\textit{a} and \emph{b}") == "<i>a</i> and <i>b</i>"


def test_nested_braces_in_italics(bp):
    assert bp.tex_to_html(r"\textit{{H}ilbert}") == "<i>Hilbert</i>"
    assert bp.tex_to_html(r"{\it Mart{\'\i}n}") == "<i>Mart\u00edn</i>"


def test_tex_to_text_drops_italics(bp):
    assert bp.tex_to_text(r"probability {\it in vivo}") == "probability in vivo"


def test_bare_percent_is_not_a_comment(bp):
    assert bp.tex_to_text("50% of trials\nand more") == "50% of trials and more"


def test_whitespace_and_dashes(bp):
    assert bp.tex_to_text("a--b\n\t  c") == "a\u2013b c"


def test_accents(bp):
    assert bp.tex_to_text(r"S\'agodi Soko{\l} Mart{\'\i}n") == "S\u00e1godi Soko\u0142 Mart\u00edn"


def test_markup_injection_is_escaped(bp):
    tex = r'A <script>alert("x")</script> \& more 5%'
    assert bp.tex_to_html(tex) == (
        "A &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; more 5%")


# --- names -----------------------------------------------------------------

@pytest.mark.parametrize("raw, display, family", [
    ("de Polavieja, Gonzalo G.", "de Polavieja, G. G.", "de Polavieja"),
    ("Van Vaerenbergh, Steven", "Van Vaerenbergh, S.", "Van Vaerenbergh"),
    (r"Mart{\'\i}n-S{\'a}nchez, Guillermo", "Mart\u00edn-S\u00e1nchez, G.",
     "Mart\u00edn-S\u00e1nchez"),
    ("Smith, Jr., John", "Smith, J., Jr.", "Smith"),
    ("Jean-Pierre Dupont", "Dupont, J.-P.", "Dupont"),
    ("Brinkman, Braden A W", "Brinkman, B. A. W.", "Brinkman"),
    (r"S\'agodi, \'Abel", "S\u00e1godi, \u00c1.", "S\u00e1godi"),
    (r"Piotr Sok\'o\l{}", "Sok\u00f3\u0142, P.", "Sok\u00f3\u0142"),
])
def test_person_display(bp, raw, display, family):
    p = bp.person(raw)
    assert p["display"] == display
    assert p["family"] == family


def test_persons_splits_on_and_and_collapses_whitespace(bp):
    ps = bp.persons("Park, Il Memming and\n\t Pillow, Jonathan")
    assert [p["display"] for p in ps] == ["Park, I. M.", "Pillow, J."]


def test_bad_name_list_is_bib_error(bp, build_one):
    with pytest.raises(bp.BibError, match="cannot parse names"):
        build_one("@article{K, title = {T}, author = {A Bee and C Dee,}, year = 2010}")


# --- kinds -----------------------------------------------------------------

@pytest.mark.parametrize("etype, extra, kind", [
    ("article", "", "journal"),
    ("inproceedings", "", "conference"),
    ("conference", "", "conference"),
    ("unpublished", "eprint = {1234.5678},", "preprint"),
    ("unpublished", "url = {https://example.org/x},", "preprint"),
    ("unpublished", "", "manuscript"),
    ("phdthesis", "", "thesis"),
    ("mastersthesis", "", "thesis"),
    ("inbook", "", "chapter"),
    ("incollection", "", "chapter"),
    ("book", "", "book"),
    ("misc", "", "other"),
    ("inproceedings", "pubtype = {abstract},", "abstract"),
    ("misc", "pubtype = {patent},", "patent"),
])
def test_kind(build_one, etype, extra, kind):
    [e] = build_one(f"@{etype}{{K, author = {{A, B}}, title = {{T}}, year = 2020, {extra}}}")
    assert e["kind"] == kind


def test_unknown_pubtype_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="pubtype"):
        build_one("@misc{K, title = {T}, pubtype = {poster}}")


# --- parse failures --------------------------------------------------------

def test_duplicate_field_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="failed to parse"):
        build_one("@article{K, year = 2020, year = 2021, title = {T}}")


def test_duplicate_key_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="failed to parse"):
        build_one("@article{K, title = {A}}\n@article{K, title = {B}}\n")


def test_unbalanced_brace_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="failed to parse"):
        build_one("@article{K1, title = {a {b}, year = 2020}\n@article{K2, title = {ok}}\n")


def test_unsafe_key_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="bib key"):
        build_one("@article{K<x, title = {T}}")


def test_comment_blocks_are_ignored(build_one):
    entries = build_one("@Comment{jabref-meta: databaseType:bibtex;}\n@article{K, title = {T}}\n")
    assert [e["key"] for e in entries] == ["K"]


# --- dates -------------------------------------------------------------------

@pytest.mark.parametrize("month, expect", [
    ("mar", 3), ("{July}", 7), ("{Aug}", 8), ("Jul", 7), ("dec", 12), ("{11}", 11), ("{spring}", None),
])
def test_month(build_one, month, expect):
    [e] = build_one("@article{K, title = {T}, year = 2020, month = " + month + "}")
    assert e["month"] == expect


@pytest.mark.parametrize("year_field, year, label", [
    ("year = 2021,", 2021, "2021"), ("year = {?},", None, "n.d."), ("", None, "n.d."),
])
def test_year(build_one, year_field, year, label):
    [e] = build_one("@article{K, title = {T}, " + year_field + "}")
    assert (e["year"], e["year_label"]) == (year, label)


# --- links -------------------------------------------------------------------

def _links(build_one, fields):
    [e] = build_one("@article{K, title = {T}, year = 2020, " + fields + "}")
    return [(link["label"], link["url"]) for link in e["links"]]


def test_doi_prefix_stripped(build_one):
    assert _links(build_one, "doi = {doi: 10.3389/conf.neuro.06.2009.03.227}") == [
        ("DOI", "https://doi.org/10.3389/conf.neuro.06.2009.03.227")]


def test_eprint_defaults_to_arxiv(build_one):
    assert _links(build_one, "eprint = {1302.5964}") == [("arXiv", "https://arxiv.org/abs/1302.5964")]


def test_eprint_biorxiv(build_one):
    assert _links(build_one, "archivePrefix = {bioRxiv}, eprint = {178418}") == [
        ("bioRxiv", "https://www.biorxiv.org/content/10.1101/178418")]


def test_archiveprefix_without_eprint_gives_no_link(build_one):
    assert _links(build_one, "archivePrefix = {bioRxiv}") == []


def test_url_labels(build_one):
    assert _links(build_one, "url = {https://openreview.net/forum?id=X}, "
                             "url2 = {https://neurips.cc/virtual/2026/poster/1}") == [
        ("OpenReview", "https://openreview.net/forum?id=X"),
        ("NeurIPS", "https://neurips.cc/virtual/2026/poster/1")]
    assert _links(build_one, "url = {https://www.mdpi.com/1099-4300/15/5/1738/pdf}") == [
        ("PDF", "https://www.mdpi.com/1099-4300/15/5/1738/pdf")]
    assert _links(build_one, "url = {https://example.org/page}") == [("Link", "https://example.org/page")]


def test_link_order_and_dedupe(build_one):
    assert _links(build_one, "pdf = {a.pdf}, url = {https://doi.org/10.1/x}, doi = {10.1/x}, "
                             "code = {https://github.com/x/y}, data = {https://zenodo.org/1}, "
                             "youtube = {https://youtu.be/z}") == [
        ("PDF", "/publications/a.pdf"),
        ("DOI", "https://doi.org/10.1/x"),
        ("Code", "https://github.com/x/y"),
        ("Data", "https://zenodo.org/1"),
        ("Video", "https://youtu.be/z")]


def test_escaped_underscore_in_url(build_one):
    assert _links(build_one, r"url = {http://ieeexplore.ieee.org/xpls/abs\_all.jsp?arnumber=5}") == [
        ("Link", "http://ieeexplore.ieee.org/xpls/abs_all.jsp?arnumber=5")]


def test_javascript_url_rejected(bp, build_one):
    with pytest.raises(bp.BibError, match="URL"):
        build_one("@article{K, title = {T}, url = {javascript:alert(1)}}")


# --- venue -------------------------------------------------------------------

def _venue(build_one, bib):
    [e] = build_one(bib)
    return e["venue_html"]


def test_venue_journal(build_one):
    assert _venue(build_one, "@article{K, title = {T}, journal = {Entropy}, volume = {15}, "
                             "number = {5}, pages = {1738--1755}}") == "Entropy, 15(5), 1738\u20131755"


def test_venue_issue_is_number(build_one):
    assert _venue(build_one, "@article{K, title = {T}, journal = {J}, volume = {2}, issue = {3}}") == "J, 2(3)"


def test_venue_pages_kept_as_strings(build_one):
    assert _venue(build_one, "@article{K, title = {T}, journal = {J}, pages = {e3001803}}") == "J, e3001803"
    assert _venue(build_one, "@article{K, title = {T}, journal = {J}, pages = {178418+}}") == "J, 178418+"


def test_venue_conference(build_one):
    assert _venue(build_one, "@inproceedings{K, title = {T}, booktitle = {Advances in Neural "
                             "Information Processing Systems (NeurIPS)}, pages = {1--9}}") == (
        "Advances in Neural Information Processing Systems (NeurIPS), 1\u20139")


def test_venue_thesis(build_one):
    assert _venue(build_one, "@phdthesis{K, title = {T}, school = {Stony Brook University}}") == (
        "Doctoral dissertation, Stony Brook University")
    assert _venue(build_one, "@mastersthesis{K, title = {T}, school = {U}}") == "Master&#x27;s thesis, U"
    assert _venue(build_one, "@phdthesis{K, title = {T}, publisher = {NOVA Repository}}") == (
        "Doctoral dissertation, NOVA Repository")


def test_venue_chapter(build_one):
    assert _venue(build_one, "@inbook{K, title = {T}, booktitle = {Statistical Signal Processing "
                             "for Neuroscience}, publisher = {Academic Press}}") == (
        "In Statistical Signal Processing for Neuroscience, Academic Press")
    assert _venue(build_one, "@inbook{K, title = {T}, chapter = {9}, publisher = {Springer}}") == (
        "Chapter 9, Springer")


def test_venue_other_uses_howpublished(build_one):
    assert _venue(build_one, "@misc{K, title = {T}, howpublished = {Poster presented at "
                             "{XLVI Dynamics Days Europe}, Lisbon, Portugal}}") == (
        "Poster presented at XLVI Dynamics Days Europe, Lisbon, Portugal")


def test_note_and_abstract_html(build_one):
    [e] = build_one("@article{K, title = {T}, note = {(in press)}, abstract = {We show $x$ and 5% \\& <y>.}}")
    assert e["note_html"] == "(in press)"
    assert e["abstract_html"] == "We show x and 5% &amp; &lt;y&gt;."
