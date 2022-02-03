#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

DEFAULT_UID=1000
DEFAULT_GID=1000

# CentOS already has a Group Id (GID) assigned of 999, so we use 996 the GID that gets
# auto-assigned when you install docker onto a fresh CentOS install.
if [ "${1}" == "centos" ]; then
  DEFAULT_DOCKER_GID=996
# Otherwise, we use 999 the GID that gets auto-assigned when you install
# docker onto a fresh Debian install.
else
  DEFAULT_DOCKER_GID=999
fi

# Choose a docker GID based on the owner of the Docker socket or the existing Docker group.
if [ -S "/var/run/docker.sock" ]; then
  DOCKER_GID="$(stat --printf="%g" /var/run/docker.sock 2>/dev/null || echo ${DEFAULT_DOCKER_GID})"
elif command -v getent >/dev/null; then
  DOCKER_GID="$(getent group docker | cut --delimiter=: --field=3)"
else
  DOCKER_GID=$DEFAULT_DOCKER_GID
fi

# If we chose a GID that conflicts with a known gid on CentOS, we use the default
# instead.
if [ "${1}" == "centos" ]; then
  if [[ $DOCKER_GID -gt 996 ]] && [[ $DOCKER_GID -lt 1000 ]]; then
    DOCKER_GID=$DEFAULT_DOCKER_GID
  fi
fi

# If we have the id command, then we use it to get the current user's uid and gid.
# This helps when we mount directories into a Docker image. It isn't strictly
# necessary, but it removes a headache when using the image in a development
# workflow.
if command -v id >/dev/null; then
  CURRENT_USER_UID="$(id -u || echo ${DEFAULT_UID})"
  CURRENT_USER_GID="${CURRENT_USER_UID}"

  # Reject superuser UIDs
  if [ "$CURRENT_USER_UID" -eq 0 ]; then
    DOCKER_USER_UID=$DEFAULT_UID
  else
    DOCKER_USER_UID=$CURRENT_USER_UID
  fi

  # Reject superuser GIDs
  if [ "$CURRENT_USER_GID" -eq 0 ]; then
    DOCKER_USER_GID=$DEFAULT_GID
  else
    DOCKER_USER_GID=$CURRENT_USER_GID
  fi
# If we don't have an id command, we just use the defaults.
else
  DOCKER_USER_UID=$DEFAULT_UID
  DOCKER_USER_GID=$DEFAULT_GID
fi

# Attempt to build the container with the same architecture as the host.
ARCH=""
case $(uname -m) in
i386) ARCH="386" ;;
i686) ARCH="386" ;;
x86_64) ARCH="amd64" ;;
aarch64) ARCH="arm64v8" ;;
arm) dpkg --print-architecture | grep -q "arm64" && ARCH="arm64v8" || ARCH="arm" ;;
*)
  echo >&2 "Unable to determine system architecture."
  exit 1
  ;;
esac
echo "Building container image with [${ARCH}] system architecture]"

# Squash our image if we are running in experimental mode
if [ "$(docker version -f '{{.Server.Experimental}}')" == 'true' ]; then
  echo "Enabling squash mode for container image"
  additional_docker_opts="--squash"
else
  additional_docker_opts=""
fi

echo "User id for [runner] user in container ${DOCKER_USER_UID}"
echo "Group id for [runner] group in container ${DOCKER_USER_GID}"
echo "Group id for [docker] group in container ${DOCKER_GID}"

docker build ${additional_docker_opts} \
  --build-arg ARCH="${ARCH}" \
  --build-arg UID="${DOCKER_USER_UID}" \
  --build-arg GID="${DOCKER_USER_GID}" \
  --build-arg DOCKER_GID="${DOCKER_GID}" \
  -t "kic-ref-arch-pulumi-aws:${1}" \
  -f "${script_dir}/Dockerfile.${1}" \
  "${script_dir}/.."

# Run unit tests
docker run --interactive --tty --rm "kic-ref-arch-pulumi-aws:${1}" bin/test_runner.sh
