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

# Use the latest version of pip
pip3 install --upgrade pip

# Installs wheel package management, so that pulumi requirements install quickly
pip3 install wheel

# Get nodeenv version so that node can be installed before we install Python
# dependencies because pulumi_eks depends on the presence of node.
pip3 install "$(grep nodeenv requirements.txt)"

# Install node.js into virtual environment so that it can be used by Python
# modules that make call outs to it.
nodeenv -p --node=lts

# Install general package requirements
pip3 install --requirement "${script_dir}/requirements.txt"
# Install local common utilities module
pip3 install --use-feature=in-tree-build "${script_dir}/kic-pulumi-utils" && \
  rm -rf "${script_dir}/kic-pulumi-utils/.eggs" \
         "${script_dir}/kic-pulumi-utils/build" \
         "${script_dir}/kic-pulumi-utils/kic_pulumi_utils.egg-info"