#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes

# Don't pollute console output with upgrade notifications
export PULUMI_SKIP_UPDATE_CHECK=true
# Run Pulumi non-interactively
export PULUMI_SKIP_CONFIRMATIONS=true

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if ! command -v pulumi > /dev/null; then
  if [ -x "${script_dir}/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/venv/bin:$PATH"

    if ! command -v pulumi > /dev/null; then
      >&2 echo "Pulumi must be installed to continue"
      exit 1
    fi
  else
    >&2 echo "Pulumi must be installed to continue"
    exit 1
  fi
fi

if ! command -v python3 > /dev/null; then
  >&2 echo "Python 3 must be installed to continue"
  exit 1
fi

if ! command -v node > /dev/null; then
  if [ -x "${script_dir}/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
    export PATH="${script_dir}/venv/bin:$PATH"

    if ! command -v node > /dev/null; then
      >&2 echo "NodeJS must be installed to continue"
      exit 1
    fi
  else
    >&2 echo "NodeJS must be installed to continue"
    exit 1
  fi
fi

if ! command -v git > /dev/null; then
  >&2 echo "git must be installed to continue"
  exit 1
fi

if ! command -v make > /dev/null; then
  >&2 echo "make is not installed - it must be installed if you intend to build NGINX Kubernetes Ingress Controller from source."
fi

if ! command -v docker > /dev/null; then
  >&2 echo "docker is not installed - it must be installed if you intend to build NGINX Kubernetes Ingress Controller from source."
fi

# Check to see if the user is logged into Pulumi
if ! pulumi whoami --non-interactive > /dev/null 2>&1; then
  pulumi login

  if ! pulumi whoami --non-interactive > /dev/null 2>&1; then
    >&2 echo "Unable to login to Pulumi - exiting"
    exit 2
  fi
fi

if [ ! -f "${script_dir}/config/environment" ]; then
  touch "${script_dir}/config/environment"
fi

if ! grep --quiet '^PULUMI_STACK=.*' "${script_dir}/config/environment"; then
  read -r -e -p "Enter the name of the Pulumi stack to use in all projects: " PULUMI_STACK
  echo "PULUMI_STACK=${PULUMI_STACK}" >> "${script_dir}/config/environment"
fi

source "${script_dir}/config/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"

# Create the stack if it does not already exist
find "${script_dir}" -mindepth 2 -maxdepth 2 -type f -name Pulumi.yaml -execdir pulumi stack select --create "${PULUMI_STACK}" \;

if [[ -z "${AWS_PROFILE+x}" ]] ; then
  echo "AWS_PROFILE not set"
  if ! grep --quiet '^AWS_PROFILE=.*' "${script_dir}/config/environment"; then
    read -r -e -p "Enter the name of the AWS Profile to use in all projects (leave blank for default): " AWS_PROFILE
      if [[ -z "${AWS_PROFILE}" ]] ; then
        AWS_PROFILE=default
      fi
    echo "AWS_PROFILE=${AWS_PROFILE}" >> "${script_dir}/config/environment"
    source "${script_dir}/config/environment"
    find "${script_dir}" -mindepth 2 -maxdepth 2 -type f -name Pulumi.yaml -execdir pulumi config set aws:profile "${AWS_PROFILE}" \;
  fi
else
  echo "Using AWS_PROFILE from environment: ${AWS_PROFILE}"
fi

# Check for default region in environment; set if not found

# First, check the config file for our current profile. If there
# is no AWS command we assume that there is no config file, which
# may not always be a valid assumption.
if "${script_dir}"/venv/bin/aws configure get region --profile ${AWS_PROFILE}  > /dev/null ; then
  AWS_DEFAULT_REGION=$("${script_dir}"/venv/bin/aws configure get region --profile ${AWS_PROFILE})
  echo $AWS_DEFAULT_REGION
fi

if [[ -z "${AWS_DEFAULT_REGION+x}" ]] ; then
  echo "AWS_DEFAULT_REGION not set"
  if ! grep --quiet '^AWS_DEFAULT_REGION=.*' "${script_dir}/config/environment"; then
    read -r -e -p "Enter the name of the AWS Region to use in all projects: " AWS_DEFAULT_REGION
    echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}" >> "${script_dir}/config/environment"
    source "${script_dir}/config/environment"
    find "${script_dir}" -mindepth 2 -maxdepth 2 -type f -name Pulumi.yaml -execdir pulumi config set aws:region "${AWS_DEFAULT_REGION}" \;
  fi
else
  echo "Using AWS_DEFAULT_REGION from environment/config: ${AWS_DEFAULT_REGION}"
  pulumi config set aws:region -C "${script_dir}/vpc" "${AWS_DEFAULT_REGION}"
fi

# The bank of anthos configuration file is stored in the ./anthos/config
# directory. This is because we cannot pull secrets from different project
# directories.
#
# This work-around is expected to be obsoleted by the work described in
# https://github.com/pulumi/pulumi/issues/4604, specifically around issue
# https://github.com/pulumi/pulumi/issues/2307
#
# Check for secrets being set
#
echo "Checking for required secrets"

# Anthos Accounts Database
if pulumi config get anthos:accounts_pwd -C ${script_dir}/anthos > /dev/null 2>&1; then
  echo "Password found for the anthos accounts database"
else
  echo "Create a password for the anthos accounts database"
  pulumi config set --secret anthos:accounts_pwd -C ${script_dir}/anthos
fi

# Anthos Ledger Database
if pulumi config get anthos:ledger_pwd -C ${script_dir}/anthos > /dev/null 2>&1; then
  echo "Password found for anthos ledger database"
else
  echo "Create a password for the anthos ledger database"
  pulumi config set --secret anthos:ledger_pwd -C ${script_dir}/anthos
fi

# Show colorful fun headers if the right utils are installed
function header() {
  "${script_dir}"/venv/bin/fart --no_copy -f standard "$1" | "${script_dir}"/venv/bin/lolcat
}

function add_kube_config() {
    pulumi_region="$(pulumi config get aws:region)"
    if [ "${pulumi_region}" != "" ]; then
      region_arg="--region ${pulumi_region}"
    else
      region_arg=""
    fi
    pulumi_aws_profile="$(pulumi config get aws:profile)"
    if [ "${pulumi_aws_profile}" != "" ]; then
      echo "Using AWS profile [${pulumi_aws_profile}] from Pulumi configuration"
      profile_arg="--profile ${pulumi_aws_profile}"
    elif [[ -n "${AWS_PROFILE+x}" ]] ; then
      echo "Using AWS profile [${AWS_PROFILE}] from environment"
      profile_arg="--profile ${AWS_PROFILE}"
    else
      profile_arg=""
    fi

    cluster_name="$(pulumi stack output cluster_name)"

    echo "adding ${cluster_name} cluster to local kubeconfig"
    "${script_dir}"/venv/bin/aws ${profile_arg} ${region_arg} eks update-kubeconfig --name ${cluster_name}
}

pulumi_args="--emoji --stack ${PULUMI_STACK}"

header "AWS VPC"
cd "${script_dir}/vpc"
pulumi $pulumi_args up

header "AWS EKS"
cd "${script_dir}/eks"
pulumi $pulumi_args up

# pulumi stack output cluster_name
add_kube_config

header "AWS ECR"
cd "${script_dir}/ecr"
pulumi $pulumi_args up

header "KIC Image Build"
cd "${script_dir}/kic-image-build"
pulumi $pulumi_args up

header "KIC Image Push"
# If we are on MacOS and the user keychain is locked, we need to prompt the
# user to unlock it so that `docker login` will work correctly.
if command -v security > /dev/null && [[ "$(uname -s)" == "Darwin" ]]; then
  if ! security show-keychain-info 2> /dev/null; then
    echo "Enter in your system credentials in order to access the system keychain for storing secrets securely with Docker."
    security unlock-keychain
  fi
fi
cd "${script_dir}/kic-image-push"
pulumi $pulumi_args up

header "Deploying KIC"
cd "${script_dir}/kic-helm-chart"
pulumi $pulumi_args up

header "Logstore"
cd "${script_dir}/logstore"
pulumi $pulumi_args up

header "Logagent"
cd "${script_dir}/logagent"
pulumi $pulumi_args up

header "Cert Manager"
cd "${script_dir}/certmgr"
pulumi $pulumi_args up

header "Prometheus"
cd "${script_dir}/prometheus"
pulumi $pulumi_args up

header "Grafana"
cd "${script_dir}/grafana"
pulumi $pulumi_args up

header "Bank of Anthos"
cd "${script_dir}/anthos"
pulumi $pulumi_args up
app_url="$(pulumi stack output --json | python3 "${script_dir}"/anthos/verify.py)"

header "Finished!"
echo "Application can now be accessed at: ${app_url}"