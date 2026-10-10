import importlib.util
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sf", os.path.join(HERE, "..", "set_fields.py"))
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)

BIB = [
    "@Article{A,\n", "  title = {T},\n", "  year  = 2020\n", "}\n",
    "\n",
    "@Article{B,\n", "  abstract = {line one\n", "    line two},\n", "  year = 2021,\n", "}\n",
]


def test_insert_adds_comma_to_previous_field():
    lines = list(BIB)
    sf.set_field(lines, "A", "tags", "kernel-methods")
    assert lines[2:5] == ["  year  = 2020,\n", "  tags = {kernel-methods},\n", "}\n"]


def test_replace_single_line_field():
    lines = list(BIB)
    sf.set_field(lines, "A", "title", "New")
    assert lines[1] == "  title = {New},\n"


def test_refuse_to_replace_multiline_field():
    with pytest.raises(SystemExit, match="spans lines"):
        sf.set_field(list(BIB), "B", "abstract", "x")


def test_unknown_key():
    with pytest.raises(SystemExit, match="no entry"):
        sf.set_field(list(BIB), "Z", "tags", "x")


def test_latex_escape_text():
    assert sf.latex_escape_text("50% & #1 a_b $5 {x} \\") == (
        r"50\% \& \#1 a\_b \$5 \{x\} \textbackslash{}")


def test_fake_field_line_inside_abstract_is_not_edited():
    lines = ["@Article{A,\n", "  abstract = {first\n", "  title = {fake},\n", "  end},\n",
             "  title = {Real},\n", "  year = 2020,\n", "}\n"]
    sf.set_field(lines, "A", "title", "New")
    assert lines[2] == "  title = {fake},\n"
    assert lines[4] == "  title = {New},\n"


def test_refuse_multiline_quoted_value():
    lines = ['@Article{A,\n', '  note = "one\n', '   two",\n', '  year = 2020,\n', '}\n']
    with pytest.raises(SystemExit, match="spans lines"):
        sf.set_field(lines, "A", "note", "x")


def _write(tmp_path, lines):
    bib = tmp_path / "t.bib"
    bib.write_text("".join(lines), encoding="utf-8")
    csv_path = tmp_path / "c.csv"
    return bib, csv_path


def test_main_replaces_once_and_leaves_no_tmp(tmp_path):
    bib, csv_path = _write(tmp_path, BIB)
    csv_path.write_text("key,field,value,format\nA,title,50% off,text\nA,tags,x,tex\n")
    assert sf.main([str(csv_path), "--bib", str(bib)]) == 0
    text = bib.read_text()
    assert "title = {50\\% off}," in text and "tags = {x}," in text
    assert sorted(os.listdir(tmp_path)) == ["c.csv", "t.bib"]


def test_main_failure_leaves_bib_untouched(tmp_path):
    bib, csv_path = _write(tmp_path, BIB)
    csv_path.write_text("key,field,value,format\nA,tags,a},tex\n")  # unbalanced brace
    before = bib.read_text()
    assert sf.main([str(csv_path), "--bib", str(bib)]) == 1
    assert bib.read_text() == before
    assert sorted(os.listdir(tmp_path)) == ["c.csv", "t.bib"]


def test_main_refusal_leaves_bib_untouched(tmp_path):
    bib, csv_path = _write(tmp_path, BIB)
    csv_path.write_text("key,field,value,format\nA,tags,x,tex\nB,abstract,y,tex\n")
    before = bib.read_text()
    with pytest.raises(SystemExit, match="spans lines"):
        sf.main([str(csv_path), "--bib", str(bib)])
    assert bib.read_text() == before
    assert sorted(os.listdir(tmp_path)) == ["c.csv", "t.bib"]


def test_main_calls_os_replace_exactly_once_on_success_and_never_on_failure(tmp_path, monkeypatch):
    calls = []
    real = os.replace
    monkeypatch.setattr(sf.os, "replace", lambda *a: (calls.append(a), real(*a))[1])
    bib, csv_path = _write(tmp_path, BIB)
    csv_path.write_text("key,field,value,format\nA,tags,x,tex\n")
    assert sf.main([str(csv_path), "--bib", str(bib)]) == 0
    assert len(calls) == 1 and calls[0][1] == str(bib)
    calls.clear()
    csv_path.write_text("key,field,value,format\nA,tags,a},tex\n")  # unbalanced brace
    assert sf.main([str(csv_path), "--bib", str(bib)]) == 1
    assert calls == []


def test_main_keeps_file_mode(tmp_path):
    bib, csv_path = _write(tmp_path, BIB)
    os.chmod(bib, 0o640)
    csv_path.write_text("key,field,value,format\nA,tags,x,tex\n")
    assert sf.main([str(csv_path), "--bib", str(bib)]) == 0
    assert os.stat(bib).st_mode & 0o777 == 0o640


def test_refuse_field_sharing_a_line():
    lines = ["@Article{A,\n", "  title = {T}, year = 2020,\n", "  pages = {1},\n", "}\n"]
    with pytest.raises(SystemExit, match="shares a line"):
        sf.set_field(lines, "A", "year", "2021")
    with pytest.raises(SystemExit, match="shares a line"):
        sf.set_field(lines, "A", "title", "N")
