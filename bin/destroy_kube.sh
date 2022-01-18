#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# Don't pollute console output with upgrade notifications
export PULUMI_SKIP_UPDATE_CHECK=true
# Run Pulumi non-interactively
export PULUMI_SKIP_CONFIRMATIONS=true

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"

if ! command -v pulumi > /dev/null; then
  if [ -x "${script_dir}/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/venv/bin:$PATH"

    if ! command -v pulumi > /dev/null; then
      echo >&2 "Pulumi must be installed to continue"
      exit 1
    fi
  else
    echo >&2 "Pulumi must be installed to continue"
    exit 1
  fi
fi

if ! command -v python3 > /dev/null; then
  echo >&2 "Python 3 must be installed to continue"
  exit 1
fi

if ! command -v node > /dev/null; then
  if [ -x "${script_dir}/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/venv/bin:$PATH"

    if ! command -v node > /dev/null; then
      echo >&2 "NodeJS must be installed to continue"
      exit 1
    fi
  else
    echo >&2 "NodeJS must be installed to continue"
    exit 1
  fi
fi

# Check to see if the user is logged into Pulumi
if ! pulumi whoami --non-interactive > /dev/null 2>&1; then
  pulumi login

  if ! pulumi whoami --non-interactive > /dev/null 2>&1; then
    echo >&2 "Unable to login to Pulumi - exiting"
    exit 2
  fi
fi

source "${script_dir}/../config/pulumi/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"


APPLICATIONS=(sirius)
KUBERNETES=(observability logagent logstore certmgr prometheus)
NGINX=(kubernetes/nginx/ingress-controller)

#
# This is a temporary process until we complete the directory reorg and move the start/stop
# process into more solid code.
#

# Destroy the application(s)
for project_dir in "${APPLICATIONS[@]}" ; do
  echo "$project_dir"
  if [ -f "${script_dir}/../pulumi/python/kubernetes/applications/${project_dir}/Pulumi.yaml" ]; then
    pulumi_args="--cwd ${script_dir}/../pulumi/python/kubernetes/applications/${project_dir} --emoji --stack ${PULUMI_STACK}"
    pulumi ${pulumi_args} destroy
  else
    >&2 echo "Not destroying - Pulumi.yaml not found in directory: ${script_dir}/../pulumi/python/kubernetes/applications/${project_dir}"
  fi
done

# Destroy other K8 resources
for project_dir in "${KUBERNETES[@]}" ; do
  echo "$project_dir"
  if [ -f "${script_dir}/../pulumi/python/kubernetes/${project_dir}/Pulumi.yaml" ]; then
    pulumi_args="--cwd ${script_dir}/../pulumi/python/kubernetes/${project_dir} --emoji --stack ${PULUMI_STACK}"
    pulumi ${pulumi_args} destroy
  else
    >&2 echo "Not destroying - Pulumi.yaml not found in directory: ${script_dir}/../pulumi/python/kubernetes/${project_dir}"
  fi
done

# Destroy NGINX components
for project_dir in "${NGINX[@]}" ; do
  echo "$project_dir"
  if [ -f "${script_dir}/../pulumi/python/${project_dir}/Pulumi.yaml" ]; then
    pulumi_args="--cwd ${script_dir}/../pulumi/python/${project_dir} --emoji --stack ${PULUMI_STACK}"
    pulumi ${pulumi_args} destroy
  else
    >&2 echo "Not destroying - Pulumi.yaml not found in directory: ${script_dir}/../pulumi/python/${project_dir}"
  fi
done

# Clean up the kubeconfig project
for project_dir in "kubeconfig" ; do
  echo "$project_dir"
  if [ -f "${script_dir}/../pulumi/python/infrastructure/${project_dir}/Pulumi.yaml" ]; then
    pulumi_args="--cwd ${script_dir}/../pulumi/python/infrastructure/${project_dir} --emoji --stack ${PULUMI_STACK}"
    pulumi ${pulumi_args} destroy
  else
    >&2 echo "Not destroying - Pulumi.yaml not found in directory: ${script_dir}/../pulumi/python/infrastructure/${project_dir}"
  fi
done




