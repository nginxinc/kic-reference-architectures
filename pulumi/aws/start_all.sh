#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

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

header "AWS VPC"
cd "${script_dir}/vpc"
pulumi --emoji up --yes

header "AWS EKS"
cd "${script_dir}/eks"
pulumi --emoji up --yes

# pulumi stack output cluster_name
add_kube_config

header "AWS ECR"
cd "${script_dir}/ecr"
pulumi --emoji up --yes

header "KIC Image Build"
cd "${script_dir}/kic-image-build"
pulumi --emoji up --yes

header "KIC Image Push"
cd "${script_dir}/kic-image-push"
pulumi --emoji up --yes

header "Deploying KIC"
cd "${script_dir}/kic-helm-chart"
pulumi --emoji up --yes

header "Logstore"
cd "${script_dir}/logstore"
pulumi --emoji up --yes

header "Logagent"
cd "${script_dir}/logagent"
pulumi --emoji up --yes

header "Demo App"
cd "${script_dir}/demo-app"
pulumi --emoji up --yes
