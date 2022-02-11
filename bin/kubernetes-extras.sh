#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# Don't pollute console output with upgrade notifications
export PULUMI_SKIP_UPDATE_CHECK=true
# Run Pulumi non-interactively
export PULUMI_SKIP_CONFIRMATIONS=true

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"


# Check to see if the venv has been installed, since this is only going to be used to start pulumi/python based
# projects.
#
if ! command -v "${script_dir}/../pulumi/python/venv/bin/python" > /dev/null ; then
  echo "NOTICE! Unable to find the vnev directory. This is required for the pulumi/python deployment process."
  echo "Please run ./setup_venv.sh from this directory to install the required virtual environment."
  echo " "
  exit 1
else
  echo "Adding to [${script_dir}/venv/bin] to PATH"
  export PATH="${script_dir}/../pulumi/python/venv/bin:$PATH"
fi

if ! command -v pulumi >/dev/null; then
  if [ -x "${script_dir}/../pulumi/python/venv/bin/pulumi" ]; then
    echo "Adding to [${script_dir}/venv/bin] to PATH"
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


function retry() {
    local -r -i max_attempts="$1"; shift
    local -i attempt_num=1
    until "$@"
    do
        if ((attempt_num==max_attempts))
        then
            echo "Attempt ${attempt_num} failed and there are no more attempts left!"
            return 1
        else
            echo "Attempt ${attempt_num} failed! Trying again in $attempt_num seconds..."
            sleep $((attempt_num++))
        fi
    done
}


script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"


echo " "
echo "NOTICE! The stack name provided here should be different from the stack name you use for your main"
echo "deployment. This stack is only used to stand up missing features into your kubernetes cluster, and "
echo "these features should not be added/removed as part of testing."
echo " "
echo "It is recommended you use the name of your cluster for this stack name, but any unique name will work."
echo " "
echo "Because of this, there is not a convenience script to remove these features. However, you can remove  "
echo "them manually using the _pulumi destroy_ command."
echo " "

# Sleep so that this is seen...
sleep 5

if [ ! -f "${script_dir}/../pulumi/python/tools/common/config/environment" ]; then
  touch "${script_dir}/../pulumi/python/tools/common/config/environment"
fi

if ! grep --quiet '^PULUMI_STACK=.*' "${script_dir}/../pulumi/python/tools/common/config/environment"; then
  read -r -e -p "Enter the name of the Pulumi stack to use in tool installation: " PULUMI_STACK
  echo "PULUMI_STACK=${PULUMI_STACK}" >>"${script_dir}/../pulumi/python/tools/common/config/environment"
fi

source "${script_dir}/../pulumi/python/tools/common/config/environment"
echo "Configuring all tool installations to use the stack: ${PULUMI_STACK}"

# Create the stack if it does not already exist
find "${script_dir}/../pulumi/python/tools" -mindepth 2 -maxdepth 2 -type f -name Pulumi.yaml -execdir pulumi stack select --create "${PULUMI_STACK}" \;


echo " "
echo "NOTICE! When using a kubeconfig file you need to ensure that your environment is configured to"
echo "connect to Kubernetes properly. If you have multiple kubernetes contexts (or custom contexts)"
echo "you may need to remove them and replace them with a simple ~/.kube/config file. This will be "
echo "addressed in a future release."
echo " "
echo "This value is used solely for the installation of the extra tools and is not persisted to the main"
echo "configuration file."
echo " "

# Sleep so that this is seen...
sleep 5

if pulumi config get kubernetes:kubeconfig -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
  echo "Kubeconfig file found"
else
  echo "Provide an absolute path to your kubeconfig file"
  pulumi config set kubernetes:kubeconfig -C ${script_dir}/../pulumi/python/tools/common
fi

# Clustername
if pulumi config get kubernetes:cluster_name -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
  echo "Clustername found"
else
  echo "Provide your clustername"
  pulumi config set kubernetes:cluster_name -C ${script_dir}/../pulumi/python/tools/common
fi

# Contextname
# TODO: Update process to use context name as well as kubeconfig and clustername #84
if pulumi config get kubernetes:context_name -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
  echo "Context name found"
else
  echo "Provide your context name"
  pulumi config set kubernetes:context_name -C ${script_dir}/../pulumi/python/tools/common
fi

# Set our variables
kubeconfig="$(pulumi config get kubernetes:kubeconfig -C ${script_dir}/../pulumi/python/tools/common)"
cluster_name="$(pulumi config get kubernetes:cluster_name -C ${script_dir}/../pulumi/python/tools/common)"
context_name="$(pulumi config get kubernetes:context_name -C ${script_dir}/../pulumi/python/tools/common)"

# Show our config...based on the kubeconfig file
if command -v kubectl > /dev/null; then
  echo "Attempting to connect to kubernetes cluster"
  retry 30 kubectl --kubeconfig="${kubeconfig}" config view
fi

# Connect to the cluster
if command -v kubectl > /dev/null; then
  echo "Attempting to connect to kubernetes cluster"
  retry 30 kubectl --kubeconfig="${kubeconfig}" --cluster="${cluster_name}" --context="${context_name}" version > /dev/null
fi

echo " "
echo "For installations that are lacking persistent volume support or egress support this script will help the user install"
echo "the necessary packages. Note that this is not the only way to do this, and also be aware that this may not be the best"
echo "solution for your environment. Ideally, your kubernetes installation already has these features enabled/installed."
echo " "

# Sleep so we are seen
sleep 5

while true; do
    read -r -e -p "Do you wish to install metallb? " yn
    case $yn in
        [Yy]* ) echo "Checking for necessary values in the configuration:"
                pulumi config set metallb:enabled -C ${script_dir}/../pulumi/python/tools/common enabled >/dev/null 2>&1
                if pulumi config get metallb:thecidr -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
                  echo "CIDR found"
                else
                  echo "Provide your CIDR (Note: no validation is done on this data)"
                  pulumi config set metallb:thecidr -C ${script_dir}/../pulumi/python/tools/common
                fi
          break;;
        [Nn]* ) # If they don't want metallb, but have a value in there we delete it
                pulumi config rm metallb:thecidr -C ${script_dir}/../pulumi/python/tools/common > /dev/null 2>&1
                pulumi config rm metallb:enabled -C ${script_dir}/../pulumi/python/tools/common > /dev/null 2>&1
                break;;
        * ) echo "Please answer yes or no.";;
    esac
done

while true; do
    read -r -e -p "Do you wish to install nfs client support for persistent volumes? " yn
    case $yn in
        [Yy]* ) echo "Checking for necessary values in the configuration:"
                pulumi config set nfsvols:enabled -C ${script_dir}/../pulumi/python/tools/common enabled >/dev/null 2>&1
                if pulumi config get nfsvols:nfsserver -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
                  echo "NFS Server IP found"
                else
                  echo "Provide your NFS Server IP (Note: no validation is done on this data)"
                  pulumi config set nfsvols:nfsserver -C ${script_dir}/../pulumi/python/tools/common
                fi
                if pulumi config get nfsvols:nfspath -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
                  echo "NFS Share Path found"
                else
                  echo "Provide your NFS Share Path (Note: no validation is done on this data)"
                  pulumi config set nfsvols:nfspath -C ${script_dir}/../pulumi/python/tools/common
                fi
          break;;
        [Nn]* ) # If they don't want nfsvols, but have a value in there we delete it
                pulumi config rm nfsvols:nfsserver -C ${script_dir}/../pulumi/python/tools/common > /dev/null 2>&1
                pulumi config rm nfsvols:nfspath -C ${script_dir}/../pulumi/python/tools/common > /dev/null 2>&1
                pulumi config rm nfsvols:enabled -C ${script_dir}/../pulumi/python/tools/common > /dev/null 2>&1
                break;;
        * ) echo "Please answer yes or no.";;
    esac
done

pulumi_args="--emoji "

if pulumi config get metallb:enabled -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
  echo "====================="
  echo "| MetalLB           |"
  echo "====================="
  cd "${script_dir}/../pulumi/python/tools/metallb"
  pulumi $pulumi_args up
fi

if pulumi config get nfsvols:enabled -C ${script_dir}/../pulumi/python/tools/common >/dev/null 2>&1; then
  echo "====================="
  echo "| NFSVols           |"
  echo "====================="

  cd "${script_dir}/../pulumi/python/tools/nfsvolumes"
  pulumi $pulumi_args up
fi