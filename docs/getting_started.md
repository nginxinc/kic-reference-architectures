# Getting Started Guide

There are a few ways to get the reference architecture set up on your machine.
You can install the dependencies locally and run the project. Alternatively,
the project can be run in a Docker container that you have built.

Here is a rough outline of the steps to get started:

1. Clone git repository, including the Bank of Sirius submodule. This can be
done by running
`git clone --recurse-submodules https://github.com/nginxinc/kic-reference-architectures`

1. Install dependencies (install section below - python3, python venv module,
git, docker, make).

1. Setup Pulumi credentials.

1. Setup AWS credentials OR Setup `kubectl` to connect to an existing cluster

1. Run `./bin/start.sh` and answer the prompts.

## Install on macOS with HomeBrew and Docker Desktop

```sh
# Install Homebrew for the Mac: https://brew.sh/
# Install Docker Toolbox for the Mac:
# https://docs.docker.com/docker-for-mac/install/
$ brew install make git python3
```

## Install on macOS with Docker Desktop

```sh
# In a terminal window with the MacOS UI, install developer tools if they
# haven't already # been installed.
$ xcode-select --install
$ bash ./bin/setup_venv.sh
```

## Install with Debian/Ubuntu Linux

```sh
$ sudo apt-get update
$ sudo apt-get install --no-install-recommends curl ca-certificates git make \
python3-venv docker.io
$ sudo usermod -aG docker $USER
$ newgrp docker
$ bash ./bin/setup_venv.sh
```

## Install with CentOS/Redhat/Rocky Linux

```sh
# Install Docker Yum repository
$ sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
$ sudo yum install python3-pip make git docker-ce
$ sudo systemctl enable --now docker
$ sudo usermod -aG docker $USER
$ newgrp docker
$ bash ./bin/setup_venv.sh
```

## Creating a Debian Docker Runtime Environment

Run the following helper script to build a Debian container image.

```sh
$ ./docker/build_dev_docker_image.sh debian
```

## Stand Alone Install

### Requirements

#### Python 3.7 or Newer or Prerequisites for Building Python 3.7 or Newer

In this project, Pulumi executes Python code that creates cloud and Kubernetes
infrastructure. In order for it to work, Python 3 and the
[venv module](https://docs.python.org/3/library/venv.html) must be installed.
Alternative, if GNU make and the gcc compiler are installed the setup script
can build and install Python 3.

Note that the minimum supported version is 3.7.

#### Git

The `git` command line tool is required for checking out KIC source code from
GitHub and for the KIC image build process.

#### Make

In order to build the Ingress Controller from source, GNU `make` is required to
be installed on the running system. If you are not building from source, you do
not need to install `make`. By default, the build script looks for `gmake` and
then `make`.

#### Docker

Docker is required because the Ingress Controller is a Docker image and needs
Docker to generate the image.

**NOTE**: The kubeconfig deployment option currently only allows you to deploy
from a registry. This allows you to deploy the NGINX IC or the NGINX Plus IC
(with a JWT from your F5 account)

#### Kubernetes

Although not required, installing the
[CLI tool `kubectl`](https://kubernetes.io/docs/tasks/tools/) will allow you to
interact with the Kubernetes cluster that you have stood up using this project.
This tool is also installed as part of the venv that is created and can be used
from that directory.

#### Setup

Within the project, you will need to install Python and dependent libraries
into the `venv` directory. To do this is to invoke the
[`./bin/setup_venv.sh`](../bin/setup_venv.sh) from the project root. This
script will install into the
[virtual environment](https://docs.python.org/3/tutorial/venv.html)
directory:

* Python 3 (via pyenv) if it is not already present
* Pulumi CLI utilities
* AWS CLI utilities
* `kubectl`

After running [`./bin/setup_venv.sh`](../bin/setup_venv.sh) from the project
root, you will need to activate the newly created virtual environment by
running `source ./pulumi/python/venv/bin/activate` from the project root.
This will load the virtual environment's path and other environment variables
into the current shell.

## Post Install Configuration

### Stack Name

For AWS, Linode, or Digital Ocean deployments you will need to add the variable
`PULUMI_STACK_NAME` to the environment file for the deployment at
[`../config/pulumi/environment`](../config/pulumi/environment). This is the name
that will be used for the provisioned Pulumi stack.

If you are running a `kubeconfig` deployment, the process will prompt you for
the value of `PULUMI_STACK_NAME` and update the environment file for you.

### Kubeconfig

If you are using an existing kubernetes installation for this project, you will
need to provide three pieces of information to the installer:

* The full path to a kubeconfig file.
* The name of the cluster you are using.
* The cluster context you are using.

The easiest way to test this is to run the command:
`kubectl --kubeconfig="yourconfig" --cluster="yourcluster" --context="yourcontext"`

### AWS

*Note:* The AWS deployment has been updated from v1.1 and no longer uses the
[`../bin/start.sh`](../bin/start.sh) script for deployment. If you attempt to
use the script to deploy to AWS you will receive an error message. Please
use the new [`../pulumi/python/runner`](../pulumi/python/runner) program for
these deployments.

If you are using AWS as your infrastructure provider
[configuring Pulumi for AWS](https://www.pulumi.com/docs/intro/cloud-providers/aws/setup/)
is necessary. If you already have run the
[`./bin/setup_venv.sh`](../bin/setup_venv.sh)
script, you will have the `aws` CLI tool installed in the path
`../pulumi/python/venv/bin/aws`
and you do not need to install it to run the steps in the Pulumi Guide.

If you want to avoid using environment variables, AWS profile and region
definitions can be contained in the `config/Pulumi.<stack>.yaml` files in each
project. Refer to the Pulumi documentation for details on how to do this.
When you run the [`../pulumi/python/runnner`](../pulumi/python/runner) program
and select your provider you will be prompted for all variables necessary to
use that provider along with MARA specific variables. This information will
be added to the `../config/Pulumi/Pulumi.<stack>.yaml` configuration file. This is
the main configuration file for the project, although there is one other
configuration file used to maintain secrets in the
[`../pulumi/python/kubernetes/secrets`](./pulumi/python/kubernetes/secrets)
kubernetes extras functionality. For more details on those, please see the
README.md in those directories.

### Digital Ocean

*Note:* The Digital Ocean deployment has been updated from v1.1 and no longer
uses the [`../bin/start.sh`](../bin/start.sh) script for deployment. If you
attempt to use the script to deploy to AWS you will receive an error message.
Please use the new [`../pulumi/python/runner`](../pulumi/python/runner) program
for these deployments.

You will need to create a
[Digital Ocean Personal API Token](https://docs.digitalocean.com/reference/api/create-personal-access-token/)
for authentication to Digital Ocean. When you run the
[`./pulumi/python/runnner`](./pulumi/python/runner) program and select your
provider you will be prompted for all variables necessary to use that provider
along with MARA specific variables. This information will be added to the
`./config/Pulumi/Pulumi.<stack>.yaml` configuration file. This is the main
configuration file for the project, although there is one other configuration file
used to maintain secrets in the
[`./pulumi/python/kubernetes/secrets`](./pulumi/python/kubernetes/secrets)
kubernetes extras functionality. For more details on those, please see the
README.md in those directories.

### Linode

*Note:* The Linode deployment has been updated from v1.1 and no longer uses the
[`../bin/start.sh`](../bin/start.sh) script for deployment. If you attempt to
use the script to deploy to AWS you will receive an error message. Please
use the new [`../pulumi/python/runner`](../pulumi/python/runner) program for
these deployments.

You will need to create a
[Linode API Token](https://www.linode.com/docs/products/tools/linode-api/guides/get-access-token/)
for authentication to Linode. When you run the
[`./pulumi/python/runnner`](./pulumi/python/runner) program and select your
provider you will be prompted for all variables necessary to use that provider
along with MARA specific variables. This information will be added to the
`./config/Pulumi/Pulumi.<stack>.yaml` configuration file. This is the main
configuration file for the project, although there is one other configuration file
used to maintain secrets in the
[`./pulumi/python/kubernetes/secrets`](./pulumi/python/kubernetes/secrets)
kubernetes extras functionality. For more details on those, please see the
README.md in those directories.

### Kubeconfig Deployments: MicroK8s / Minikube / K3s / Other

Deployments that use a `kubeconfig` file to access an existing K8 installation
will continue to use the [`../bin/start.sh`](../bin/start.sh) script.
Additionally, these deployments are not able to build the Ingress Controller
and instead need to download from the NGINX repositories. The installation of
NGINX+ is supported via the use of a JWT, if desired.

These deployments will be moved over to use the
[`../pulumi/python/runner`](../pulumi/python/runner) program in a future
release, which will bring them to parity for NGINX IC build/deployment with the
other infrastructures.

### Pulumi

If you already have run the [`./bin/setup_venv.sh`](../bin/setup_venv.sh)
script, you will have the `pulumi` CLI tool installed in the path
`venv/bin/pulumi`. You will need to make an account on
[pulumi.com](https://pulumi.com) or alternatively use another form of state
store. Next, login to pulumi from the CLI by running the command
[`./pulumi/python/venv/bin/pulumi login`](https://www.pulumi.com/docs/reference/cli/pulumi_login/).
Refer to the Pulumi documentation for additional details regarding the command
and alternative state stores.

## Running the Project

Provided you have completed the installation steps, the easiest way to run the
project is to run [`../pulumi/python/runner`](../pulumi/python/runner) for AWS,
Linode, or Digital Ocean and [`../bin/start.sh`](../bin/start.sh) for
`kubeconfig` deployments. This process will prompt you for all required
variables for your deployment type. This information will be used to populate
the configuration files.

Alternatively, you can enter into each Pulumi project directory and execute
each project independently by doing `pulumi up`. Take a look at `start.sh` and
dependent scripts to get a feel for the flow.

If you want to destroy the entire environment you can run
[`../pulumi/python/runner`](../pulumi/python/runner) for AWS, Linode, or
Digital Ocean or [`destroy.sh`](../bin/destroy.sh) for `kubeconfig` deployments.
Detailed information and warnings are emitted by the process as it runs.

### Running the Project in a Docker Container

If you are using a Docker container to run Pulumi, you will want to run the
with the docker socket mounted, like the following command.

```console
$ docker run --interactive --tty \
 --volume /var/run/docker.sock:/var/run/docker.sock \
 kic-ref-arch-pulumi-aws:<distro>
```

If you already have set up Pulumi, kubeconfig information, and/or AWS
credentials on the host machine, you can mount them into the container using
Docker with the following options.

```console
$ docker run --interactive --tty \
 --volume /var/run/docker.sock:/var/run/docker.sock \
 --volume  $HOME/.pulumi:/pulumi/projects/kic-reference-architectures/.pulumi \
 --volume  $HOME/.aws:/pulumi/projects/kic-reference-architectures/.aws \
 --volume  $HOME/.kube:/pulumi/projects/kic-reference-architectures/.kube \
 kic-ref-arch-pulumi-aws:debian
```

### Accessing the Application

The final output from the startup process will provide you with detailed
information on how to access your project. This information will vary based on
the K8 distribution that you are deploying against; the following output is
from a deployment against an existing K8 installation using the *kubeconfig*
option:

```console
Next Steps:
1. Map the IP address (192.168.100.100) of your Ingress Controller with your
   FQDN (mara.example.com).
2. Use the ./bin/test-forward.sh program to establish tunnels you can use to
   connect to the management tools.
3. Use kubectl, k9s, or the Kubernetes dashboard to explore your deployment.

To review your configuration options, including the passwords defined, you can
access the pulumi secrets via the
following commands:

Main Configuration: pulumi config -C <conf path>
Bank of Sirius (Example Application) Configuration: pulumi config -C <conf path>
K8 Loadbalancer IP: kubectl get services --namespace nginx-ingress

Please see the documentation in the github repository for more information
```

### Accessing the Management Tooling

Please see the document
[Accessing Management Tools in MARA](./accessing_mgmt_tools.md) for information
on how to access these tools.

### Cleaning Up

If you want to completely remove all the resources you have provisioned,
run the [`../pulumi/python/runner`](../pulumi/python/runner) for AWS, Linode,
or Digital Ocean or [`destroy.sh`](../bin/destroy.sh) for `kubeconfig`
deployments. Detailed information and warnings are emitted by the
process as it runs.

Be careful because this will **DELETE ALL** the resources you have provisioned.

## Other Resources

Starting with release `v1.1`, the MARA project has begun the process of
transitioning the deployment logic away from BASH scripts and instead using the
[Pulumi Automation API](https://www.pulumi.com/docs/guides/automation-api/) with
Python. For more information on this, please see this
[Design Document](../pulumi/python/automation/DESIGN.md).
