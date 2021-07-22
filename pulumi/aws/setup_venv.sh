#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o pipefail  # don't hide errors within pipes

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if ! command -v python3 > /dev/null; then
  >&2 echo "Python 3 must be installed to continue"
  exit 1
fi

if [ -z "${VIRTUAL_ENV}" ]; then
  VIRTUAL_ENV="${script_dir}/venv"
  echo "No virtual environment already specified, defaulting to: ${VIRTUAL_ENV}"
fi

if [ ! -d "${VIRTUAL_ENV}" ]; then
  echo "Creating new virtual environment: ${VIRTUAL_ENV}"
  python3 -m venv "${VIRTUAL_ENV}"
fi

source "${VIRTUAL_ENV}/bin/activate"

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
if [ ! -x "${VIRTUAL_ENV}/bin/node" ]; then
  nodeenv -p --node=lts
else
  echo "Node.js version $("${VIRTUAL_ENV}/bin/node" --version) is already installed"
fi

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
  download_cmd="curl --fail --silent --location"
else
  >&2 echo "either wget or curl must be installed"
  exit 1
fi

# Add local kubectl to the virtual environment
if [ ! -x "${VIRTUAL_ENV}/bin/kubectl" ]; then
  echo "Downloading kubectl into virtual environment"
  KUBECTL_VERSION="$(${download_cmd} https://dl.k8s.io/release/stable.txt)"
  ${download_cmd} "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl" > "${VIRTUAL_ENV}/bin/kubectl"
  KUBECTL_CHECKSUM="$(${download_cmd} "https://dl.k8s.io/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl.sha256")"
  echo "${KUBECTL_CHECKSUM}  ${VIRTUAL_ENV}/bin/kubectl" | sha256sum --check
  chmod +x "${VIRTUAL_ENV}/bin/kubectl"
else
  echo "kubectl is already installed"
fi

# Add Pulumi to the virtual environment
echo "Downloading Pulumi CLI into virtual environment"
PULUMI_VERSION="$(grep '^pulumi~=.*$' "${script_dir}/requirements.txt" | cut -d '=' -f2)"

if [[ -x "${VIRTUAL_ENV}/bin/pulumi" ]] && [[ "$("${VIRTUAL_ENV}/bin/pulumi" version)" == "v${PULUMI_VERSION}" ]]; then
  echo "Pulumi version ${PULUMI_VERSION} is already installed"
else
  PULUMI_TARBALL_URL="https://get.pulumi.com/releases/sdk/pulumi-v${PULUMI_VERSION}-${OS}-${ARCH/amd64/x64}.tar.gz"
  PULUMI_TARBALL_DESTTARBALL_DEST=$(mktemp -t pulumi.tar.gz.XXXXXXXXXX)
  ${download_cmd} "${PULUMI_TARBALL_URL}" > "${PULUMI_TARBALL_DESTTARBALL_DEST}"
  tar --extract --gunzip --directory "${VIRTUAL_ENV}/bin" --strip-components 1 --file "${PULUMI_TARBALL_DESTTARBALL_DEST}"
  rm "${PULUMI_TARBALL_DESTTARBALL_DEST}"
fi