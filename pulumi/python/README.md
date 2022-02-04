# MARA: Pulumi / Python

This directory contains the 

This project illustrates the end to end stand up of an AWS VPC cluster, Elastic Kubernetes Service (EKS), NGINX
Kubernetes Ingress Controller (KIC), and a sample application using [Pulumi](https://www.pulumi.com/). The project is
intended to be used as a reference when building your own infrastructure as code deployments. As such, each discrete
stage of deployment is defined as a separate Pulumi project that can be deployment independently of each stage. Although
Pulumi supports many programming languages, Python was chosen as the language for this project. The reimplementation of
the deployments definitions here should be reproducible in other languages.

## Getting Started

For instructions on running the project, refer to the
[Getting Started Guide](../../docs/getting_started.md).

## Project Structure

### Top Level
There are several directories located at the root of the project which are used; these are at the project root
because they are intended to be outside the specific IaC providers (ie, for example to be used for a port to Terraform).

```
├── bin
├── config
│   └── pulumi
├── docker
├── docs
└── extras
```

- The [`bin`](../../bin) directory contains all the binaries and scripts that are used to start/stop the project, as well
as perform capabilities testing and deployment of extra functionality. 
- The [`config`](../../config) directory holds the `requirements.txt` for the venv needed for this project.
- The [`config/pulumi`](../../config/pulumi) directory holds the configuration files for deployments, as well as a
reference configuration that illustrates the available configuration options and their defaults.
- The [`docker`](../../docker) directory contains Dockerfiles and a script to build a docker-based deployment image that 
contains all the tooling necessary to deploy MARA.
- The [`docs`](../../docs) directory contains all documentation relevant to the overall project.
- The [`extras`](../../extras) directory contains additional scripts, notes, and configurations.

### Pulumi/Python Level
This directory contains all the Pulumi/Python based logic, which currently consists of the following:

```
├── config
├── infrastructure
│   ├── aws
│   └── kubeconfig
├── kubernetes
│   ├── applications
│   ├── certmgr
│   ├── logagent
│   ├── logstore
│   ├── nginx
│   ├── observability
│   ├── prometheus
│   └── venv
├── tools
│   ├── common
│   ├── kubevip
│   ├── metallb
│   └── nfsvolumes
├── utility
│   ├── kic-image-build
│   ├── kic-image-push
│   └── kic-pulumi-utils
└── venv
    ├── bin
    ├── include
    ├── lib
    ├── lib64 -> lib
    ├── share
    └── src
```


- The [`config`](./config) directory contains files used by Pulumi to manage the configuration for this project. Note that
this directory is essentially a redirect to the project-wide [`config`](../../config/pulumi) directory.
- The [`infrastructure`](./infrastructure) directory contains files used to stand up Kubernetes as well as to provide a 
common project for all of the infrastructure and kubeconfig based clusters.
- The [`kubernetes`](./kubernetes) directory contains all of the kubernetes based deployments; there are two key subdirectories
in this directory:
  - The [`nginx`](./kubernetes/nginx) directory contains all NGNIX products.
  - The [`applications`](./kubernetes/applications) directory contains all applications that have been tested for deployment with MARA.
- The [`tools`](./tools) directory contains projects that are used with the `kubernetes-extras.sh` script found in the bin 
directory.
- The [`utility`](./utility) directory contains the code used to build/pull/push the NGNIX Ingress Controller, and other 
projects used to support the environment. 
- The [`venv/bin`](./venv/bin) directory contains the virtual environment for Python along with some key utilities, such
as `pulumi`, `kubectl`, and `node`.

## Configuration

The Pulumi configuration files are in the [`config`](../../config/pulumi) directory. Pulumi's configuration files use the following
naming convention:
`Pulumi.<stackname>.yaml`. To create a new configuration file for your Pulumi stack, create a new file with a name that
include the stack name. Then, refer to the sample [configuration file](../../config/pulumi/Pulumi.stackname.yaml.example)
for configuration entries that you want to customize and copy over the entries that you want to modify from their
defaults.

### AWS
The following directories are specific to AWS.

#### VPC

Contained within the [`vpc`](./infrastructure/aws/vpc) directory is the first Pulumi project which is responsible for setting up the VPC
and subnets used by EKS. The project is built such that it will attempt to create a subnet for each availability zone
within the running region. You may want to customize this behavior, or the IP addressing scheme used.

#### Elastic Kubernetes Service (EKS)

Located within the [`eks`](./infrastructure/aws/eks) directory is a project used to stand up a new EKS cluster on AWS. This project reads
data from the previously executed VPC project using its vpc id and subnets. In this project you may want to customize
the `instance_type`, `min_size`, or `max_size` parameters provided to the cluster.

#### Elastic Container Registry (ECR)

The [`ecr`](./infrastructure/aws/ecr) project is responsible for installing and configuring ECR for use with the previously created EKS
cluster.

### NGINX Ingress Controller Docker Image Build

Within the [`kic-image-build`](./utility/kic-image-build) directory, there is a Pulumi project that will allow you to build a
new NGINX Kubernetes Ingress Controller from source. Download of source, compilation, and image creation are fully
automated. This project can be customized to build different flavors of KIC.

### NGINX Ingress Controller Docker Image Push

Within the [`kic-image-push`](./utility/kic-image-push) directory, there is a Pulumi project that will allow you to push the
previously created KIC Docker image to ECR in a fully automated manner.

### NGINX Ingress Controller Helm Chart

In the [`ingress-contoller`](./kubernetes/nginx/ingress-controller) directory, you will find the Pulumi project responsible for installing the
NGINX Ingress Controller. You may want to customize this project to allow for deploying different versions of KIC. This 
chart is only used for AWS deployments. All other deployments use the [`ingress-controller-repo-only`](./kubernetes/nginx/ingress-controller-repo-only)
directory, which at this time **only allows the use of deployments from the NGINX repo with a JWT**.

A sample config-map is provided in the Pulumi deployment code; this code will adjust the logging format to approximate
the upstream NGINX KIC project which will allow for easier ingestion into log storage and processing systems.

Note that this deployment uses the GA Ingress APIs; this has been tested with helm chart version 0.11.1 and NGINX KIC 2.0.2. 
Older versions of the KIC and helm charts can be used, but care should be taken to ensure that the helm chart version used
is compatible with the KIC version. This information can be found in the 
[NGINX KIC Release Notes](https://docs.nginx.com/nginx-ingress-controller/releases/) for each release.

#### Ingress API Versions and NGINX KIC

Starting with Kubernetes version 1.22, support for the Ingress Beta API `networking.k8s.io/v1beta` will be dropped requiring
use of the GA Ingress API `networking.k8s.io/v1`. However, Kubernetes versions 1.19 through 1.21 allows these two API versions 
to coexist and maintains compatibility for consumers of the API, meaning that the API will respond correctly to calls to either
the `v1beta` and/or `v1` routes.

This project uses the NGINX KIC v2.x releases which includes full support for the GA APIs.
do not use the 

### Log Store

In the [`logstore`](./kubernetes/logstore) directory, you will find the Pulumi project responsible for installing your log store.
The current solution deploys
[Elasticsearch and Kibana](https://www.elastic.co/elastic-stack)
using the
[Bitnami Elasticsearch](https://bitnami.com/stack/elasticsearch/helm)
chart. This solution can be swapped for other options as desired. This application is deployed to the `logstore`
namespace. There are several configuration options available in the configuration file for the project in order to better
tailor this deployment to the size of the cluster being used.

#### Notes

In order to access the Kibana dashboard via your web browser, you will need to setup port forwarding for the kibana pod.
This can be accomplished using the `kubectl` command:

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

### Log Agent

In the [`logagent`](./logagent) directory, you will find the Pulumi project responsible for installing your log agent.
The current solution deploys [`Filebeat`](https://www.elastic.co/beats/) which connects to the logstore deployed in the
previous step. This solution can be swapped for other options as desired. This application is deployed to the `logagent`
namespace.

### Certificate Management

TLS is enabled via [cert-manager](https://cert-manager.io/) which is installed in the cert-manager namespace. Creation
of ClusterIssuer or Issuer resources is delegated to the individual applications and is not done as part of this
deployment.

### Prometheus

Prometheus is deployed and configured to enable the collection of metrics for all components that have
a defined service monitor. At installation time, the deployment will instantiate:
- Node Exporters
- Kubernetes Service Monitors
- Grafana preloaded with dashboards and datasources for Kubernetes management
- The NGINX Ingress Controller
- Statsd receiver

The former behavior of using the `prometheus.io:scrape: true` property set in the annotations
indicating pods where metrics should be scraped has been deprecated, and these annotations will
be removed in the near future.

Also, the standalone Grafana deployment has been removed from the standard deployment scripts, as it is installed
as part of this project.

Finally, this namespace will hold service monitors created by other projects, for example the Bank of Sirius
deployment currently deploys a service monitor for each of the postgres monitors that are deployed.

Notes: 
1. The NGINX IC needs to be configured to expose prometheus metrics; this is currently done by default.
2. The default address binding of the `kube-proxy` component is set to `127.0.0.1` and as such will cause errors when the 
canned prometheus scrape configurations are run. The fix is to set this address to `0.0.0.0`. An example manifest
has been provided in [prometheus/extras](./kubernetes/prometheus/extras) that can be applied against your installation with 
`kubectl apply -f ./filename`. Please only apply this change once you have verified that it will work with your 
version of Kubernetes.
3. The _grafana_ namespace has been maintained in the configuration file to be used by the prometheus operator deployed
version of Grafana. This version only accepts a password; you can still specify a username for the admin account but it 
will be silently ignored. This will be changed in the future.


### Observability

We deploy the [OTEL Collector Operator](https://github.com/open-telemetry/opentelemetry-collector) along with a simple
collector. There are several other configurations in the [observability/otel-objects](./kubernetes/observability/otel-objects) 
directory. See the [README.md](./kubernetes/observability/otel-objects/README.md) file in the 
[observability/otel-objects](./kubernetes/observability/otel-objects) for more information, including an explanation of the
default configuration.

### Demo Application

A forked version of the Google
[_Bank of Anthos_](https://github.com/GoogleCloudPlatform/bank-of-anthos)
application is contained in the [`sirius`](./kubernetes/applications/sirius) directory. The github repository for this for is at [_Bank of
Sirius_](https://github.com/nginxinc/bank-of-sirius).

Normally, the `frontend` microservice is exposed via a load balancer for traffic management. This deployment has been
modified to use the NGINX or NGINX Plus KIC to manage traffic to the `frontend` microservice. The NGINX or NGINX Plus
KIC is integrated into the cluster logging system, and the user can configure the KIC as desired.

An additional change to the application is the conversion of several of the standard Kubernetes deployment manifests
into Pulumi code. This has been done for the configuration maps, the ingress controller, and the JWT RSA signing kay
pair. This allows the user to take advantage Pulumi's feature set, by demonstrating the process of creating and
deploying an RSA key pair at deployment time and using the project configuration file to set config variables, including
secrets.

As part of the Bank of Sirius deployment, we deploy a cluster-wide
[self-signed](https://cert-manager.io/docs/configuration/selfsigned/)
issuer using the cert-manager deployed above. This is then used by the Ingress object created to enable TLS access to
the application. Note that this Issuer can be changed out by the user, for example to use the
[ACME](https://cert-manager.io/docs/configuration/acme/) issuer. The use of the ACME issuer has been tested and works 
without issues, provided the FQDN meets the length requirements. As of this writing the AWS ELB hostname is too long
to work with the ACME server. Additional work in this area will be undertaken to provide dynamic DNS record creation
as part of this process so legitimate certificates can be issued.

In order to provide visibility into the Postgres databases that are running as part of the application, the Prometheus
Postgres data exporter will be deployed into the same namespace as the application and will be configured to be scraped
by the prometheus server installed earlier.

**Note** Due to the way that Pulumi currently handles secrets, the [sirius](./kubernetes/applications/sirius)
directory contains its own configuration directory [sirius/config](./kubernetes/applications/sirius/config). This directory contains an example
configuration file that can be copied over and used. The user will be prompted to add passwords to the configuration
file at the first run of the [start.sh](../../bin/start_all.sh) script. This is a work-around that will be retired as Pulumi
provides better tools for hierarchical configuration files.

## Simple Load Testing

In order to help enable simple load testing, a script has been provided that uses the
`kubectl` command to port-forward monitoring and management connections to the local workstation. This command
is [`test-foward.sh`](../../bin/test-forward.sh).
