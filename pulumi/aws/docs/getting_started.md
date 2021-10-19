# Getting Started Guide

There are a few ways to get the reference architecture set up on your machine.
You can install the dependencies locally and run the project. Alternatively,
the project can be run in a Docker container that you have built.

Here is a rough outline of the steps to get started:

 1. Clone git repository, including the Bank of Sirius submodule. This can be done 
    by running `git clone --recurse-submodules https://github.com/nginxinc/kic-reference-architectures`
 2. Install dependencies (install section below - python3, python venv module, 
    git, docker, make).
 3. Setup AWS credentials.
 4. Setup Pulumi credentials.
 5. Run `start_all.sh` and answer the prompts.

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

## Creating a CentOS Docker Runtime Environment 

Run the following helper script to build a CentOS container image.
```
$ ./build_dev_docker_image.sh centos
```

## Stand Alone Install

### Requirements

#### Python 3 or Prerequisites for Building Python

In this project, Pulumi executes Python code that creates cloud and Kubernetes
infrastructure. In order for it to work, Python 3 and the [venv module](https://docs.python.org/3/library/venv.html) 
must be installed. Alternative, if GNU make and the gcc compiler are installed
the setup script can build and install Python 3.

#### Git

The `git` command line tool is required for checking out KIC source code from
github and for the KIC image build process.

#### Make

In order to build the Ingress Controller from source, GNU `make` is required
to be installed on the running system. If you are not building from source,
you do not need to install `make`. By default, the build script looks for
`gmake` and then `make`.

#### Docker

Docker is required because the Ingress Controller is a Docker image and needs
Docker to generate the image.

#### Kubernetes

Although not required, installing the [CLI tool `kubectl`](https://kubernetes.io/docs/tasks/tools/)
will allow you to interact with the Kubernetes cluster that you have stood up
using this project.

#### Setup

Within the project, you will need to install Python and dependent libraries 
into the `venv` directory. To do this is to invoke the [`setup_venv.sh`](./setup_venv.sh) 
included in the project. This script will install into the [virtual environment](https://docs.python.org/3/tutorial/venv.html)
directory:

 * Python 3 (via pyenv) if it is not already present
 * Pulumi CLI utilities
 * AWS CLI utilities 
 * `kubectl`

After running [`setup_venv.sh`](./setup_venv.sh), you will need to activate 
the newly created virtual environment by running `source venv/bin/activate`.
This will load the virtual environment's path and other environment variables
into the current shell.

## Post Install Configuration

### AWS

Since this project illustrates deploying infrastructure to AWS, 
[configuring Pulumi for AWS](https://www.pulumi.com/docs/intro/cloud-providers/aws/setup/)
is necessary. If you already have run the [`setup_venv.sh`](../setup_venv.sh)
script, you will have the `aws` CLI tool installed in the path `venv/bin/aws`
and you do not need to install it to run the steps in the Pulumi Guide.

If you want to avoid using environment variables, AWS profile
and region definitions can be contained in the `config/Pulumi.<stack>.yaml` 
files in each project. Refer to the Pulumi documentation for details on how to
do this. When you run the script [`startup_all.sh`](./start_all.sh) will 
prompt you to add the AWS region and profile values that will then be added 
to the `config/Pulumi.<stack>.yaml` in each project directory.

### Pulumi

If you already have run the [`setup_venv.sh`](../setup_venv.sh)
script, you will have the `pulumi` CLI tool installed in the path `venv/bin/pulumi`.
You will need to make an account on [pulumi.com](https://pulumi.com) or 
alternatively use another form of state store. Next, login to pulumi from
the CLI by running the command [`venv/bin/pulumi login`](https://www.pulumi.com/docs/reference/cli/pulumi_login/).
Refer to the Pulumi documentation for additional details regarding the command
and alternative state stores.

## Running the Project

The easiest way to run the project is to run [`start_all.sh`](./start_all.sh) 
after you have completed the installation steps. When doing so, be sure to 
choose the same 
[Pulumi stack name](https://www.pulumi.com/docs/intro/concepts/stack/) 
for all of your projects. Additionally, this script will prompt you for the
AWS region and profile information. This information will be used to populate
the `config/Pulumi.<stack>.yaml` files in each project directory.

Alternatively, you can enter into each Pulumi
project directory and execute each project independently by doing 
`pulumi up`. Take a look at `start_all.sh` to get a feel for the flow.

If you want to blow away the entire environment you can run 
[`destroy.sh`](./destroy.sh).

### Running the Project in a Docker Container

If you are using a Docker container to run Pulumi, you will want to run the
with the docker socket mounted, like the following command.
```
docker run --interactive --tty --volume /var/run/docker.sock:/var/run/docker.sock \
     kic-ref-arch-pulumi-aws:<distro>
```

If you already have setup Pulumi and/or AWS credentials on the host machine,
you can mount them into the container using Docker with the following options.
```
docker run --interactive --tty \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    --volume  $HOME/.pulumi:/pulumi/projects/kic-reference-architectures/.pulumi \
    --volume  $HOME/.aws:/pulumi/projects/kic-reference-architectures/.aws \
    kic-ref-arch-pulumi-aws:<distro>
```

Replace `<distro>` with either `centos` or `debian`.

### Cleaning Up

If you want to completely remove all the resources you have provisioned, run the
script: [`destroy.sh`](../destroy.sh).

Be careful because this will **DELETE ALL** the resources you have provisioned.