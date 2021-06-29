# NGINX Kubernetes Ingress Controller Automation

This project illustrates the end to end stand up of an AWS VPC cluster,
Elastic Kubernetes Service (EKS), NGINX Kubernetes Ingress Controller (KIC),
and a sample application using [Pulumi](https://www.pulumi.com/). The project
is intended to be used as a reference when building your own infrastructure as 
code deployments. As such, each discrete stage of deployment is defined as a
separate Pulumi project that can be deployment independently of each stage.
Although Pulumi supports many programming languages, Python was chosen as
the language for this project. The reimplementation of the deployments
definitions here should be reproducible in other languages.

## Requirements

### Python

This project is compatible with Python 3.6+. To run the project,
you will need to have installed Python on your system as well as the 
[venv module](https://docs.python.org/3/library/venv.html) and
[pip](https://pypi.org/project/pip/).

Within the project, you will need to install the Python required libraries into
the `venv` directory. The easiest way to do this is to invoke the 
[`setup_venv.sh`](./setup_venv.sh) included in the project.

### NodeJS

A Python dependency that this project relies on makes call outs to a NodeJS
dependency, so unfortunately NodeJS is also a dependency to run the
reference architecture.

### Pulumi

In order to run this project, you will need to first [download, install and 
configure Pulumi](https://www.pulumi.com/docs/get-started/install/) for 
your environment.

### AWS

Since this project illustrates deploying to AWS, 
[configuring Pulumi for AWS](https://www.pulumi.com/docs/intro/cloud-providers/aws/setup/)
is necessary. If you want to avoid using environment variables, AWS profile
and region definitions can be contained in the `config/Pulumi.<stack>.yaml` 
files in each project. Refer to the Pulumi documentation for details on how to
do this.

If the [`aws` CLI](https://aws.amazon.com/cli/) is installed, it will be used
in the setup bash scripts to update your `kubectl` local configuration to use
the newly created EKS.

### Kubernetes

Although not required, installing the [CLI tool `kubectl`](https://kubernetes.io/docs/tasks/tools/)
will allow you to interact with the Kubernetes cluster that you have stood up
using this project.

### Bash

The setup bash scripts will invoke external utilities to display colors and
large banners announcing what resources are set up. These utilities are
completely optional. If you want to see the colorized text display, install
the following.
 * [`colorscript`](https://github.com/charitarthchugh/shell-color-scripts)
 * [`figlet`](http://www.figlet.org/)
 * [`lolcat`](https://github.com/ur0/lolcat) or a suitable alternative

## Getting Started

The easiest way to run the project is to run [`start_all.sh`](./start_all.sh) 
after you have  completed the steps in [requirements](README.md#requirements).
When doing so, be sure to choose the same 
[Pulumi stack name](https://www.pulumi.com/docs/intro/concepts/stack/) 
for all of your projects. Alternatively, you can enter into each Pulumi
project directory and execute each project independently by doing 
`pulumi up`. Take a look at `start_all.sh` to get a feel for the flow.

If you want to blow away the entire environment you can run 
[`destroy.sh`](./destroy.sh).

## Project Structure

To deploy the sample application, the following Pulumi projects are executed
in the order shown below. Each project name maps to a directory name relative
to the root directory of this repository.

```
vpc - defines and installs the VPC and subnets to use with EKS
└─eks - deploys EKS
  └─ecr - configures ECR for use in the cluster
    └─kic-image-build - project that builds a new KIC image  
      └─kic-image-push - pushes KIC image built in previous step to ECR
        └─kic-helm-chart - deploys NGINX Ingress Controller to the EKS cluster 
          └─logstore - deploys a logstore (elasticsearch) to the EKS cluster 
            └─logagent - deploys a logging agent (filebeat) to the EKS cluster 
              └─demo-app - deploys a sample application to the cluster
```

## Configuration

The Pulumi configuration files are in the [config](./config) directory.
Pulumi's configuration files use the following naming convention:
`Pulumi.<stackname>.yaml`. To create a new configuration file for your
Pulumi stack, create a new file with a name that include the stack name.
Then, refer to the sample [configuration file](./config/Pulumi.stackname.yaml.example)
for configuration entries that you want to customize and copy over the
entries that you want to modify from their defaults.

### VPC

Contained within the [`vpc`](./vpc) directory is the first Pulumi project
which is responsible for setting up the VPC and subnets used by EKS. The
project is built such that it will attempt to create a subnet for each
availability zone within the running region. You may want to customize this
behavior, or the IP addressing scheme used.

### Elastic Kubernetes Service (EKS)

Located within the [`eks`](./eks) directory is a project used to stand up a
new EKS cluster on AWS. This project reads data from the previously executed
VPC project using its vpc id and subnets. In this project you may want to 
customize the `instance_type`, `min_size`, or `max_size` parameters provided
to the cluster.

### Elastic Container Registry (ECR)
The [`ecr`](./ecr) project is responsible for installing and configuring
ECR for use with the previously created EKS cluster.

### NGINX Ingress Controller Docker Image Build

Within the [`kic-image-build`](./kic-image-build) directory, there is a
Pulumi project that will allow you to build a new NGINX Kubernetes
Ingress Controller from source. Download of source, compilation, and image
creation are fully automated. This project can be customized to build
different flavors of KIC.

### NGINX Ingress Controller Docker Image Push

Within the [`kic-image-push`](./kic-image-push) directory, there is a
Pulumi project that will allow you to push the previously created KIC
Docker image to ECR in a fully automated manner.

### NGINX Ingress Controller Helm Chart

In the [`kic-helm-chart`](./kic-helm-chart) directory,
you will find the Pulumi project responsible for installing the NGINX
Ingress Controller on the previously deployed EKS cluster. You may want
to customize this project to allow for deploying different versions of
KIC.

A sample config-map is provided in the Pulumi deployment code; this 
code will adjust the logging format to approximate the upstream 
NGINX KIC project which will allow for easier injestion into log
storage and processing systems. 

### Log Store

In the [`logstore`](./logstore) directory, you will find the Pulumi
project reponsible for installing your log store. The current
solution deploys 
[Elasticsearch and Kibana](https://www.elastic.co/elastic-stack) 
using the 
[Bitnami Elasticsearch](https://bitnami.com/stack/elasticsearch/helm)
chart. This solution can be swapped for other options as desired.
This application is deployed to the `logstore` namespace. 

#### Notes
In order to access the Kibana dashboard via your web browser, you will
need to setup port forwarding for the kibana pod. This can be accomplished
using the `kubectl` command:

```
$ # Find the Kibana pod name
$ kubectl get pods -n logstore
NAME                                            READY   STATUS    RESTARTS   AGE
elastic-coordinating-only-b76674c4c-d58rh       1/1     Running   0          61m
elastic-coordinating-only-b76674c4c-sb6v7       1/1     Running   0          61m
elastic-elasticsearch-data-0                    1/1     Running   0          61m
elastic-elasticsearch-data-1                    1/1     Running   0          61m
elastic-elasticsearch-ingest-589d4ddf4b-6djjz   1/1     Running   0          61m
elastic-elasticsearch-ingest-589d4ddf4b-6mzmb   1/1     Running   0          61m
elastic-elasticsearch-master-0                  1/1     Running   0          61m
elastic-elasticsearch-master-1                  1/1     Running   0          61m
elastic-kibana-d45db8647-ghhx2                  1/1     Running   0          61m
$ # Setup the port forward
$ kubectl port-forward elastic-kibana-d45db8647-ghhx2 5601:5601 -n logstore
Forwarding from 127.0.0.1:5601 -> 5601
Forwarding from [::1]:5601 -> 5601
Handling connection for 5601
````

Additionally, you will need to load the saved object data for Kibana from 
the provided [`kibana-data.ndjson`](./extras/kibana/kibana-data.ndjson) 
which can be found in the `./extras/kibana` directory in this project. To
accomplish this, go to "Stack Management -> Saved Objects" in the Kibana
interface. 

### Log Agent

In the [`logagent`](./logagent) directory, you will find the Pulumi
project reponsible for installing your log agent. The current solution
deploys [`Filebeat`](https://www.elastic.co/beats/) which connects
to the logstore deployed in the previous step. This solution can be
swapped for other options as desired. This application is
deployed to the `logagent` namespace.


### Demo Application

A simple sample application is contained in the [`demo-app`](./demo-app)
directory. This project shows off how one may deploy their application
to a cluster that is using KIC.
