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

header "Demo App"
cd "${script_dir}/demo-app"
pulumi $pulumi_args up
