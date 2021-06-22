#!/usr/bin/env bash

set -o errexit   # abort on nonzero exit status
set -o nounset   # abort on unbound variable
set -o pipefail  # don't hide errors within pipes

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd "${script_dir}/demo-app"
pulumi --emoji destroy --yes

cd "${script_dir}/logagent"
pulumi --emoji destroy --yes

cd "${script_dir}/logstore"
pulumi --emoji destroy --yes

cd "${script_dir}/kic-helm-chart"
pulumi --emoji destroy --yes

cd "${script_dir}/kic-image-push"
pulumi --emoji destroy --yes

cd "${script_dir}/kic-image-build"
pulumi --emoji destroy --yes

cd "${script_dir}/ecr"
pulumi --emoji destroy --yes

cd "${script_dir}/eks"
pulumi --emoji destroy --yes

cd "${script_dir}/vpc"
pulumi --emoji destroy --yes
