"""Unit tests for build_publications.py. Non-ASCII expectations use \\u escapes."""
import re

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


_INV = (r"@inproceedings{K, author = {A, B}, title = {T}, booktitle = {Proc X}, "
        r"pages = {1--5}, year = 2018, ")


def test_invited_pubtype(build_one):
    [e] = build_one(_INV + "pubtype = {invited}}")
    [c] = build_one(_INV.rstrip(", ") + "}")
    assert (e["kind"], e["kind_name"], e["refereed"]) == ("invited", "Invited paper", False)
    assert c["kind"] == "conference"
    assert e["apa_text"] == c["apa_text"] and "In Proc X" in e["apa_text"]
    assert e["apa_html"] == c["apa_html"] and e["venue_html"] == c["venue_html"]
    differ = {k for k in e if e[k] != c[k]}
    assert differ <= {"kind", "kind_name", "refereed", "bibtex"}


@pytest.mark.parametrize("etype, extra, refereed", [
    ("article", "", True),
    ("inproceedings", "", True),
    ("unpublished", "eprint = {1234.5678},", False),
    ("inproceedings", "pubtype = {abstract},", False),
    ("phdthesis", "", False),
    ("inbook", "", False),
    ("book", "", False),
    ("misc", "pubtype = {patent},", False),
    ("unpublished", "", False),
    ("misc", "", False),
])
def test_refereed(build_one, etype, extra, refereed):
    [e] = build_one(f"@{etype}{{K, author = {{A, B}}, title = {{T}}, year = 2020, {extra}}}")
    assert e["refereed"] is refereed


def test_refereed_follows_kind_name_in_entry(build_one):
    [e] = build_one("@article{K, author = {A, B}, title = {T}, year = 2020}")
    keys = list(e)
    assert keys[keys.index("kind_name") + 1] == "refereed"


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


@pytest.mark.parametrize("body, expected", [
    ("eprint = {2604.23903}, archivePrefix = {arXiv},", "arXiv:2604.23903"),
    ("journal = {ArXiv e-prints}, eprint = {1511.07367},", "arXiv:1511.07367"),
    ("eprint = {arXiv:2602.08640},", "arXiv:2602.08640"),
    ("eprint = {2001.00001}, archivePrefix = {bioRxiv},", "bioRxiv"),
])
def test_venue_preprint_names_archive(build_one, body, expected):
    assert _venue(build_one, "@unpublished{K, title = {T}, " + body + " year = {2026}}") == expected


def test_venue_article_with_eprint_keeps_journal(build_one):
    assert _venue(build_one, "@article{K, title = {T}, journal = {Neuron}, "
                             "eprint = {2604.23903}, archivePrefix = {arXiv}}") == "Neuron"


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


# --- fix round 1: dedupe, URL safety, parsing ---------------------------------

def test_dedupe_doi_variants(build_one):
    assert _links(build_one, "url = {http://dx.doi.org/10.1/X}, doi = {10.1/x}") == [
        ("DOI", "https://doi.org/10.1/x")]


def test_dedupe_arxiv_variants(build_one):
    assert _links(build_one, "url = {http://arxiv.org/abs/1302.5964v2}, eprint = {1302.5964}") == [
        ("arXiv", "https://arxiv.org/abs/1302.5964")]
    assert _links(build_one, "url = {https://www.arxiv.org/abs/1302.5964}, eprint = {arXiv:1302.5964}") == [
        ("arXiv", "https://arxiv.org/abs/1302.5964")]


def test_dedupe_other_urls_scheme_and_host_case(build_one):
    assert _links(build_one, "url = {https://Example.org/a?b=1}, code = {http://example.ORG/a?b=1}") == [
        ("Link", "https://Example.org/a?b=1")]


@pytest.mark.parametrize("doi", ["https://dx.doi.org/10.1/x", "https://doi.org/10.1/x"])
def test_doi_url_forms_normalized(build_one, doi):
    assert _links(build_one, "doi = {" + doi + "}") == [("DOI", "https://doi.org/10.1/x")]


@pytest.mark.parametrize("field", [
    r"url = {/\evil.com}", "url = {//evil.com}", "url = {ftp://x}", "url2 = {javascript:alert(1)}",
    "code = {javascript:alert(1)}", "data = {ftp://x/y}", "youtube = {javascript:alert(1)}",
    "url = {https://x/a\\tb}", "pdf = {../x.pdf}", "pdf = {https://x/y.pdf}", r"pdf = {a\b.pdf}",
])
def test_unsafe_links_rejected(bp, build_one, field):
    with pytest.raises(bp.BibError):
        build_one("@article{K, title = {T}, " + field + "}")


def test_unknown_archiveprefix_raises(bp, build_one):
    with pytest.raises(bp.BibError, match="archivePrefix"):
        build_one("@article{K, title = {T}, archivePrefix = {foo}, eprint = {1}}")


def test_unicode_digits_do_not_crash(build_one):
    [e] = build_one("@article{K, title = {T}, year = {\u00b2}, month = {\u00b2}}")
    assert (e["year"], e["year_label"], e["month"]) == (None, "n.d.", None)


def test_month_names_exact(build_one):
    for month, expect in (("{March}", 3), ("{SEPTEMBER}", 9), ("{marvel}", None), ("{ma}", None)):
        [e] = build_one("@article{K, title = {T}, year = 2020, month = " + month + "}")
        assert e["month"] == expect


def test_missing_year_warning(build_one, capsys):
    build_one("@article{K, title = {T}}")
    assert "missing year; shown as n.d." in capsys.readouterr().err


# --- APA 7 -------------------------------------------------------------------

def _apa(build_one, bib):
    [e] = build_one(bib)
    return e["apa_text"]


def test_apa_journal(build_one):
    bib = ("@article{K, author = {Archer, Evan and Park, Il Memming and Pillow, Jonathan}, "
           "title = {Bayesian Estimators}, journal = {Entropy}, year = 2013, volume = {15}, "
           "number = {5}, pages = {1738--1755}, doi = {10.3390/e15051738}}")
    [e] = build_one(bib)
    assert e["apa_text"] == ("Archer, E., Park, I. M., & Pillow, J. (2013). Bayesian Estimators. "
                             "Entropy, 15(5), 1738\u20131755. https://doi.org/10.3390/e15051738")
    assert "<i>Entropy</i>, <i>15</i>(5)" in e["apa_html"]


def test_apa_conference(build_one):
    assert _apa(build_one, r"@inproceedings{K, author = {S\'agodi, \'Abel and Park, Il Memming}, "
                           r"title = {Universal Approximation}, booktitle = {Advances in Neural "
                           r"Information Processing Systems (NeurIPS)}, year = 2026, "
                           r"url = {https://openreview.net/forum?id=JFUIDA4w6C}}") == (
        "S\u00e1godi, \u00c1., & Park, I. M. (2026). Universal Approximation. In Advances in "
        "Neural Information Processing Systems (NeurIPS). https://openreview.net/forum?id=JFUIDA4w6C")


def test_apa_conference_with_venue_in_journal_field(build_one):
    assert _apa(build_one, "@inproceedings{K, author = {Park, Il}, title = {T}, "
                           "journal = {IEEE EMBC}, year = 2008}") == "Park, I. (2008). T. In IEEE EMBC."


def test_apa_abstract_and_poster(build_one):
    assert _apa(build_one, "@inproceedings{K, author = {Park, Il}, title = {Point Process Model.}, "
                           "booktitle = {Computational and Systems Neuroscience (COSYNE)}, year = 2009, "
                           "month = feb, pubtype = {abstract}}") == (
        "Park, I. (2009, February). Point Process Model [Conference abstract]. "
        "Computational and Systems Neuroscience (COSYNE).")
    assert _apa(build_one, "@misc{K, author = {Park, Il}, title = {UAP}, howpublished = {Dynamics "
                           "Days Europe}, year = 2026, month = {July}, note = {Poster presentation}, "
                           "pubtype = {abstract}}") == (
        "Park, I. (2026, July). UAP [Poster presentation]. Dynamics Days Europe.")


def test_apa_preprint_arxiv_doi(build_one):
    assert _apa(build_one, "@unpublished{K, author = {Park, Il Memming}, title = {Integrative "
                           "Modeling}, year = 2026, eprint = {2604.23903}, archivePrefix = {arXiv}}") == (
        "Park, I. M. (2026). Integrative Modeling. arXiv. https://doi.org/10.48550/arXiv.2604.23903")


def test_apa_preprint_biorxiv_doi(build_one):
    assert _apa(build_one, "@unpublished{K, author = {Park, Il Memming}, title = {Coding}, "
                           "year = 2020, eprint = {178418}, archivePrefix = {bioRxiv}}") == (
        "Park, I. M. (2020). Coding. bioRxiv. https://doi.org/10.1101/178418")


def test_apa_manuscript_no_year(build_one):
    assert _apa(build_one, r"@unpublished{K, author = {Paiva, Ant\'onio R. C.}, "
                           r"title = {Optimization in RKHS}, note = {Unpublished manuscript}}") == (
        "Paiva, A. R. C. (n.d.). Optimization in RKHS [Unpublished manuscript].")


def test_apa_thesis(build_one):
    assert _apa(build_one, r"@phdthesis{K, author = {Sok{\'o}{\l}, Piotr}, title = {Geometry of "
                           r"learning}, school = {Stony Brook University}, year = 2023}") == (
        "Sok\u00f3\u0142, P. (2023). Geometry of learning [Unpublished doctoral dissertation]. "
        "Stony Brook University.")
    assert _apa(build_one, "@phdthesis{K, author = {Vermani, Ayesha}, title = {Identifying Invariant "
                           "Representations}, year = 2025, publisher = {NOVA Repository}, "
                           "url = {http://hdl.handle.net/10362/190610}}") == (
        "Vermani, A. (2025). Identifying Invariant Representations [Doctoral dissertation]. "
        "NOVA Repository. http://hdl.handle.net/10362/190610")


def test_apa_chapter(build_one):
    assert _apa(build_one, r"@inbook{K, author = {Paiva, Ant\'onio R. C. and Park, Il}, "
                           r"title = {Inner Products}, booktitle = {Statistical Signal Processing for "
                           r"Neuroscience}, editor = {Karim G. Oweiss}, publisher = {Academic Press}, "
                           r"year = 2010, pages = {1--20}}") == (
        "Paiva, A. R. C., & Park, I. (2010). Inner Products. In K. G. Oweiss (Ed.), Statistical Signal "
        "Processing for Neuroscience (pp. 1\u201320). Academic Press.")


def test_apa_book(build_one):
    assert _apa(build_one, r"@book{K, author = {Pr\'incipe, Jos\'e C.}, title = {Information "
                           r"Theoretic Learning}, publisher = {Springer}, year = 2010, "
                           r"url = {http://www.springer.com/us/book/9781441915696}}") == (
        "Pr\u00edncipe, J. C. (2010). Information Theoretic Learning. Springer. "
        "http://www.springer.com/us/book/9781441915696")


def test_apa_patent_application(build_one):
    assert _apa(build_one, "@misc{K, author = {Nassar, Josue and Park, Il Memming}, title = {System "
                           "and method}, journal = {United States Patent and Trademark Office}, "
                           "number = {20250209344:A1}, year = 2025, pubtype = {patent}}") == (
        "Nassar, J., & Park, I. M. (2025). System and method (U.S. Patent Application Publication "
        "No. 20250209344 A1). United States Patent and Trademark Office.")


def test_apa_more_than_twenty_authors(build_one):
    names = " and ".join(f"A{i}, X" for i in range(1, 22))
    text = _apa(build_one, "@article{K, author = {" + names + "}, title = {T}, journal = {J}, year = 2020}")
    listed = ", ".join(f"A{i}, X." for i in range(1, 20))
    assert text.startswith(listed + ", . . . A21, X. (2020). T.")


def test_apa_without_author_starts_with_title(build_one):
    [e] = build_one("@misc{K, title = {Lab Report}, year = 2020, howpublished = {Online}}")
    assert e["apa_text"] == "Lab Report. (2020). Online."
    assert e["apa_html"].startswith("<i>Lab Report</i>.")
    assert e["authors"] == [] and e["authors_html"] == ""


def test_title_ending_in_question_mark_gets_no_extra_period(build_one):
    assert _apa(build_one, "@article{K, author = {Park, Il}, title = {Why?}, journal = {J}, year = 2020}") == (
        "Park, I. (2020). Why? J.")


def test_authors_html_lists_everyone_with_ampersand(build_one):
    [e] = build_one("@article{K, author = {A, B and C, D and E, F}, title = {T}, year = 2020}")
    assert e["authors_html"] == "A, B., C, D., &amp; E, F."


# --- copied BibTeX -----------------------------------------------------------

def test_bibtex_keeps_tex_and_abstract_drops_bookkeeping(build_one):
    [e] = build_one("@inproceedings{K, author = {S\\'agodi, \\'Abel}, title = {{H}ilbert\n\t spaces}, "
                    "year = 2026, month = dec, abstract = {We show $x$.}, owner = {me}, "
                    "timestamp = {2020}, tags = {}, selected = {false}}")
    assert e["bibtex"] == ("@inproceedings{K,\n"
                           "  author = {S\\'agodi, \\'Abel},\n"
                           "  title = {{H}ilbert spaces},\n"
                           "  year = 2026,\n"
                           "  month = dec,\n"
                           "  abstract = {We show $x$.},\n"
                           "}")

def test_apa_journal_article_number_and_in_press(build_one):
    assert _apa(build_one, "@article{K, author = {Brinkman, Braden A W}, title = {Metastable dynamics}, "
                           "journal = {Applied Physics Reviews}, year = 2022, volume = 9, number = 1, "
                           "pages = {011313}, doi = {10.1063/5.0062603}}") == (
        "Brinkman, B. A. W. (2022). Metastable dynamics. Applied Physics Reviews, 9(1), "
        "Article 011313. https://doi.org/10.1063/5.0062603")
    assert _apa(build_one, "@article{K, author = {Schaffer, Evan}, title = {Embodied Computation}, "
                           "journal = {The Journal of Neuroscience}, year = 2026, note = {In press}}") == (
        "Schaffer, E. (in press). Embodied Computation. The Journal of Neuroscience.")


def test_apa_journal_without_journal_field(build_one):
    [e] = build_one("@article{K, author = {Park, Il}, title = {T}, year = 2020}")
    assert e["apa_text"] == "Park, I. (2020). T."
    assert "<i></i>" not in e["apa_html"]


def test_apa_unpublished_masters_thesis(build_one):
    assert _apa(build_one, "@mastersthesis{K, author = {Arora, Tushar}, title = {Expressive power}, "
                           "school = {Stony Brook University}, year = 2023}") == (
        "Arora, T. (2023). Expressive power [Unpublished master's thesis]. Stony Brook University.")


def test_apa_conference_with_editors(build_one):
    assert _apa(build_one, "@inproceedings{K, author = {Park, Il}, title = {T}, booktitle = {Proc}, "
                           "editor = {Karim G. Oweiss and Jose Principe}, pages = {1--2}, year = 2010}") == (
        "Park, I. (2010). T. In K. G. Oweiss & J. Principe (Eds.), Proc (pp. 1\u20132).")


def test_apa_presentation_location_and_day(build_one):
    assert _apa(build_one, "@inproceedings{K, author = {Park, Il}, title = {T}, booktitle = {ECRO}, "
                           "address = {Lisbon, Portugal}, year = 2018, month = sep, day = {12}, "
                           "pubtype = {abstract}}") == (
        "Park, I. (2018, September 12). T [Conference abstract]. ECRO, Lisbon, Portugal.")


def test_bad_editor_list_is_bib_error(bp, build_one):
    with pytest.raises(bp.BibError, match="cannot parse names"):
        build_one("@inbook{K, title = {T}, booktitle = {B}, editor = {A Bee and C Dee,}, year = 2010}")


# --- fix round 1: APA edge cases ---------------------------------------------

def test_unknown_archive_prefix_is_bib_error(bp, build_one):
    with pytest.raises(bp.BibError, match="archivePrefix"):
        build_one("@unpublished{K, author = {Park, Il}, title = {T}, year = 2020, "
                  "eprint = {1}, archivePrefix = {medRxiv}}")


def test_apa_html_escapes_everything_but_italics(build_one):
    [e] = build_one(r'@inbook{K, author = {Park, Il}, title = {A <b> \& "q"}, '
                    r'booktitle = {B <i> \& C}, editor = {Ed <x>, Al}, '
                    r'publisher = {P \& "Q"}, year = 2010}')
    out = e["apa_html"]
    assert "<b>" not in out and "<x>" not in out and "<i> &" not in out
    assert "&lt;b&gt; &amp; &quot;q&quot;" in out
    assert "<i>B &lt;i&gt; &amp; C</i>" in out
    assert "Ed &lt;x&gt;" in out and "P &amp; &quot;Q&quot;" in out
    assert set(re.findall(r"</?\w+>", out)) == {"<i>", "</i>"}


def test_apa_conference_and_chapter_without_booktitle(build_one):
    [e] = build_one("@inproceedings{K, author = {Park, Il}, title = {T}, year = 2020}")
    assert e["apa_text"] == "Park, I. (2020). T." and "<i></i>" not in e["apa_html"]
    [e] = build_one("@inbook{K, author = {Park, Il}, title = {T}, publisher = {P}, year = 2020}")
    assert e["apa_text"] == "Park, I. (2020). T. P." and "<i></i>" not in e["apa_html"]


def test_apa_presentation_location_field_and_bad_day(build_one):
    base = ("@misc{K, author = {Park, Il}, title = {T}, howpublished = {V}, year = 2018, "
            "month = sep, pubtype = {abstract}, ")
    assert _apa(build_one, base + "location = {Lisbon}}") == (
        "Park, I. (2018, September). T [Conference abstract]. V, Lisbon.")
    assert _apa(build_one, base + "day = {12th}}") == "Park, I. (2018, September). T [Conference abstract]. V."
    assert _apa(build_one, base + "day = {32}}") == "Park, I. (2018, September). T [Conference abstract]. V."


def test_apa_abstract_month_without_year(build_one):
    assert _apa(build_one, "@misc{K, author = {Park, Il}, title = {T}, howpublished = {V}, "
                           "month = feb, pubtype = {abstract}}") == (
        "Park, I. (n.d.). T [Conference abstract]. V.")


def test_apa_abstract_venue_falls_back_to_journal(build_one):
    assert _apa(build_one, "@misc{K, author = {Park, Il}, title = {T}, journal = {Meeting}, "
                           "year = 2018, pubtype = {abstract}}") == (
        "Park, I. (2018). T [Conference abstract]. Meeting.")


def test_apa_published_thesis_with_school(build_one):
    assert _apa(build_one, "@phdthesis{K, author = {Park, Il}, title = {T}, school = {SBU}, "
                           "publisher = {Repo}, year = 2023, url = {http://x.org/a}}") == (
        "Park, I. (2023). T [Doctoral dissertation, SBU]. Repo. http://x.org/a")


def test_apa_doi_is_unescaped_like_the_link(build_one):
    [e] = build_one(r"@article{K, author = {Park, Il}, title = {T}, journal = {J}, year = 2020, "
                    r"doi = {10.1000/a\_b}}")
    assert e["apa_text"].endswith("https://doi.org/10.1000/a_b")
    assert e["links"][0]["url"] == "https://doi.org/10.1000/a_b"


def test_apa_single_hyphen_ranges_get_en_dash(build_one):
    assert _apa(build_one, "@article{K, author = {Park, Il}, title = {T}, journal = {J}, "
                           "year = 2020, pages = {10-20}}") == "Park, I. (2020). T. J, 10\u201320."
    assert _apa(build_one, "@inbook{K, author = {Park, Il}, title = {T}, booktitle = {B}, "
                           "year = 2020, pages = {10-20}}") == "Park, I. (2020). T. In B (pp. 10\u201320)."


def test_apa_patent_without_number(build_one):
    assert _apa(build_one, "@misc{K, author = {Park, Il}, title = {System?}, year = 2025, "
                           "pubtype = {patent}}") == (
        "Park, I. (2025). System? U.S. Patent and Trademark Office.")


def test_apa_editor_suffix_and_blank_editor(build_one):
    assert _apa(build_one, "@inbook{K, author = {Park, Il}, title = {T}, booktitle = {B}, "
                           "editor = {Smith, Jr., John}, year = 2020}") == (
        "Park, I. (2020). T. In J. Smith Jr. (Ed.), B.")
    assert _apa(build_one, "@inbook{K, author = {Park, Il}, title = {T}, booktitle = {B}, "
                           "editor = {  }, year = 2020}") == "Park, I. (2020). T. In B."


def test_apa_journal_issue_without_volume(build_one):
    assert _apa(build_one, "@article{K, author = {Park, Il}, title = {T}, journal = {J}, "
                           "number = {1}, pages = {1--2}, year = 2020}") == "Park, I. (2020). T. J(1), 1\u20132."


def test_bibtex_drops_underscore_fields(build_one):
    [e] = build_one("@article{K, title = {T}, _publisher = {X}, _pages = {1}, year = 2020}")
    assert e["bibtex"] == "@article{K,\n  title = {T},\n  year = 2020,\n}"


# --- labels -------------------------------------------------------------------

LABELS = """\
themes:
  - {id: language, name: Improving our language for neural computation}
facets:
  - id: research
    name: Research topic
    tags:
      - {id: continuous-attractors, name: Continuous attractors}
  - id: method
    name: Method
    tags:
      - {id: kernel-methods, name: Kernel methods}
"""


def test_labels_and_selected(build_one):
    [e] = build_one("@article{K, title = {T}, themes = {language}, "
                    "tags = {continuous-attractors; kernel-methods}, selected = {true}}", labels=LABELS)
    assert e["themes"] == ["language"]
    assert e["tags"] == ["continuous-attractors", "kernel-methods"]
    assert e["labels"] == [
        {"group": "theme", "id": "language", "name": "Improving our language for neural computation"},
        {"group": "research", "id": "continuous-attractors", "name": "Continuous attractors"},
        {"group": "method", "id": "kernel-methods", "name": "Kernel methods"}]
    assert e["selected"] is True


def test_unknown_tag_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="unknown tag"):
        build_one("@article{K, title = {T}, tags = {kernel-method}}", labels=LABELS)


def test_unknown_theme_is_error(bp, build_one):
    with pytest.raises(bp.BibError, match="unknown theme"):
        build_one("@article{K, title = {T}, themes = {langauge}}", labels=LABELS)


def test_selected_must_be_boolean(bp, build_one):
    with pytest.raises(bp.BibError, match="selected"):
        build_one("@article{K, title = {T}, selected = {yes}}")


def test_label_id_defined_twice_is_error(bp, build_one):
    twice = LABELS + "  - id: area\n    name: Area\n    tags:\n      - {id: kernel-methods, name: X}\n"
    with pytest.raises(bp.BibError, match="defined twice"):
        build_one("@article{K, title = {T}}", labels=twice)


def test_label_ids_must_be_kebab_case(bp, build_one):
    bad = LABELS.replace("kernel-methods", 'kernel" onfocus="x')
    with pytest.raises(bp.BibError, match="kebab-case"):
        build_one("@article{K, title = {T}}", labels=bad)


def test_no_labels_file_means_no_labels(build_one):
    [e] = build_one("@article{K, title = {T}}")
    assert (e["themes"], e["tags"], e["labels"], e["selected"]) == ([], [], [], False)


def test_bare_ampersand_is_kept(bp):
    assert bp.tex_to_text("Theory & Practice") == "Theory & Practice"
    assert bp.tex_to_html("Theory & Practice") == "Theory &amp; Practice"
    assert bp.tex_to_text(r"Theory \& Practice") == "Theory & Practice"


# --- roster -------------------------------------------------------------------

ROSTER = [
    {"name": "\u00c1bel S\u00e1godi", "family": "S\u00e1godi", "given": "\u00c1bel", "aliases": []},
    {"name": "Piotr A. Sok\u00f3\u0142", "family": "Sok\u00f3\u0142", "given": "Piotr A.", "aliases": []},
    {"name": "Il Memming Park", "family": "Park", "given": "Il Memming", "aliases": []},
    {"name": "A. Carolina Filipe", "family": "Filipe", "given": "A. Carolina", "aliases": []},
    {"name": "Yuan Zhao", "family": "Zhao", "given": "Yuan",
     "aliases": [{"family": "Zhao", "given": "Y"}]},
]


def test_member_marking(build_one):
    [e] = build_one("@article{K, author = {Sagodi, Abel and Sokol, Piotr and Park, Il and "
                    "Park, Jane and Zhao, Y.}, title = {T}, year = 2020}", roster=ROSTER)
    assert [a["member"] for a in e["authors"]] == [True, True, True, False, True]
    assert e["authors_html"].startswith('<strong class="member">Sagodi, A.</strong>, ')


@pytest.mark.parametrize("author, member", [
    ("Park, Il Memming", True), ("Park, I. Memming", True), ("Park, Memming", True),
    ("Park, Il", True), ("Park, Mijung", False), ("Park, Jong C.", False),
    ("Filipe, Carolina", True), ("Filipe, A. Carolina", True), ("Sokol, Piotr Aleksander", True),
    ("Liang, Justine", False),
])
def test_member_name_variants(build_one, author, member):
    [e] = build_one("@article{K, author = {" + author + "}, title = {T}, year = 2020}", roster=ROSTER)
    assert e["authors"][0]["member"] is member


def test_fold(bp):
    assert bp.fold("Sok\u00f3\u0142") == "sokol"
    assert bp.fold("S\u00c1GODI") == "sagodi"


# --- ordering, CLI, determinism -----------------------------------------------

def test_sort_order(build_one):
    entries = build_one("@article{A, title = {T}, year = 2020, month = mar}\n"
                        "@article{B, title = {T}, year = 2021}\n"
                        "@article{C, title = {T}, year = 2021, month = may}\n"
                        "@article{D, title = {T}}\n"
                        "@article{E, title = {T}, year = 2021, month = may}\n")
    assert [e["key"] for e in entries] == ["C", "E", "B", "A", "D"]


BIB_TWO = "@article{K1, title = {One}, year = 2020}\n@article{K2, title = {Two}, year = 2021}\n"


def test_main_writes_deterministic_json(bp, tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text(BIB_TWO, encoding="utf-8")
    out = tmp_path / "out.json"
    args = ["--bib", str(bib), "--labels", str(tmp_path / "none.yml"),
            "--roster", str(tmp_path / "none.json"), "--out", str(out)]
    assert bp.main(args) == 0
    first = out.read_bytes()
    assert bp.main(args) == 0
    assert out.read_bytes() == first
    assert first.endswith(b"\n")


def test_entry_order_in_bib_does_not_matter(bp, tmp_path):
    a = tmp_path / "a.bib"
    b = tmp_path / "b.bib"
    a.write_text(BIB_TWO, encoding="utf-8")
    b.write_text("\n".join(reversed(BIB_TWO.strip().split("\n"))) + "\n", encoding="utf-8")
    none = str(tmp_path / "none")
    assert bp.build(str(a), none, none) == bp.build(str(b), none, none)


def test_main_leaves_output_untouched_on_error(bp, tmp_path):
    bib = tmp_path / "x.bib"
    bib.write_text("@article{K1, title = {a {b}, year = 2020}\n", encoding="utf-8")
    out = tmp_path / "out.json"
    out.write_text("OLD", encoding="utf-8")
    none = str(tmp_path / "none")
    assert bp.main(["--bib", str(bib), "--labels", none, "--roster", none, "--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "OLD"


def test_dedupe_keeps_fragment_distinct_urls(build_one):
    assert _links(build_one, "url = {https://example.org/page#paper}, url2 = {https://example.org/page#data}") == [
        ("Link", "https://example.org/page#paper"), ("Link", "https://example.org/page#data")]


def test_refereed_field_overrides_kind_default(build_one):
    [a] = build_one("@inproceedings{K, author = {A, B}, title = {T}, year = 2020, "
                    "pubtype = {abstract}, refereed = {True}}")
    [c] = build_one("@inproceedings{K, author = {A, B}, title = {T}, year = 2020, refereed = {false}}")
    assert a["kind"] == "abstract" and a["refereed"] is True
    assert c["kind"] == "conference" and c["refereed"] is False


def test_bad_refereed_is_bib_error(bp, build_one):
    with pytest.raises(bp.BibError, match="K: refereed"):
        build_one("@article{K, author = {A, B}, title = {T}, year = 2020, refereed = {yes}}")


def test_refereed_not_in_copied_bibtex(build_one):
    [e] = build_one("@article{K, author = {A, B}, title = {T}, year = 2020, refereed = {true}}")
    assert "refereed" not in e["bibtex"]


# --- arXiv-only entries are preprints ----------------------------------------

def test_arxiv_article_is_unrefereed_preprint_with_arxiv_venue(build_one):
    [e] = build_one("@article{K, title = {T}, journal = {arXiv preprint arXiv:2101.00001}, "
                    "eprint = {2101.00001}, year = 2021}")
    assert (e["kind"], e["refereed"], e["venue_html"]) == ("preprint", False, "arXiv:2101.00001")


@pytest.mark.parametrize("bib, kind", [
    ("@article{K, title = {T}, journal = {ArXiv e-prints}, year = 2020}", "preprint"),
    ("@article{K, title = {T}, journal = {bioRxiv}, year = 2020}", "preprint"),
    ("@article{K, title = {T}, journal = {Preprint}, year = 2020}", "preprint"),
    ("@misc{K, title = {T}, eprint = {2001.00001}, year = 2020}", "preprint"),
    ("@article{K, title = {T}, journal = {Neuron}, year = 2020}", "journal"),
    ("@misc{K, title = {T}, year = 2020}", "other"),
])
def test_preprint_kind_detection(build_one, bib, kind):
    [e] = build_one(bib)
    assert e["kind"] == kind
    assert e["refereed"] is (kind == "journal")


def test_patent_venue_normalizes_number_like_apa(build_one):
    [e] = build_one("@misc{K, title = {T}, journal = {USPTO}, number = {20250209344:A1}, "
                    "year = 2025, pubtype = {patent}}")
    assert e["venue_html"] == "USPTO, 20250209344 A1"


# --- missing pdf files -------------------------------------------------------

def test_missing_pdf_file_warns(bp, build_one, tmp_path, monkeypatch, capsys):
    (tmp_path / "there.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(bp, "PUBLICATIONS_DIR", str(tmp_path))
    build_one("@article{K, title = {T}, pdf = {there.pdf}, year = 2020}")
    assert capsys.readouterr().err == ""
    build_one("@article{K, title = {T}, pdf = {gone.pdf}, year = 2020}")
    assert "gone.pdf" in capsys.readouterr().err


def test_textasciicircum_decodes_to_caret(bp):
    assert bp.tex_to_text(r"x\textasciicircum{}2") == "x^2"
    assert bp.tex_to_html(r"x\textasciicircum{}2") == "x^2"
