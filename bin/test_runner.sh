#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o pipefail # don't hide errors within pipes

#source /pulumi/projects/kic-reference-architectures/pulumi/python/venv/bin/activate
source ./pulumi/python/venv/bin/activate
#/pulumi/projects/kic-reference-architectures/pulumi/python/venv/bin/python3 /pulumi/projects/kic-reference-architectures/bin/test.py
./pulumi/python/venv/bin/python3 ./bin/test.py
