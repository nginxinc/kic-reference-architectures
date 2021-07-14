#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if command -v getent > /dev/null; then
  DOCKER_GID="$(getent group docker | cut --delimiter=: --field=3)"
else
  DOCKER_GID=999
fi

if command -v id > /dev/null; then
  DOCKER_USER_UID="$(id --user)"
  DOCKER_USER_GID="$(id --group)"
else
  DOCKER_USER_UID=1000
  DOCKER_USER_GID=1000
fi

docker build \
  --build-arg UID="${DOCKER_USER_UID}" \
  --build-arg GID="${DOCKER_USER_GID}" \
  --build-arg DOCKER_GID="${DOCKER_GID}" \
  -t kic-ref-arch-pulumi-aws \
  -f "${script_dir}/Dockerfile" \
  "${script_dir}"