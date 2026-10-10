#!/bin/sh
# Run the generator's unit tests. Extra arguments go to pytest.
set -eu
cd "$(dirname "$0")"
exec uv run --no-project --with pytest --with 'bibtexparser>=2.1' \
  --with 'pylatexenc>=2.10' --with 'pyyaml>=6.0' \
  python -m pytest tests -q "$@"
