#!/bin/sh
# Build the site with GitHub Pages' production gem set in Docker.
# Usage: build_site.sh [DATA_DIR]
#   Copies the working tree to $WORK/site_src (never builds inside the repo),
#   copies every file in DATA_DIR over $WORK/site_src/_data/ when given, and
#   writes the built site to $WORK/site_out.
set -eu
SITE=$(cd "$(dirname "$0")/../.." && pwd)
WORK=${PUBS_SCRATCH:-$HOME/scratch/projects/catniplab-pubs}
SRC=$WORK/site_src
OUT=$WORK/site_out
GEMS=$WORK/gems
mkdir -p "$SRC" "$OUT" "$GEMS"
rsync -a --delete --exclude .git --exclude _site "$SITE"/ "$SRC"/
if [ $# -ge 1 ]; then
  for f in "$1"/*.json "$1"/*.yml; do
    if [ -f "$f" ]; then cp "$f" "$SRC/_data/"; fi
  done
fi
docker run --rm \
  -v "$SRC":/srv/site -v "$OUT":/srv/out -v "$GEMS":/usr/local/bundle \
  -e BUNDLE_GEMFILE=/srv/site/bib_export/tests/Gemfile.pages \
  -w /srv/site ruby:3.3 \
  sh -c 'bundle install --quiet && bundle exec jekyll build --quiet -s /srv/site -d /srv/out'
echo "built site in $OUT"
