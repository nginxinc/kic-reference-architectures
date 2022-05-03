#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# Don't pollute console output with upgrade notifications
export PULUMI_SKIP_UPDATE_CHECK=true
# Run Pulumi non-interactively
export PULUMI_SKIP_CONFIRMATIONS=true

# Unset virtual environment if defined....
unset VIRTUAL_ENV

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

# Check to see if the venv has been installed, since this is only going to be used to start pulumi/python based
# projects.
#
if ! command -v "${script_dir}/../pulumi/python/venv/bin/python" > /dev/null ; then
  echo "NOTICE! Unable to find the venv directory. This is required for the pulumi/python deployment process."
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

if ! command -v python3 >/dev/null; then
  echo >&2 "Python 3 must be installed to continue"
  exit 1
fi

# Check to see if the user is logged into Pulumi
if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
  pulumi login

  if ! pulumi whoami --non-interactive >/dev/null 2>&1; then
    echo >&2 "Unable to login to Pulumi - exiting"
    exit 2
  fi
fi

echo " "
echo "NOTICE! This shell script will call the appropriate helper script depending on your answer to the next question."
echo " "
echo "This script currently supports standing up AWS, Linode, and Digital Ocean kubernetes deployments, provided "
echo "the correct credentials are supplied. It also supports the user of a kubeconfig file with a defined cluster name"
echo "and context, which must be provided by the user."
echo " "
echo "Please read the documentation for more details."
echo " "
# Sleep so we are seen...
sleep 5

if [ -s "${script_dir}/../config/pulumi/environment" ] && grep --quiet '^PULUMI_STACK=.*' "${script_dir}/../config/pulumi/environment"; then
  source "${script_dir}/../config/pulumi/environment"
  echo "Environment data found for stack: ${PULUMI_STACK}"
  while true; do
    read -r -e -p "Environment file exists and is not empty. Answer yes to use, no to delete. " yn
    case $yn in
    [Yy]*) # We have an environment file and they want to keep it....
      if pulumi config get kubernetes:infra_type -C ${script_dir}/../pulumi/python/config>/dev/null 2>&1; then
        INFRA="$(pulumi config get kubernetes:infra_type -C ${script_dir}/../pulumi/python/config)"
        if [ $INFRA == 'AWS' ]; then
          exec ${script_dir}/start_aws.sh
          exit 0
        elif [ $INFRA == 'kubeconfig' ]; then
          exec ${script_dir}/start_kube.sh
          exit 0
        elif [ $INFRA == 'DO' ]; then
          exec ${script_dir}/start_do.sh
          exit 0
        elif [ $INFRA == 'LKE' ]; then
          exec ${script_dir}/start_lke.sh
          exit 0
        else
          echo "Corrupt or non-existent configuration file, please restart and delete and reconfigure."
          exit 1
        fi
      else
        echo "Corrupt or non-existent configuration file, please restart and delete and reconfigure."
        exit 1
      fi
      break
      ;;
    [Nn]*) # They want to remove and reconfigure
      rm -f ${script_dir}/../config/pulumi/environment
      break
      ;;
    *) echo "Please answer yes or no." ;;
    esac
  done
fi

while true; do
  read -e -r -p "Type a for AWS, d for Digital Ocean, k for kubeconfig, l for Linode? " infra
  case $infra in
  [Aa]*)
    echo "Calling AWS startup script"
    exec ${script_dir}/start_aws.sh
    exit 0
    break
    ;;
  [Kk]*)
    echo "Calling kubeconfig startup script"
    exec ${script_dir}/start_kube.sh
    exit 0
    break
    ;;
  [Dd]*)
    echo "Calling Digital Ocean startup script"
    exec ${script_dir}/start_do.sh
    exit 0
    break
    ;;
  [Ll]*)
    echo "Calling Linode startup script"
    exec ${script_dir}/start_lke.sh
    exit 0
    break
    ;;
  *) echo "Please answer a, d, k, or l." ;;
  esac
done
