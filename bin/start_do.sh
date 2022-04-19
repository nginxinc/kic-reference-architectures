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

if [[ -z "${DIGITALOCEAN_TOKEN+x}" ]]; then
  echo "DIGITALOCEAN_TOKEN not set"
  if ! grep --quiet '^DIGITALOCEAN_TOKEN=.*' "${script_dir}/../config/pulumi/environment"; then
    read -r -e -p "Enter the Digital Ocean Token to use in all projects (leave blank for default): " DIGITALOCEAN_TOKEN
    if [[ -z "${DIGITALOCEAN_TOKEN}" ]]; then
      echo "No Digital Ocean token found - exiting"
      exit 4
    fi
    echo "DIGITALOCEAN_TOKEN=${DIGITALOCEAN_TOKEN}" >>"${script_dir}/../config/pulumi/environment"
    source "${script_dir}/../config/pulumi/environment"
    find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi config set --plaintext digitalocean:token "${DIGITALOCEAN_TOKEN}" \;
  fi
else
  echo "Using DIGITALOCEAN_TOKEN from environment: ${DIGITALOCEAN_TOKEN}"
  find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi config set --plaintext digitalocean:token "${DIGITALOCEAN_TOKEN}" \;
fi

# Function to auto-generate passwords
function createpw() {
  base64 /dev/random | tr -dc '[:alnum:]' | head -c${1:-16}
  return 0
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
  echo "Password found for the sirius accounts database"
else
  ACCOUNTS_PW=$(createpw)
  pulumi config set --secret sirius:accounts_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius $ACCOUNTS_PW
  echo "Created password for the sirius accounts database"
fi

# Sirius Ledger Database
if pulumi config get sirius:ledger_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius >/dev/null 2>&1; then
  echo "Password found for sirius ledger database"
else
  LEDGER_PW=$(createpw)
  pulumi config set --secret sirius:accounts_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius $LEDGER_PW
  echo "Created password for the sirius ledger database"
fi

# Admin password for grafana (see note in __main__.py in prometheus project as to why not encrypted)
# This is for the deployment that is setup as part of the the prometheus operator driven prometheus-kube-stack.
#
if pulumi config get prometheus:adminpass -C ${script_dir}/../pulumi/python/config >/dev/null 2>&1; then
  echo "Password found for grafana admin account"
else
  echo "Create a password for the grafana admin user"
  pulumi config set prometheus:adminpass -C ${script_dir}/../pulumi/python/config
fi
# TODO: Figure out better way to handle hostname / ip address for exposing our IC #82
#
# This version of the code forces you to add a hostname which is used to generate the cert when the application is
# deployed, and will output the IP address and the hostname that will need to be set in order to use the self-signed
# cert and to access the application.
#

echo " "
echo "NOTICE! Currently we do not automatically pull the hostname of the K8 LoadBalancer with this deployment; instead"
echo "you will need to create a FQDN and map the assigned IP address to your FQDN in order to use the deployment. "
echo "You can then add this mapping to DNS, or locally to your host file"
echo " "
echo "See https://networkdynamics.com/2017/05/the-benefits-of-testing-your-website-with-a-local-hosts-file/ for details"
echo "on how this can be accomplished. "
echo " "
echo "This will be streamlined in a future release of MARA."
echo " "

# So we can see...
sleep 5

if pulumi config get kic-helm:fqdn -C ${script_dir}/../pulumi/python/config >/dev/null 2>&1; then
  echo "Hostname found for deployment"
else
  echo "Create a fqdn for your deployment"
  pulumi config set kic-helm:fqdn -C ${script_dir}/../pulumi/python/config
fi
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
  echo "adding ${cluster_name} cluster to local kubeconfig"
  doctl kubernetes cluster config save ${cluster_name}
}

function validate_do_credentials() {
  pulumi_do_token="$(pulumi --cwd "${script_dir}/../pulumi/python/config" config get digitalocean:token)"
  echo "Validating Digital Ocean credentials"
  if ! doctl account get >/dev/null; then
    echo >&2 "Digital Ocean credentials have expired or are not valid"
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

#
# This deploy only works with the NGINX registries.
#
echo " "
echo "NOTICE! Currently the deployment for Digital Ocean only supports pulling images from the registry! A JWT is "
echo "required in order to access the NGINX Plus repository. This should be placed in a file in the extras directory"
echo "in the project root, in a file named jwt.token"
echo " "
echo "See https://docs.nginx.com/nginx-ingress-controller/installation/using-the-jwt-token-docker-secret/ for more "
echo "details and examples."
echo " "

# Make sure we see it
sleep 5

#
# TODO: Integrate this into the mainline along with logic to work with/without #80
#
# This logic takes the JWT and transforms it into a secret so we can pull the NGINX Plus IC. If the user is not
# deploying plus (and does not have a JWT) we create a placeholder credential that is used to create a secert. That
# secret is not a valid secret, but it is created to make the logic easier to read/code.
#
if [[ -s "${script_dir}/../extras/jwt.token" ]]; then
  JWT=$(cat ${script_dir}/../extras/jwt.token)
  echo "Loading JWT into nginx-ingress/regcred"
  ${script_dir}/../pulumi/python/venv/bin/kubectl create secret docker-registry regcred --docker-server=private-registry.nginx.com --docker-username=${JWT} --docker-password=none -n nginx-ingress --dry-run=client -o yaml >${script_dir}/../pulumi/python/kubernetes/nginx/ingress-controller-repo-only/manifests/regcred.yaml
else
  # TODO: need to adjust so we can deploy from an unauthenticated registry (IC OSS) #81
  echo "No JWT found; writing placeholder manifest"
  ${script_dir}/../pulumi/python/venv/bin/kubectl create secret docker-registry regcred --docker-server=private-registry.nginx.com --docker-username=placeholder --docker-password=placeholder -n nginx-ingress --dry-run=client -o yaml >${script_dir}/../pulumi/python/kubernetes/nginx/ingress-controller-repo-only/manifests/regcred.yaml
fi

if command -v doctl >/dev/null; then
  validate_do_credentials
fi

#
# Set the headers to respect the NO_COLOR variable
#
if [ -z ${NO_COLOR+x} ]; then
  pulumi_args="--emoji --stack ${PULUMI_STACK}"
else
  pulumi_args="--color never --stack ${PULUMI_STACK}"
fi

# We automatically set this to DO for infra type; since this is a script specific to DO
# TODO: combined file should query and manage this
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/config DO
# Bit of a gotcha; we need to know what infra type we have when deploying our application (BoS) due to the
# way we determine the load balancer FQDN or IP. We can't read the normal config since Sirius uses it's own
# configuration because of the encryption needed for the passwords.
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius DO

header "DO Kubernetes"
cd "${script_dir}/../pulumi/python/infrastructure/digitalocean/domk8s"
pulumi $pulumi_args up

# pulumi stack output cluster_name
cluster_name=$(pulumi stack output cluster_id -s "${PULUMI_STACK}" -C ${script_dir}/../pulumi/python/infrastructure/digitalocean/domk8s)
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

header "Deploying IC"
cd "${script_dir}/../pulumi/python/kubernetes/nginx/ingress-controller-repo-only"
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

# We currently don't run this becuase in most cases we are going to need to create either a DNS entry or a hostfile
# mapping for our application.
# TODO: find a more elegant solution to LB IP / hostname combos for testing the app #82
# Bind this to something for now
app_url=" "
#app_url="$(pulumi stack output --json | python3 "${script_dir}"/../pulumi/python/kubernetes/applications/sirius/verify.py)"

header "Finished!"
echo "Application can now be accessed at: ${app_url}"
