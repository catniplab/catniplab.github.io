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
