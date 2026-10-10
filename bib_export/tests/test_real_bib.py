"""Checks on the real catniplab.bib and vocabulary."""
import json
import os
import random
import re

import pytest

SITE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIB = os.path.join(SITE, "bib_export", "catniplab.bib")
LABELS = os.path.join(SITE, "_data", "publication_labels.yml")
ROSTER = os.path.join(SITE, "_data", "lab_members.json")


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
    assert len(entries) == 173
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


@pytest.mark.skip(reason="labels not yet applied to the bib (Task 10 Step 5)")
def test_tags_are_applied(bp):
    entries = bp.build(BIB, LABELS, ROSTER)
    vocab_tags = {t for e in entries for t in e["tags"]}
    assert vocab_tags, "no tags applied"
