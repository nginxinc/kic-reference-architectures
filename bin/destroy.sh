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
  fi
fi

if ! command -v pulumi >/dev/null; then
  echo >&2 "Pulumi must be installed to continue"
  exit 1
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
echo "Notice! This shell script will read the config/environment file to determine which pulumi stack to destroy."
echo "Based on the type of stack it will either run the ./bin/destroy_kube.sh or the ./bin/destroy_aws.sh script."
echo "If this is not what you want to do, please abort the script by typing ctrl-c and running the appropriate "
echo "script manually."
echo " "

# Sleep so we are seen...
sleep 5

source "${script_dir}/../config/pulumi/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"

#
# Determine what destroy script we need to run
#
if pulumi config get kubernetes:infra_type -C ${script_dir}/../pulumi/python/config>/dev/null 2>&1; then
  INFRA="$(pulumi config get kubernetes:infra_type -C ${script_dir}/../pulumi/python/infrastructure/aws/vpc)"
  if [ $INFRA == 'AWS' ]; then
    echo "Destroying an AWS based stack; if this is not right please type ctrl-c to abort this script."
    sleep 5
    ${script_dir}/destroy_aws.sh
    exit 0
  elif [ $INFRA == 'kubeconfig' ]; then
    echo "Destroying a kubeconfig based stack; if this is not right please type ctrl-c to abort this script."
    sleep 5
    ${script_dir}/destroy_kube.sh
    exit 0
  else
    print "No infrastructure set in config file; aborting!"
    exit 1
  fi
else
  print "No infrastructure set in config file; aborting!"
  exit 2
fi
