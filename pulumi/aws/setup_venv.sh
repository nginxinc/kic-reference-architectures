#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o pipefail  # don't hide errors within pipes

# Function below is based upon code in this StackOverflow post:
# https://stackoverflow.com/a/31939275/33611
# CC BY-SA 3.0 License: https://creativecommons.org/licenses/by-sa/3.0/
function askYesNo {
        QUESTION=$1
        DEFAULT=$2
        if [ "$DEFAULT" = true ]; then
                OPTIONS="[Y/n]"
                DEFAULT="y"
            else
                OPTIONS="[y/N]"
                DEFAULT="n"
        fi
        if [ "${DEBIAN_FRONTEND}" != "noninteractive" ]; then
          read -p "$QUESTION $OPTIONS " -n 1 -s -r INPUT
          INPUT=${INPUT:-${DEFAULT}}
          echo "${INPUT}"
        fi

        if [ "${DEBIAN_FRONTEND}" == "noninteractive" ]; then
            ANSWER=$DEFAULT
        elif [[ "$INPUT" =~ ^[yY]$ ]]; then
            ANSWER=true
        else
            ANSWER=false
        fi
}

# Function below is based upon code in this StackOverflow post:
# https://stackoverflow.com/a/18443300/33611
# CC BY-SA 3.0 License: https://creativecommons.org/licenses/by-sa/3.0/
realpath() (
  OURPWD=$PWD
  cd "$(dirname "$1")"
  LINK=$(readlink "$(basename "$1")")
  while [ "$LINK" ]; do
    cd "$(dirname "$LINK")"
    LINK=$(readlink "$(basename "$1")")
  done
  REALPATH="$PWD/$(basename "$1")"
  cd "$OURPWD"
  echo "$REALPATH"
)

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if ! command -v git > /dev/null; then
   >&2 echo "git must be installed to continue"
  exit 1
fi

if ! command -v python3 > /dev/null; then
  echo "Python 3 is not installed. Adding pyenv to allow for Python installation"
  export PYENV_ROOT="${script_dir}/.pyenv"
  mkdir -p "${PYENV_ROOT}"
  git clone --depth 1 --branch v2.0.3 https://github.com/pyenv/pyenv.git "${PYENV_ROOT}" 2> "${script_dir}/pyenv_git_clone.log" \
    && rm "${script_dir}/pyenv_git_clone.log" # remove log if clone worked
  export PATH="$PYENV_ROOT/bin:$PATH"
fi

# If pyenv is available we use a hardcoded python version
if command -v pyenv > /dev/null; then
  eval "$(pyenv init --path)"
  eval "$(pyenv init -)"
  pyenv install --skip-existing < "${script_dir}/.python-version"

  # If the pyenv-virtualenv tools are installed, prompt the user if they want to
  # use them.
  if [ -d "${PYENV_ROOT}/plugins/pyenv-virtualenv" ]; then
    askYesNo "Use pyenv-virtualenv to manage virtual environment?" true
    if [ $ANSWER = true ]; then
      has_pyenv_venv_plugin=1
    else
      has_pyenv_venv_plugin=0
    fi
  else
    has_pyenv_venv_plugin=0
  fi
else
  has_pyenv_venv_plugin=0
fi

# if pyenv with virtual-env plugin is installed, use that
if [ ${has_pyenv_venv_plugin} -eq 1 ]; then
  eval "$(pyenv virtualenv-init -)"

  if ! pyenv virtualenvs --bare | grep --quiet '^ref-arch-pulumi-aws'; then
    pyenv virtualenv ref-arch-pulumi-aws
  fi

  if [ -z "${VIRTUAL_ENV}" ]; then
    pyenv activate ref-arch-pulumi-aws
  fi

  if [ -h "${script_dir}/venv" ]; then
    echo "Link already exists [${script_dir}/venv] - removing and relinking"
    rm "${script_dir}/venv"
  elif [ -d "${script_dir}/venv" ]; then
    echo "Virtual environment directory already exists"
    askYesNo "Delete and replace with pyenv-virtualenv managed link?" false
    if [ $ANSWER = true ]; then
      echo "Deleting ${script_dir}/venv"
      rm -rf "${script_dir}/venv"
    else
      >&2 echo "The path ${script_dir}/venv must not be a virtual environment directory when using pyenv-virtualenv"
      >&2 echo "Exiting. Please manually remove the directory"
      exit 1
    fi
  fi

  echo "Linking virtual environment [${VIRTUAL_ENV}] to local directory [venv]"
  ln -s "${VIRTUAL_ENV}" "${script_dir}/venv"
fi

# If pyenv isn't present do everything with default python tooling
if [ ${has_pyenv_venv_plugin} -eq 0 ]; then
  if [ -z "${VIRTUAL_ENV}" ]; then
    VIRTUAL_ENV="${script_dir}/venv"
    echo "No virtual environment already specified, defaulting to: ${VIRTUAL_ENV}"
  fi

  if [ ! -d "${VIRTUAL_ENV}" ]; then
    echo "Creating new virtual environment: ${VIRTUAL_ENV}"
    python3 -m venv "${VIRTUAL_ENV}"
  fi

  source "${VIRTUAL_ENV}/bin/activate"
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
  echo "${KUBECTL_CHECKSUM}  ${VIRTUAL_ENV}/bin/kubectl" | shasum --algorithm 256 --check
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