#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if ! command -v python3 > /dev/null; then
  >&2 echo "Python 3 must be installed to continue"
  exit 1
fi

if [ ! -d "${script_dir}/venv" ]; then
  python3 -m venv "${script_dir}/venv"
fi

source "${script_dir}/venv/bin/activate"

# Installs wheel package management, so that pulumi requirements install quickly
pip3 install wheel
# Install general package requirements
pip3 install -r "${script_dir}/requirements.txt"
# Install local common utilities module
pip3 install --use-feature=in-tree-build "${script_dir}/kic-pulumi-utils" && \
  rm -rf "${script_dir}/kic-pulumi-utils/.eggs" \
         "${script_dir}/kic-pulumi-utils/build" \
         "${script_dir}/kic-pulumi-utils/kic_pulumi_utils.egg-info"