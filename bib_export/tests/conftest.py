"""Shared fixtures: load build_publications.py as a module and build small bibs."""
import importlib.util
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "build_publications.py")


def _load():
    spec = importlib.util.spec_from_file_location("build_publications", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def bp():
    return _load()


@pytest.fixture
def build_one(bp, tmp_path):
    """Write a bib (and optional labels YAML / roster list) and run build()."""
    def run(bib, labels=None, roster=None):
        bib_path = tmp_path / "x.bib"
        bib_path.write_text(bib, encoding="utf-8")
        labels_path = tmp_path / "labels.yml"
        roster_path = tmp_path / "roster.json"
        if labels is not None:
            labels_path.write_text(labels, encoding="utf-8")
        if roster is not None:
            roster_path.write_text(json.dumps(roster), encoding="utf-8")
        return bp.build(str(bib_path), str(labels_path), str(roster_path))
    return run
