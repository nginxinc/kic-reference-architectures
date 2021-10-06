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

## Getting Started

For instructions on running the project, refer to the 
[Getting Started Guide](docs/getting_started.md).

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
              └─certmgr - deploys the open source cert-manager.io helm chart to the EKS cluster
                └─prometheus - deploys prometheus server, node exporter, and statsd collector for metrics
                  └─grafana - deploys the grafana visualization platform
                    └─sirius - deploys the Bank of Sirus application to the EKS cluster
                
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

### Certificate Management

TLS is enabled via [cert-manager](https://cert-manager.io/) which is installed in 
the cert-manager namespace. Creation of ClusterIssuer or Issuer resources
is delegated to the individual applications and is not done as part of this 
deployment. 

### Prometheus

Prometheus is deployed and configured to enable the collection of metrics for all 
components that have properties `prometheus.io:scrape: true` set in the annotations
(along with any other connection information). This includes the prometheus `node-exporter`
daemonset which is deployed in this step as well.

This also pulls data from the NGINX KIC, provided the KIC is configured to allow 
prometheus access (which is enabled by default). 

### Grafana

Grafana is deployed and configured with a connection to the prometheus datasource
installed above. At the time of this writing, the NGINX Plus KIC dashboard is installed
as part of the initial setup. Additional datasources and dashboards can be added by the
user either in the code, or via the standard Grafana tooling.

### Demo Application

A forked version of the Google 
[_Bank of Anthos_](https://github.com/GoogleCloudPlatform/bank-of-anthos)
application is contained in the [`sirius`](./sirius) directory. The github repository
for this for is at [_Bank of Sirius_](https://github.com/nginxinc/bank-of-sirius). 

Normally, the `frontend` microservice is exposed via a load balancer for
traffic management. This deployment has been modified to use the NGINX or
NGINX Plus KIC to manage traffic to the `frontend` microservice. The NGINX
or NGINX Plus KIC is integrated into the cluster logging system, and the 
user can configure the KIC as desired.

An additional change to the application is the conversion of several of 
the standard Kubernetes deployment manifests into Pulumi code. This has been
done for the configuration maps, the ingress controller, and the JWT RSA
signing kay pair. This allows the user to take advantage Pulumi's feature 
set, by demonstrating the process of creating and deploying an RSA key pair
at deployment time and using the project configuration file to set config
variables, including secrets.

As part of the Bank of Sirius deployment, we deploy a cluster-wide 
[self-signed](https://cert-manager.io/docs/configuration/selfsigned/)
issuer using the cert-manager deployed above. This is then used by the 
Ingress object created to enable TLS access to the application. Note that
this Issuer can be changed out by the user, for example to use the 
[ACME](https://cert-manager.io/docs/configuration/acme/) issuer. 

In order to provide visibility into the Postgres databases that are running as part
of the application, the Prometheus Postgres data exporter will be deployed into 
the same namespace as the application and will be configured to be scraped by the 
prometheus server installed earlier.

**Note** Due to the way that Pulumi currently handles secrets, the [sirius](./sirius)
directory contains its own configuration directory [sirius/config](./sirius/config).
This directory contains an example configuration file that can be copied over
and used. The user will be prompted to add passwords to the configuration file at the
first run of the [start_all.sh](./start_all.sh) script. This is a work-around that 
will be retired as Pulumi provides better tools for hierarchical configuration files.

## Simple Load Testing

In order to help enable simple load testing, a script has been provided that uses the 
`kubectl` command to port-forward monitoring and management connections to the local
workstation. This command is [`test-foward.sh`](./extras/test-forward.sh) and is located
in the [`extras`](./extras) directory. 