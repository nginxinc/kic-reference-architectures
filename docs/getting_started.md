# Getting Started Guide

There are a few ways to get the reference architecture set up on your machine. You can install the dependencies locally
and run the project. Alternatively, the project can be run in a Docker container that you have built.

Here is a rough outline of the steps to get started:

1. Clone git repository, including the Bank of Sirius submodule. This can be done by
   running `git clone --recurse-submodules https://github.com/nginxinc/kic-reference-architectures`
2. Install dependencies (install section below - python3, python venv module, git, docker, make).
3. Setup Pulumi credentials.
4. Setup AWS credentials OR Setup `kubectl` to connect to an existing cluster
5. Run `./bin/start.sh` and answer the prompts.

## Install on MacOS with HomeBrew and Docker Desktop

```
# Install Homebrew for the Mac: https://brew.sh/
# Install Docker Toolbox for the Mac: https://docs.docker.com/docker-for-mac/install/
$ brew install make git python3
```

## Install on MacOS with Docker Desktop

```
# In a terminal window with the MacOS UI, install developer tools if they haven't already 
# been installed.
$ xcode-select --install
$ bash ./setup_venv.sh
```

## Install with Debian/Ubuntu Linux

```
$ sudo apt-get update
$ sudo apt-get install --no-install-recommends curl ca-certificates git make python3-venv docker.io
$ sudo usermod -aG docker $USER
$ newgrp docker
$ bash ./setup_venv.sh
```

## Install with CentOS/Redhat Linux

```
# Install Docker Yum repository
$ sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
$ sudo yum install python3-pip make git docker-ce
$ sudo systemctl enable --now docker
$ sudo usermod -aG docker $USER
$ newgrp docker
$ bash ./setup_venv.sh
```

## Creating a Debian Docker Runtime Environment

Run the following helper script to build a Debian container image.

```
$ ./build_dev_docker_image.sh debian
```

## Stand Alone Install

### Requirements

#### Python 3 or Prerequisites for Building Python

In this project, Pulumi executes Python code that creates cloud and Kubernetes infrastructure. In order for it to work,
Python 3 and the [venv module](https://docs.python.org/3/library/venv.html)
must be installed. Alternative, if GNU make and the gcc compiler are installed the setup script can build and install
Python 3.

#### Git

The `git` command line tool is required for checking out KIC source code from github and for the KIC image build
process.

#### Make

In order to build the Ingress Controller from source, GNU `make` is required to be installed on the running system. If
you are not building from source, you do not need to install `make`. By default, the build script looks for
`gmake` and then `make`.

#### Docker

Docker is required because the Ingress Controller is a Docker image and needs Docker to generate the image.

**NOTE**: The kubeconfig deployment option currently requires that a JWT token be used to pull the NGINX plus image from
the nginx.com repository. This will be updated in a future release.

#### Kubernetes

Although not required, installing the [CLI tool `kubectl`](https://kubernetes.io/docs/tasks/tools/)
will allow you to interact with the Kubernetes cluster that you have stood up using this project.

#### Setup

Within the project, you will need to install Python and dependent libraries into the `venv` directory. To do this is to
invoke the [`./bin/setup_venv.sh`](../bin/setup_venv.sh)
from the project root. This script will install into
the [virtual environment](https://docs.python.org/3/tutorial/venv.html)
directory:

* Python 3 (via pyenv) if it is not already present
* Pulumi CLI utilities
* AWS CLI utilities
* `kubectl`

After running [`./bin/setup_venv.sh`](../bin/setup_venv.sh) from the project root, you will need to activate the newly
created virtual environment by running
`source ./pulumi/python/venv/bin/activate` from the project root. This will load the virtual environment's path and
other environment variables into the current shell.

## Post Install Configuration

### Kubeconfig

If you are using an existing kubernetes installation for this project, you will need to provide three pieces of
information to the installer:

- The full path to a kubeconfig file.
- The name of the cluster you are using.
- The cluster context you are using.

The easiest way to test this is to run the command:
`kubectl --kubeconfig="yourconfig" --cluster="yourcluster" --context="yourcontext"`

One you have verified you can connect to the cluster you will need to test to make sure your cluster supports the
minimum required capabilities for MARA. You can test this by running the [`./bin/testcap.sh`](../bin/testcap.sh)
script.

This script does several things:

1. Creates a namespace
2. Creates a persistent volume claim
3. Deploys a pod to test the persistent volume
4. Writes to the persistent volume
5. Reads from the persistent volume
6. Destroys the pod
7. Destroys the persistent volume
8. Deploys a service and attempts to provision a `LoadBalancer` to obtain an egress IP address
9. Destroys the service
10. Destroys the namespace

If any of these tests fails the script exits with notes on the failure. These failures need to be remediated before MARA
can be installed.

There are several utilities under the `./pulumi/python/tools` directory that are intended for use to add the necessary
capabilities to a Kubernetes cluster. Note that these are not extensively tested with MARA, but are included for
convenience. Please see the [README.md](../pulumi/python/tools/README.md) in that directory for additional information.
Note that these tools can be installed via the [kubernetes-extras.sh](../bin/kubernetes-extras.sh)
script.

### AWS

If you are using AWS as your infrastructure provider
[configuring Pulumi for AWS](https://www.pulumi.com/docs/intro/cloud-providers/aws/setup/)
is necessary. If you already have run the [`./bin/setup_venv.sh`](../bin/setup_venv.sh)
script, you will have the `aws` CLI tool installed in the path `./pulumi/python/venv/bin/aws`
and you do not need to install it to run the steps in the Pulumi Guide.

If you want to avoid using environment variables, AWS profile and region definitions can be contained in
the `config/Pulumi.<stack>.yaml`
files in each project. Refer to the Pulumi documentation for details on how to do this. When you run the
script [`./bin/start.sh`](../bin/start.sh) and select an AWS installation, you will be prompted to add the AWS region
and profile values that will then be added to the `./config/Pulumi/Pulumi.<stack>.yaml`. This is the main configuration
file for the project, although there are two other configuration files kept for the application standup and the
kubernetes extras functionality. For more details on those, please see the README.md in those directories.

### Pulumi

If you already have run the [`./bin/setup_venv.sh`](../bin/setup_venv.sh)
script, you will have the `pulumi` CLI tool installed in the path `venv/bin/pulumi`. You will need to make an account
on [pulumi.com](https://pulumi.com) or alternatively use another form of state store. Next, login to pulumi from the CLI
by running the
command [`./pulumi/python/venv/bin/pulumi login`](https://www.pulumi.com/docs/reference/cli/pulumi_login/). Refer to the
Pulumi documentation for additional details regarding the command and alternative state stores.

## Running the Project

The easiest way to run the project is to run [`start.sh`](./start.sh)
after you have completed the installation steps. When doing so, be sure to choose the same
[Pulumi stack name](https://www.pulumi.com/docs/intro/concepts/stack/)
for all of your projects. Additionally, this script will prompt you for the AWS region and profile information. This
information will be used to populate the `./config/pulumi/Pulumi.<stack>.yaml` file.

Alternatively, you can enter into each Pulumi project directory and execute each project independently by doing
`pulumi up`. Take a look at `start.sh` and dependent scripts to get a feel for the flow.

If you want to destroy the entire environment you can run [`destroy.sh`](./destroy.sh). This script calls either an AWS
or kubeconfig specific script for the actual destruction. Detailed information and warnings are emitted by the script as
it runs.

### Running the Project in a Docker Container

If you are using a Docker container to run Pulumi, you will want to run the with the docker socket mounted, like the
following command.

```
docker run --interactive --tty --volume /var/run/docker.sock:/var/run/docker.sock \
     kic-ref-arch-pulumi-aws:<distro>
```

If you already have setup Pulumi, kubeconfig information, and/or AWS credentials on the host machine, you can mount them
into the container using Docker with the following options.

```
docker run --interactive --tty \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    --volume  $HOME/.pulumi:/pulumi/projects/kic-reference-architectures/.pulumi \
    --volume  $HOME/.aws:/pulumi/projects/kic-reference-architectures/.aws \
    --volume  $HOME/.kube:/pulumi/projects/kic-reference-architectures/.kube \
    kic-ref-arch-pulumi-aws:debian
```

### Cleaning Up

If you want to completely remove all the resources you have provisioned, run the
script: [`./bin/destroy.sh`](../bin/destroy.sh).

Be careful because this will **DELETE ALL** the resources you have provisioned.