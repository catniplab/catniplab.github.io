#!/bin/sh
# Regenerate _data/publications.json from catniplab.bib (Jekyll renders
# /publications.html from it). Extra arguments go to the generator.
exec uv run --script "$(dirname "$0")/build_publications.py" "$@"
