#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o pipefail  # don't hide errors within pipes

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if ! command -v python3 > /dev/null; then
  >&2 echo "Python 3 must be installed to continue"
  exit 1
fi

if [ ! -d "${script_dir}/venv" ]; then
  echo "Creating new virtual environment: ${script_dir}/venv"
  python3 -m venv "${script_dir}/venv"
fi

source "${script_dir}/venv/bin/activate"

set -o nounset   # abort on unbound variable

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

ARCH=""
case $(uname -m) in
    i386)    ARCH="386" ;;
    i686)    ARCH="386" ;;
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    arm)     dpkg --print-architecture | grep -q "arm64" && ARCH="arm64" || ARCH="arm" ;;
    *)   >&2 echo "Unable to determine system architecture."; exit 1 ;;
esac
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"

if command -v wget > /dev/null; then
  download_cmd="wget --quiet --max-redirect=12 --output-document -"
elif command -v curl > /dev/null; then
  download_cmd="curl --silent --location"
else
  >&2 echo "either wget or curl must be installed"
  exit 1
fi

# Add local kubectl if a version is not in the path
if ! command -v kubectl > /dev/null; then
  echo "Downloading kubectl into virtual environment"
  KUBECTL_VERSION="$(${download_cmd} https://dl.k8s.io/release/stable.txt)"
  ${download_cmd} "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl" > "${script_dir}/venv/bin/kubectl"
  KUBECTL_CHECKSUM="$(${download_cmd} "https://dl.k8s.io/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl.sha256")"
  echo "${KUBECTL_CHECKSUM}  ${script_dir}/venv/bin/kubectl" | sha256sum --check
  chmod +x "${script_dir}/venv/bin/kubectl"
fi