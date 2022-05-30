# install docker
# docker pull jekyll/jekyll
# export JEKYLL_VERSION=3.8.4 # via https://pages.github.com/versions.json (most recent not in official docker image atm)
# check versions here: https://hub.docker.com/r/jekyll/jekyll/tags
# docker run --rm --volume="$PWD:/srv/jekyll:Z" --volume="$PWD/vendor/bundle:/usr/local/bundle:Z" -it jekyll/jekyll:$JEKYLL_VERSION bundle update
docker run --rm --volume="$PWD:/srv/jekyll:Z" --volume="$PWD/vendor/bundle:/usr/local/bundle:Z" -p 4000:4000 jekyll/jekyll:$JEKYLL_VERSION jekyll serve
