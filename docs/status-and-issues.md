# Overview

This project is a work in progress and as such there are a number of areas for improvement. As of this writing, the
development process is primarily using AWS and MicroK8s for development and testing. However, there is manual testing
being undertaken on several other K8 providers. Current information on known issues, bugs, and open feature requests can
be seen on the [Project Github Issue Page](https://github.com/nginxinc/kic-reference-architectures/issues).
Additionally, the core contributors are available for discussion on the
[Project Github Discussion Page](https://github.com/nginxinc/kic-reference-architectures/discussions)

## Provider Status

This matrix lists out the currently tested configurations, along with any notes on that configuration. The matrix
includes the following:

- K8 Provider: The name of the provider
- Infrastructure Support: Does the project stand up the infrastructure with this provider?
- Ingress Controller Options: What are the options for IC deployment?
- FQDN/IP: How does the project handle the IP addressing and FQDN for the certificates?
- Notes: Any additional information on the provider / project interaction.

All of these configurations use Pulumi code within Python as the Infrastructure as Code (IaC) manager.

| K8 Provider     | Tested | Infrastructure Support      | IC Options              | FQDN/IP         | Notes                                            |
|-----------------|--------|-----------------------------|-------------------------|-----------------|--------------------------------------------------|
| AWS EKS         | Yes    | Full Infrastructure Standup | Build, Pull (uses ECR)  | Provided        |                                                  |
| Azure AKS       | Yes    | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) |                                                  |
| Google GKE      | Yes    | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) |                                                  |
| MicroK8s        | Yes    | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) | Storage, DNS, and Metallb need to be Enabled (4) |
| Harvester/RKE2  | Yes    | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) | Needs Storage, K8 LoadBalancer                   |
| K3S             | Yes    | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) | Needs Storage, K8 LoadBalancer                   |
| Rancher Desktop | No     | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) | Needs Storage, K8 LoadBalancer                   |
| Minikube        | No     | Kubeconfig Only (3)         | NGINX Plus (w/ JWT) (1) | Manual FQDN (2) | Needs Storage, K8 LoadBalancer                   |

### Notes:
1. The NGINX IC build/deploy process is currently under active development and support for IC will be standardized across
all providers. Follow [#81](https://github.com/nginxinc/kic-reference-architectures/issues/81) and 
[#86](https://github.com/nginxinc/kic-reference-architectures/issues/86) for details.
2. The process via which the IP and FQDN are created and used is currently under active development, and will be streamlined
and standardized for all providers. Follow [#82](https://github.com/nginxinc/kic-reference-architectures/issues/82) for
details.
3. The initial deployment was entirely built to work with AWS. As part of our reorganization the ability to use a 
kubeconfig file was added, along with the necessary configuration to support additional standup options. This is currently
in active development and will result in this process being streamlined for these additional environments. Please follow
[#80](https://github.com/nginxinc/kic-reference-architectures/issues/80) for details.
4. We are currently using filebeat as our logging agent. This deployment requires that the correct paths to the container
log directory are present in the deployment data. We have discovered that this differs based on the K8 provider. Please
see [#76](https://github.com/nginxinc/kic-reference-architectures/issues/76) for more detail.

## Known Issues / Caveats
1. Currently, the use of the Elastic tooling has shown to be problematic under heavy load, with containers falling over
and causing disruptions. Please see the tuning variables in the configuration file to adjust the number of replicas 
deployed for the Elastic logstore to tune to your environment.
2. The default Helm timeout is 5 minutes, which is acceptable for most managed clouds but tends to be too short for 
single-vm or workstation deployments. Please see the configuration file variables to adjust the helm timeout as required
for your environment.
3. When load testing the Bank of Sirius using Locust, you will likely see a high failure rate as you increase the max
users and spawn rate. This is "normal" and is an area we want to expose and explore for troubleshooting, determining
which metrics/traces are helpful, etc.
4. The most common failure modes for non-cloud environments tend towards the following failures:
   1. Unable to provision persistent storage; correct by ensuring you have a persistent volue provider and can provision a volume.
   2. Unable to provision an External IP; correct by adding an IP provider such as kubevip or metallb.
   3. Resource starvation (not enough CPU, Memory); expand the size of the VM or detune the environment.
   4. Timeouts in helm; increase the helm timeout in the configuration file.
5. If you are using a cloud provider with timed credentials, such as AWS, one failure mode that can arise is when the 
credentials expire. This will result in a number of strange and seemingly confusing errors. Double check to make sure that
the credentials are valid.
6. Currently, the build/test process is highly manual. This will be addressed in the future.
