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
  if [ -x "${script_dir}/../pulumi/python/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/../pulumi/python/venv/bin] to PATH"
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

if ! command -v node >/dev/null; then
  if [ -x "${script_dir}/../pulumi/python/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/../pulumi/python/venv/bin] to PATH"
    export PATH="${script_dir}/../pulumi/python/venv/bin:$PATH"

    if ! command -v node >/dev/null; then
      echo >&2 "NodeJS must be installed to continue"
      exit 1
    fi
  else
    echo >&2 "NodeJS must be installed to continue"
    exit 1
  fi
fi

if ! command -v git >/dev/null; then
  echo >&2 "git must be installed to continue"
  exit 1
fi

if ! command -v make >/dev/null; then
  echo >&2 "make is not installed - it must be installed if you intend to build NGINX Kubernetes Ingress Controller from source."
fi

if ! command -v docker >/dev/null; then
  echo >&2 "docker is not installed - it must be installed if you intend to build NGINX Kubernetes Ingress Controller from source."
fi

# Check to see if the user is logged into Pulumi
if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
  pulumi login

  if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
    echo >&2 "Unable to login to Pulumi - exiting"
    exit 2
  fi
fi

if [ ! -f "${script_dir}/../config/pulumi/environment" ]; then
  touch "${script_dir}/../config/pulumi/environment"
fi

if ! grep --quiet '^PULUMI_STACK=.*' "${script_dir}/../config/pulumi/environment"; then
  read -r -e -p "Enter the name of the Pulumi stack to use in all projects: " PULUMI_STACK
  echo "PULUMI_STACK=${PULUMI_STACK}" >>"${script_dir}/../config/pulumi/environment"
fi

# Do we have the submodule source....
#
# Note: We had been checking for .git, but this is not guaranteed to be
# there if we build the docker image or use a tarball. So now we look
# for the src subdirectory which should always be there.
#
if [[ -d "${script_dir}/../pulumi/python/kubernetes/applications/sirius/src/src" ]]; then
  echo "Submodule source found"
else
  # Error out with instructions.
  echo "Bank of Sirius submodule not found"
  echo " "
  echo "Please run:"
  echo "    git submodule update --init --recursive --remote"
  echo "Inside your git directory and re-run this script"
  echo ""
  echo >&2 "Unable to find submodule - exiting"
  exit 3
fi

source "${script_dir}/../config/pulumi/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"

# Create the stack if it does not already exist
# We skip over the tools directory, because that uses a unique stack for setup of the
# kubernetes components for installations without them.
find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi stack select --create "${PULUMI_STACK}" \;

if [[ -z "${AWS_PROFILE+x}" ]]; then
  echo "AWS_PROFILE not set"
  if ! grep --quiet '^AWS_PROFILE=.*' "${script_dir}/../config/pulumi/environment"; then
    read -r -e -p "Enter the name of the AWS Profile to use in all projects (leave blank for default): " AWS_PROFILE
    if [[ -z "${AWS_PROFILE}" ]]; then
      AWS_PROFILE=default
    fi
    echo "AWS_PROFILE=${AWS_PROFILE}" >>"${script_dir}/../config/pulumi/environment"
    source "${script_dir}/../config/pulumi/environment"
    find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi config set aws:profile "${AWS_PROFILE}" \;
  fi
else
  echo "Using AWS_PROFILE from environment: ${AWS_PROFILE}"
fi

# Check for default region in environment; set if not found
# The region is set by checking the following in the order below:
# * AWS_DEFAULT_REGION environment variable
# * config/environment values of AWS_DEFAULT_REGION
# * prompt the user for a region

if [[ -z "${AWS_DEFAULT_REGION+x}" ]]; then
  echo "AWS_DEFAULT_REGION not set"
  if ! grep --quiet '^AWS_DEFAULT_REGION=.*' "${script_dir}/../config/pulumi/environment"; then
    # First, check the config file for our current profile. If there
    # is no AWS command we assume that there is no config file, which
    # may not always be a valid assumption.
    if ! command -v aws >/dev/null; then
      AWS_CLI_DEFAULT_REGION="us-east-1"
    elif aws configure get region --profile "${AWS_PROFILE}" >/dev/null; then
      AWS_CLI_DEFAULT_REGION="$(aws configure get region --profile "${AWS_PROFILE}")"
    else
      AWS_CLI_DEFAULT_REGION="us-east-1"
    fi

    read -r -e -p "Enter the name of the AWS Region to use in all projects [${AWS_CLI_DEFAULT_REGION}]: " AWS_DEFAULT_REGION
    echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-${AWS_CLI_DEFAULT_REGION}}" >>"${script_dir}/../config/pulumi/environment"
    source "${script_dir}/../config/pulumi/environment"
    find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi config set aws:region "${AWS_DEFAULT_REGION}" \;
  fi
else
  echo "Using AWS_DEFAULT_REGION from environment/config: ${AWS_DEFAULT_REGION}"
  pulumi config set aws:region -C "${script_dir}/../pulumi/python/config" "${AWS_DEFAULT_REGION}"
fi

function createpw() {
  PWORD=$(dd if=/dev/urandom count=1 2>/dev/null | base64 | head -c16)
  echo $PWORD
}

# The bank of sirius configuration file is stored in the ./sirius/config
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

# Sirius Accounts Database
if pulumi config get sirius:accounts_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius >/dev/null 2>&1; then
  true
else
  ACCOUNTS_PW=$(createpw)
  pulumi config set --secret sirius:accounts_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius $ACCOUNTS_PW
fi

# Sirius Ledger Database
if pulumi config get sirius:ledger_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius >/dev/null 2>&1; then
  true
else
  LEDGER_PW=$(createpw)
  pulumi config set --secret sirius:ledger_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius $LEDGER_PW
fi

# Admin password for grafana (see note in __main__.py in prometheus project as to why not encrypted)
# This is for the deployment that is setup as part of the the prometheus operator driven prometheus-kube-stack.
#
if pulumi config get prometheus:adminpass -C ${script_dir}/../pulumi/python/config >/dev/null 2>&1; then
  echo "Existing password found for grafana admin user"
else
  echo "Create a password for the grafana admin user; this password will be used to access the Grafana dashboard"
  echo "This should be an alphanumeric string without any shell special characters; it is presented in plain text"
  echo "due to current limitations with Pulumi secrets. You will need this password to access the Grafana dashboard."
  pulumi config set prometheus:adminpass -C ${script_dir}/../pulumi/python/config
fi

#
# Show colorful fun headers if the right utils are installed and NO_COLOR is not set
#
function header() {
  if [ -z ${NO_COLOR+x} ]; then
    "${script_dir}"/../pulumi/python/venv/bin/fart --no_copy -f standard "$1" | "${script_dir}"/../pulumi/python/venv/bin/lolcat
  else
    "${script_dir}"/../pulumi/python/venv/bin/fart --no_copy -f standard "$1"
  fi
}

function add_kube_config() {
  pulumi_region="$(pulumi ${pulumi_args} config get aws:region -C ${script_dir}/../pulumi/python/config)"
  if [ "${pulumi_region}" != "" ]; then
    region_arg="--region ${pulumi_region}"
  else
    region_arg=""
  fi
  pulumi_aws_profile="$(pulumi ${pulumi_args} config get aws:profile -C ${script_dir}/../pulumi/python/config)"
  if [ "${pulumi_aws_profile}" != "" ]; then
    echo "Using AWS profile [${pulumi_aws_profile}] from Pulumi configuration"
    profile_arg="--profile ${pulumi_aws_profile}"
  elif [[ -n "${AWS_PROFILE+x}" ]]; then
    echo "Using AWS profile [${AWS_PROFILE}] from environment"
    profile_arg="--profile ${AWS_PROFILE}"
  else
    profile_arg=""
  fi

  cluster_name="$(pulumi ${pulumi_args} stack output cluster_name -C ${script_dir}/../pulumi/python/infrastructure/aws/eks)"

  echo "adding ${cluster_name} cluster to local kubeconfig"
  "${script_dir}"/../pulumi/python/venv/bin/aws ${profile_arg} ${region_arg} eks update-kubeconfig --name ${cluster_name}
}

function validate_aws_credentials() {
  pulumi_aws_profile="$(pulumi --cwd "${script_dir}/../pulumi/python/config" config get aws:profile || true)"
  if [ "${pulumi_aws_profile}" != "" ]; then
    profile_arg="--profile ${pulumi_aws_profile}"
  elif [[ -n "${AWS_PROFILE+x}" ]]; then
    profile_arg="--profile ${AWS_PROFILE}"
  else
    profile_arg=""
  fi

  echo "Validating AWS credentials"
  if ! aws ${profile_arg} sts get-caller-identity >/dev/null; then
    echo >&2 "AWS credentials have expired or are not valid"
    exit 2
  fi
}

function retry() {
  local -r -i max_attempts="$1"
  shift
  local -i attempt_num=1
  until "$@"; do
    if ((attempt_num == max_attempts)); then
      echo "Attempt ${attempt_num} failed and there are no more attempts left!"
      return 1
    else
      echo "Attempt ${attempt_num} failed! Trying again in $attempt_num seconds..."
      sleep $((attempt_num++))
    fi
  done
}

if command -v aws >/dev/null; then
  validate_aws_credentials
fi

#
# Set the headers to respect the NO_COLOR variable
#
if [ -z ${NO_COLOR+x} ]; then
  pulumi_args="--emoji --stack ${PULUMI_STACK}"
else
  pulumi_args="--color never --stack ${PULUMI_STACK}"
fi

# We automatically set this to aws for infra type; since this is a script specific to AWS
# TODO: combined file should query and manage this
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/config AWS
# Bit of a gotcha; we need to know what infra type we have when deploying our application (BoS) due to the
# way we determine the load balancer FQDN or IP. We can't read the normal config since Sirius uses it's own
# configuration because of the encryption needed for the passwords.
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius AWS

header "Version Info"
echo "Version and Account Information"
echo "====================================================================="
echo "Pulumi version is: $(pulumi version)"
echo "Pulumi user is: $(pulumi whoami)"
echo "Python version is: $(python --version)"
echo "Kubectl version information: "
echo "$(kubectl version -o json)"
echo "Python module information: "
echo "$(pip list)"
echo "====================================================================="
echo " "

header "AWS VPC"
cd "${script_dir}/../pulumi/python/infrastructure/aws/vpc"
pulumi $pulumi_args up

header "AWS EKS"
cd "${script_dir}/../pulumi/python/infrastructure/aws/eks"
pulumi $pulumi_args up

# pulumi stack output cluster_name
add_kube_config

if command -v kubectl >/dev/null; then
  echo "Attempting to connect to newly create kubernetes cluster"
  retry 30 kubectl version >/dev/null
fi

#
# This is used to streamline the pieces that follow. Moving forward we can add new logic behind this and this
# should abstract away for us. This way we just call the kubeconfig project to get the needed information and
# let the infrastructure specific parts do their own thing (as long as they work with this module)
#
header "Kubeconfig"
cd "${script_dir}/../pulumi/python/infrastructure/kubeconfig"
pulumi $pulumi_args up

header "AWS ECR"
cd "${script_dir}/../pulumi/python/infrastructure/aws/ecr"
pulumi $pulumi_args up

header "IC Image Build"
cd "${script_dir}/../pulumi/python/utility/kic-image-build"
pulumi $pulumi_args up

header "IC Image Push"
# If we are on MacOS and the user keychain is locked, we need to prompt the
# user to unlock it so that `docker login` will work correctly.
if command -v security >/dev/null && [[ "$(uname -s)" == "Darwin" ]]; then
  if ! security show-keychain-info 2>/dev/null; then
    echo "Enter in your system credentials in order to access the system keychain for storing secrets securely with Docker."
    security unlock-keychain
  fi
fi
cd "${script_dir}/../pulumi/python/utility/kic-image-push"
pulumi $pulumi_args up

header "Deploying IC"
cd "${script_dir}/../pulumi/python/kubernetes/nginx/ingress-controller"
pulumi $pulumi_args up

header "Logstore"
cd "${script_dir}/../pulumi/python/kubernetes/logstore"
pulumi $pulumi_args up

header "Logagent"
cd "${script_dir}/../pulumi/python/kubernetes/logagent"
pulumi $pulumi_args up

header "Cert Manager"
cd "${script_dir}/../pulumi/python/kubernetes/certmgr"
pulumi $pulumi_args up

header "Prometheus"
cd "${script_dir}/../pulumi/python/kubernetes/prometheus"
pulumi $pulumi_args up

header "Observability"
cd "${script_dir}/../pulumi/python/kubernetes/observability"
pulumi $pulumi_args up

header "Bank of Sirius"
cd "${script_dir}/../pulumi/python/kubernetes/applications/sirius"

pulumi $pulumi_args up
app_url="$(pulumi ${pulumi_args} stack output --json | python3 "${script_dir}"/../pulumi/python/kubernetes/applications/sirius/verify.py)"

header "Finished!"
echo "The startup process has finished successfully"
echo " "
echo "Next Steps:"
echo " "
echo "1. The application can now be accessed at: ${app_url}."
echo "2. Use the ./bin/test-forward.sh program to establish tunnels you can use to connect to the management tools."
echo "3. Use kubectl, k9s, or the Kubernetes dashboard to explore your deployment."
echo " "
echo "To review your configuration options, including the passwords defined, you can access the pulumi secrets via the"
echo "following commands:"
echo " "
echo "Main Configuration: pulumi config -C ${script_dir}/../pulumi/python/config"
echo "Bank of Sirius (Example Application) Configuration: pulumi config -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius"
echo "K8 Loadbalancer IP: kubectl get services --namespace nginx-ingress"
echo " "
echo "Please see the documentation in the github repository for more information"
