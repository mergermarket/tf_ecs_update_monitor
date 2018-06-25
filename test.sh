#!/bin/sh

set -e

echo testing with python 3 >&2

echo -n building docker image for test... >&2
dockerfile=Dockerfile.test
image=$(docker build -q -f $dockerfile .)
echo done. >&2

docker run \
    --rm \
    -i $(tty -s && echo -t) \
    $(tty -s && echo -v $(pwd)/.hypothesis/:/usr/src/app/.hypothesis/) \
    $image py.test \
        -n auto \
        --cov=. \
        --cov-report term-missing \
        --tb=short \
        "$@"

docker run --rm $image flake8 --max-complexity=4
