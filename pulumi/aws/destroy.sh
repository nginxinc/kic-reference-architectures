#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# Don't pollute console output with upgrade notifications
export PULUMI_SKIP_UPDATE_CHECK=true
# Run Pulumi non-interactively
export PULUMI_SKIP_CONFIRMATIONS=true

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

if ! command -v pulumi >/dev/null; then
  if [ -x "${script_dir}/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/venv/bin:$PATH"

    if ! command -v pulumi >/dev/null; then
      echo >&2 "Pulumi must be installed to continue"
      exit 1
    fi
  else
    echo >&2 "Pulumi must be installed to continue"
    exit 1
  fi
fi

if ! command -v python3 >/dev/null; then
  echo >&2 "Python 3 must be installed to continue"
  exit 1
fi

if ! command -v node >/dev/null; then
  if [ -x "${script_dir}/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/venv/bin:$PATH"

    if ! command -v node >/dev/null; then
      echo >&2 "NodeJS must be installed to continue"
      exit 1
    fi
  else
    echo >&2 "NodeJS must be installed to continue"
    exit 1
  fi
fi

# Check to see if the user is logged into Pulumi
if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
  pulumi login

  if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
    echo >&2 "Unable to login to Pulumi - exiting"
    exit 2
  fi
fi

source "${script_dir}/config/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"

pulumi_args="--emoji --stack ${PULUMI_STACK}"

cd "${script_dir}/sirius"
pulumi ${pulumi_args} destroy

cd "${script_dir}/grafana"
pulumi ${pulumi_args} destroy

cd "${script_dir}/prometheus"
pulumi ${pulumi_args} destroy

cd "${script_dir}/certmgr"
pulumi ${pulumi_args} destroy

cd "${script_dir}/logagent"
pulumi ${pulumi_args} destroy

cd "${script_dir}/logstore"
pulumi ${pulumi_args} destroy

cd "${script_dir}/kic-helm-chart"
pulumi ${pulumi_args} destroy

cd "${script_dir}/kic-image-push"
pulumi ${pulumi_args} destroy

cd "${script_dir}/kic-image-build"
pulumi ${pulumi_args} destroy

cd "${script_dir}/ecr"
pulumi ${pulumi_args} destroy

cd "${script_dir}/eks"
pulumi ${pulumi_args} destroy

cd "${script_dir}/vpc"
pulumi ${pulumi_args} destroy
