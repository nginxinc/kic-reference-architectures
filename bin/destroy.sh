#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# Don't pollute console output with upgrade notifications
export PULUMI_SKIP_UPDATE_CHECK=true
# Run Pulumi non-interactively
export PULUMI_SKIP_CONFIRMATIONS=true
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

#
# Check to see if the venv has been installed, since this is only going to be
# used to start pulumi/python based projects.
#
if ! command -v "${script_dir}/../pulumi/python/venv/bin/python" >/dev/null; then
  echo "NOTICE! Unable to find the venv directory. This is required for the pulumi/python deployment process."
  echo "Please run ./setup_venv.sh from this directory to install the required virtual environment."
  echo " "
  exit 1
else
  echo "Adding to [${script_dir}/venv/bin] to PATH"
  export PATH="${script_dir}/../pulumi/python/venv/bin:$PATH"
fi

if ! command -v pulumi >/dev/null; then
  if [ -x "${script_dir}/../pulumi/python/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/../pulumi/python/venv/bin:$PATH"

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

# Check to see if the user is logged into Pulumi
if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
  pulumi login

  if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
    echo >&2 "Unable to login to Pulumi - exiting"
    exit 2
  fi
fi

echo " "
echo "Notice! This shell script will only destroy kubeconfig based deployments; if you have deployed to AWS, "
echo "DigitalOcean, or Linode you will need to use the ./pulumi/python/runner script instead."
echo " "

# Sleep so we are seen...
sleep 5

source "${script_dir}/../config/pulumi/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"

#
# Determine what destroy script we need to run
#
if pulumi config get kubernetes:infra_type -C "${script_dir}"/../pulumi/python/config >/dev/null 2>&1; then
  INFRA="$(pulumi config get kubernetes:infra_type -C ${script_dir}/../pulumi/python/config)"
  if [ "$INFRA" == 'AWS' ]; then
    echo "This script no longer works with AWS deployments; please use ./pulumi/python/runner instead"
    exec ${script_dir}/../pulumi/python/runner
    exit 0
  elif [ "$INFRA" == 'kubeconfig' ]; then
    echo "Destroying a kubeconfig based stack; if this is not right please type ctrl-c to abort this script."
    sleep 5
    "${script_dir}"/destroy_kube.sh
    exit 0
  elif [ "$INFRA" == 'DO' ]; then
    echo "This script no longer works with DigitalOcean deployments; please use ./pulumi/python/runner instead"
    exec "${script_dir}"/../pulumi/python/runner
    sleep 5
    "${script_dir}"/destroy_do.sh
    exit 0
  elif [ "$INFRA" == 'LKE' ]; then
    echo "This script no longer works with Linode deployments; please use ./pulumi/python/runner instead"
    exec "${script_dir}"/../pulumi/python/runner
    sleep 5
    "${script_dir}"/destroy_lke.sh
    exit 0
  else
    print "No infrastructure set in config file; aborting!"
    exit 1
  fi
else
  print "No infrastructure set in config file; aborting!"
  exit 2
fi
