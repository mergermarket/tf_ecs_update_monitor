#!/bin/sh

set -e

for version in 2 3; do
    echo testing with python $version >&2

    echo -n building docker image for test... >&2
    dockerfile=Dockerfile.test-$version
    cat Dockerfile.test.in | sed s/PYTHON_VERSION/$version/ > $dockerfile
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
done
