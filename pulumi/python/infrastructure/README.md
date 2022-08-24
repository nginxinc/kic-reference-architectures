# Directory

`<repository-root>/python/pulumi/infrastructure`

## Purpose

Holds all infrastructure related files.

## Key Files

* [`aws`](./aws) Files to stand up a K8 cluster in AWS using VPC, EKS, and ECR.
* [`digitalocean`](./digitalocean) Files to stand up a K8 cluster in
   DigitalOcean using DO Managed K8s.
* [`linode`](./linode) Files to stand up a K8 cluster in Linode using Linode
  Kubernetes Engine.
* [`kubeconfig`](./kubeconfig) Files to allow users to connect to any kubernetes
  installation that can be specified via a `kubeconfig` file.

## Notes

The `kubeconfig` project is intended to serve as a shim between infrastructure
providers and the rest of the project. For example, even if you use the AWS
logic you will still use the logic inside the `kubeconfig` stack as part of the
process. Additional infrastructures added will need to follow this pattern.
