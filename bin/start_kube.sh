#!/usr/bin/env bash

# Remove...JAS
set -o verbose
set -o xtrace

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
# Do not change the tools directory of add-ons.
find "${script_dir}/../pulumi" -mindepth 2 -maxdepth 6 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi stack select --create "${PULUMI_STACK}" \;

# Show colorful fun headers if the right utils are installed and NO_COLOR is not set
#
function header() {
  if [ -z ${NO_COLOR+x} ]; then
    "${script_dir}"/../pulumi/python/venv/bin/fart --no_copy -f standard "$1" | "${script_dir}"/../pulumi/python/venv/bin/lolcat
  else
    "${script_dir}"/../pulumi/python/venv/bin/fart --no_copy -f standard "$1"
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

function createpw() {
    PASSWORD=$(base64 /dev/random|head -c${1:-16} | tr -dc  '[:alnum:]')
    echo $PASSWORD
}

#
# This deploy only works with the NGINX registries.
#
echo " "
echo "NOTICE! Currently the deployment via kubeconfig only supports pulling images from the registry! A JWT is "
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

# Check for stack info....
# TODO: Move these to use kubeconfig for the Pulumi main config (which redirects up) instead of aws/vpc #80
#

# We automatically set this to a kubeconfig type for infra type
# TODO: combined file should query and manage this #80
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/config kubeconfig
# Bit of a gotcha; we need to know what infra type we have when deploying our application (BoS) due to the
# way we determine the load balancer FQDN or IP. We can't read the normal config since Sirius uses it's own
# configuration because of the encryption needed for the passwords.
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius kubeconfig

# Inform the user of what we are doing

echo " "
echo "NOTICE! When using a kubeconfig file you need to ensure that your environment is configured to"
echo "connect to Kubernetes properly. If you have multiple kubernetes contexts (or custom contexts)"
echo "you may need to remove them and replace them with a simple ~/.kube/config file. This will be "
echo "addressed in a future release."
echo " "

# Sleep so that this is seen...
sleep 5

if pulumi config get kubernetes:kubeconfig -C ${script_dir}/../pulumi/python/config >/dev/null 2>&1; then
  echo "Kubeconfig file found"
else
  echo "Provide an absolute path to your kubeconfig file"
  pulumi config set kubernetes:kubeconfig -C ${script_dir}/../pulumi/python/config
fi

# Clustername
if pulumi config get kubernetes:cluster_name -C ${script_dir}/../pulumi/python/config >/dev/null 2>&1; then
  echo "Clustername found"
else
  echo "Provide your clustername"
  pulumi config set kubernetes:cluster_name -C ${script_dir}/../pulumi/python/config
fi

# Connect to the cluster
if command -v kubectl >/dev/null; then
  echo "Attempting to connect to kubernetes cluster"
  retry 30 kubectl version >/dev/null
fi

# TODO: Figure out better way to handle hostname / ip address for exposing our IC #82
#
# This version of the code forces you to add a hostname which is used to generate the cert when the application is
# deployed, and will output the IP address and the hostname that will need to be set in order to use the self-signed
# cert and to access the application.
#
if pulumi config get kic-helm:fqdn -C ${script_dir}/../pulumi/python/config >/dev/null 2>&1; then
  echo "Hostname found for deployment"
else
  echo "Create a fqdn for your deployment"
  pulumi config set kic-helm:fqdn -C ${script_dir}/../pulumi/python/config
fi

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
  #ACCOUNTS_PW=$(createpw)
  ACCOUNTS_PW=$(base64 /dev/random|head -c${1:-16} | sed 's/[^a-zA-Z0-9]//g')
  pulumi config set --secret sirius:accounts_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius $ACCOUNTS_PW
fi

# Sirius Ledger Database
if pulumi config get sirius:ledger_pwd -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius >/dev/null 2>&1; then
  true
else
  #LEDGER_PW=$(createpw)
  LEDGER_PWW=$(base64 /dev/random|head -c${1:-16} | sed 's/[^a-zA-Z0-9]//g')
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
# TODO: Allow startup scripts to prompt and accept additional config values #97
# The default helm timeout for all of the projects is set at the default of 300 seconds (5 minutes)
# However, since this code path is most commonly going to be used to deploy locally we need to bump
# that value up. A fix down the road will add this a prompt, but for now we are going to double this
# value for all helm deploys.
#

pulumi config set kic-helm:helm_timeout 600 -C ${script_dir}/../pulumi/python/config
pulumi config set logagent:helm_timeout 600 -C ${script_dir}/../pulumi/python/config
pulumi config set logstore:helm_timeout 600 -C ${script_dir}/../pulumi/python/config
pulumi config set certmgr:helm_timeout 600 -C ${script_dir}/../pulumi/python/config
pulumi config set prometheus:helm_timeout 600 -C ${script_dir}/../pulumi/python/config

#
# Set the headers to respect the NO_COLOR variable
#
if [ -z ${NO_COLOR+x} ]; then
  pulumi_args="--emoji --stack ${PULUMI_STACK}"
else
  pulumi_args="--color never --stack ${PULUMI_STACK}"
fi

header "Kubeconfig"
cd "${script_dir}/../pulumi/python/infrastructure/kubeconfig"
pulumi $pulumi_args up

# TODO: This is using a different project than the AWS deploy; we need to collapse those #80
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

header "Finished!!"
THE_FQDN=$(pulumi config get kic-helm:fqdn -C ${script_dir}/../pulumi/python/config || echo "Cannot Retrieve")
THE_IP=$(kubectl get service kic-nginx-ingress  --namespace nginx-ingress --output=jsonpath='{.status.loadBalancer.ingress[*].ip}' || echo "Cannot Retrieve")

echo " "
echo "The startup process has finished successfully"
echo " "
echo " "
echo "Next Steps:"
echo " "
echo "1. Map the IP address ($THE_IP) of your Ingress Controller with your FQDN ($THE_FQDN)."
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
