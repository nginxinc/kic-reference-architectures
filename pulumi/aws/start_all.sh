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

if ! command -v aws > /dev/null; then
  echo "AWS CLI not installed; some functionality will not be available"
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
    read -r -e -p "Enter the name of the AWS Profile to use in all projects: " AWS_PROFILE
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
if command -v aws > /dev/null; then
  if aws configure get region --profile ${AWS_PROFILE}  > /dev/null ; then
    AWS_DEFAULT_REGION=$(aws configure get region --profile ${AWS_PROFILE})
    echo $AWS_DEFAULT_REGION
  fi
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


# Show colorful fun headers if the right utils are installed
function header() {
  if command -v colorscript > /dev/null; then
    colorscript --exec crunchbang-mini
  else
    echo "####################################"
  fi

  if command -v figlet > /dev/null; then
    if command -v lolcat > /dev/null; then
      figlet "$1" | lolcat
    else
      figlet "$1"
    fi
  else
    echo "▶ $1"
  fi
}

function add_kube_config() {
    if command -v aws > /dev/null; then
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
      aws ${profile_arg} ${region_arg} eks update-kubeconfig --name ${cluster_name}
    else
        echo "aws cli command not available on path - not writing cluster kubeconfig"
    fi
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

header "Bank of Anthos"
cd "${script_dir}/anthos"
pulumi $pulumi_args up
