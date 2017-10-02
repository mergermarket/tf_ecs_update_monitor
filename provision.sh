#!/bin/sh

set -e

if [ "$#" != "6" ]; then
    echo 'Usage: provision.sh <module-root> <cluster> <service> <taskdef> <region> <caller-arn>' >&2
    exit 1
fi

cd "$1"

python -m ecs_update_monitor --cluster    "$2" \
                             --service    "$3" \
                             --taskdef    "$4" \
                             --region     "$5" \
                             --caller-arn "$6"
