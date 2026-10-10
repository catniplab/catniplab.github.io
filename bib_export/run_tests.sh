#!/bin/sh
# Run the generator's unit tests. Extra arguments go to pytest.
set -eu
cd "$(dirname "$0")"
exec uv run --no-project --with pytest --with 'bibtexparser==2.1.0' \
  --with 'pylatexenc>=2.10' --with 'pyyaml>=6.0' \
  python -B -m pytest tests -q -p no:cacheprovider -o python_files='test_*.py' "$@"
