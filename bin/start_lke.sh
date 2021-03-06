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

function createpw() {
  PWORD=$(dd if=/dev/urandom count=1 2>/dev/null | base64 | head -c16)
  echo $PWORD
}

source "${script_dir}/../config/pulumi/environment"
echo "Configuring all Pulumi projects to use the stack: ${PULUMI_STACK}"

# Create the stack if it does not already exist
# We skip over the tools directory, because that uses a unique stack for setup of the
# kubernetes components for installations without them.
find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi stack select --create "${PULUMI_STACK}" \;

if [[ -z "${LINODE_TOKEN+x}" ]]; then
  echo "LINODE_TOKEN not set"
  if ! grep --quiet '^LINODE_TOKEN=.*' "${script_dir}/../config/pulumi/environment"; then
    read -r -e -p "Enter the Linode Token to use in all projects (leave blank for default): " LINODE_TOKEN
    if [[ -z "${LINODE_TOKEN}" ]]; then
      echo "No Linode Token found - exiting"
      exit 4
    fi
    echo "LINODE_TOKEN=${LINODE_TOKEN}" >>"${script_dir}/../config/pulumi/environment"
    source "${script_dir}/../config/pulumi/environment"
    find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi config set --plaintext linode:token "${LINODE_TOKEN}" \;
  fi
else
  echo "Using LINODE_TOKEN from environment: ${LINODE_TOKEN}"
  find "${script_dir}/../pulumi/python" -mindepth 1 -maxdepth 7 -type f -name Pulumi.yaml -not -path "*/tools/*" -execdir pulumi config set --plaintext linode:token "${LINODE_TOKEN}" \;
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

#
# The initial version of this tried to manage the kubernetes configuration file, but for some reason
# Linode is a bit touchy about this.
#
# So, now we just backup the existing file and slide ours in place. This will be streamlined/addressed as
# part of the rewrite...
#
function add_kube_config() {
  echo "adding ${cluster_name} cluster to local kubeconfig"
  mv $HOME/.kube/config $HOME/.kube/config.mara.backup || true
  pulumi stack output kubeconfig -s "${PULUMI_STACK}" -C ${script_dir}/../pulumi/python/infrastructure/kubeconfig --show-secrets >$HOME/.kube/config
}

function validate_lke_credentials() {
  pulumi_lke_token="$(pulumi --cwd "${script_dir}/../pulumi/python/config" config get linode:token)"
  echo "Validating Linode credentials"
  if ! linode_cli account view >/dev/null; then
    echo >&2 "Linode credentials have expired or are not valid"
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
echo "NOTICE! Currently the deployment for Linode LKE only supports pulling images from the registry! A JWT is "
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

if command -v linode_cli >/dev/null; then
  validate_lke_credentials
fi

#
# Set the headers to respect the NO_COLOR variable
#
if [ -z ${NO_COLOR+x} ]; then
  pulumi_args="--emoji --stack ${PULUMI_STACK}"
else
  pulumi_args="--color never --stack ${PULUMI_STACK}"
fi

# We automatically set this to LKE for infra type; since this is a script specific to LKE
# TODO: combined file should query and manage this
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/config LKE
# Bit of a gotcha; we need to know what infra type we have when deploying our application (BoS) due to the
# way we determine the load balancer FQDN or IP. We can't read the normal config since Sirius uses it's own
# configuration because of the encryption needed for the passwords.
pulumi config set kubernetes:infra_type -C ${script_dir}/../pulumi/python/kubernetes/applications/sirius LKE

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

header "Linode LKE"
cd "${script_dir}/../pulumi/python/infrastructure/linode/lke"
pulumi $pulumi_args up

#
# This is used to streamline the pieces that follow. Moving forward we can add new logic behind this and this
# should abstract away for us. This way we just call the kubeconfig project to get the needed information and
# let the infrastructure specific parts do their own thing (as long as they work with this module)
#
header "Kubeconfig"
cd "${script_dir}/../pulumi/python/infrastructure/kubeconfig"
pulumi $pulumi_args up

# pulumi stack output cluster_name
cluster_name=$(pulumi stack output cluster_id -s "${PULUMI_STACK}" -C ${script_dir}/../pulumi/python/infrastructure/linode/lke)
add_kube_config

# Display the server information
echo "Kubernetes client/server version information:"
kubectl version -o json
echo " "

if command -v kubectl >/dev/null; then
  echo "Attempting to connect to newly create kubernetes cluster"
  retry 30 kubectl version >/dev/null
fi

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

header "Finished!"
THE_FQDN=$(pulumi config get kic-helm:fqdn -C ${script_dir}/../pulumi/python/config || echo "Cannot Retrieve")
THE_IP=$(kubectl get service kic-nginx-ingress --namespace nginx-ingress --output=jsonpath='{.status.loadBalancer.ingress[*].ip}' || echo "Cannot Retrieve")

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
