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
  >&2 echo "Pulumi must be installed to continue"
  exit 1
fi

if ! command -v python3 > /dev/null; then
  >&2 echo "Python 3 must be installed to continue"
  exit 1
fi

if ! command -v node > /dev/null; then
  >&2 echo "NodeJS must be installed to continue"
  exit 1
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
fi

# If it does not already exist we will create the configuration file for the 
# bank of anthos application.
# 
# This is done by merging the main config file with the configuration 
# file from the main config.
#
# This is a work-around, as we are using a common configuration file for
# the project but secrets are encrypted at the stack/project level.
#
# The logic is
# 1. If a configuration file of the format ./config/Pulumi.stackname.yaml
#    exists in the Anthos directory we just check for the secrets.
# 2. If the file does not exist, we create a file by merging the contents
#    of the top level config file (Pulumi.stackname.yaml) with the template
#    file in the Anthos directory (./config/Pulumi.stackname.yaml.example)
#    to create ./config/Pulumi.stackname.yaml.
# 
# To fully recreate the file (including re-adding the passwords) you can 
# remove the ./config/Pulumi.stackname.yaml file and re-run this script.
#
# This work-around is expected to be obsoleted by the work described in 
# https://github.com/pulumi/pulumi/issues/4604, specifically around issue
# https://github.com/pulumi/pulumi/issues/2307
#
if [ ! -f "${script_dir}/anthos/config/Pulumi.${PULUMI_STACK}.yaml" ]; then
    echo "Merging master config with Bank of Anthos config"
    ${script_dir}/venv/bin/yamlreader ${script_dir}/config/Pulumi.${PULUMI_STACK}.yaml ${script_dir}/anthos/config/Pulumi.stackname.yaml.example  > \
    ${script_dir}/anthos/config/Pulumi.${PULUMI_STACK}.yaml
else
    echo "Bank of Anthos config exists"
fi

# Check for secrets being set
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

# Demo Account
if pulumi config get anthos:demo_pwd -C ${script_dir}/anthos > /dev/null 2>&1; then
  echo "Password found for anthos demo account"
else
  echo "Create a password for the anthos demo application; you will need this to log in"
  pulumi config set --secret anthos:demo_pwd -C ${script_dir}/anthos
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
      profile_arg="--profile ${pulumi_aws_profile}"
    else
      profile_arg=""
    fi

    cluster_name="$(pulumi stack output cluster_name)"

    echo "adding ${cluster_name} cluster to local kubeconfig"
    "${script_dir}"/venv/bin/aws ${profile_arg} ${region_arg} eks update-kubeconfig --name ${cluster_name}
}

pulumi_args="--emoji"

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

header "Bank of Anthos"
cd "${script_dir}/anthos"
pulumi $pulumi_args up
