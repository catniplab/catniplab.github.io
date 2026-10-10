"""Checks on the real catniplab.bib and vocabulary."""
import json
import os
import random
import re

import yaml

SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIB = os.path.join(SITE, "bib_export", "catniplab.bib")
LABELS = os.path.join(SITE, "_data", "publication_labels.yml")
ROSTER = os.path.join(SITE, "_data", "lab_members.json")
_HEADER = re.compile(r"^\s*@(?!comment\b|string\b|preamble\b)\w+\s*[{(]", re.I | re.M)


def count_entry_headers():
    """Entry count taken from the bib text, so adding a paper keeps the suite green."""
    with open(BIB, encoding="utf-8") as fh:
        return len(_HEADER.findall(fh.read()))


def test_real_bib_builds_and_is_deterministic(bp):
    a = json.dumps(bp.build(BIB, LABELS, ROSTER), ensure_ascii=False)
    b = json.dumps(bp.build(BIB, LABELS, ROSTER), ensure_ascii=False)
    assert a == b


def test_shuffled_real_bib_gives_same_output(bp, tmp_path):
    text = open(BIB, encoding="utf-8").read()
    blocks = re.split(r"(?m)^(?=@)", text)
    head, entries = blocks[0], blocks[1:]
    random.Random(20261010).shuffle(entries)
    shuffled = tmp_path / "shuffled.bib"
    shuffled.write_text(head + "".join(e if e.endswith("\n") else e + "\n" for e in entries), encoding="utf-8")
    assert bp.build(str(shuffled), LABELS, ROSTER) == bp.build(BIB, LABELS, ROSTER)


def test_every_entry_has_a_kind_and_members_are_marked(bp):
    entries = bp.build(BIB, LABELS, ROSTER)
    assert len(entries) == count_entry_headers()
    assert all(e["kind"] for e in entries)
    assert any(a["member"] for e in entries for a in e["authors"])


def test_specific_roster_matches(bp):
    # display is 'Family, initials', so match on family + given words instead
    by_name = {}
    for e in bp.build(BIB, LABELS, ROSTER):
        for a in e["authors"]:
            by_name.setdefault((a["family"], a["given"]), set()).add(a["member"])
    for name in [("Park", "Il Memming"), ("Park", "Memming"), ("Park", "I. Memming"),
                 ("Filipe", "Carolina")]:
        assert by_name.get(name) == {True}, name
    for name in [("Park", "Mijung"), ("Park", "Jong C.")]:
        assert by_name.get(name) == {False}, name


def test_tags_match_vocabulary(bp):
    entries = bp.build(BIB, LABELS, ROSTER)
    with open(LABELS, encoding="utf-8") as fh:
        vocab = yaml.safe_load(fh)
    defined = {t["id"] for f in vocab["facets"] for t in f["tags"]}
    used = {t for e in entries for t in e["tags"]}
    assert used <= defined, f"tags not in vocabulary: {used - defined}"
    assert defined <= used, f"vocabulary tags used by no entry: {defined - used}"
