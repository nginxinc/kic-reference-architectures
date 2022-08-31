# Directory

`<repository-root>/pulumi/python/kubernetes`

## Purpose

All kubernetes deployments are stored in this directory; all of these stacks
will use the [`infrastructure/kubeconfig`](../infrastructure/kubeconfig) stack as
a source of information about the kubernetes installation that is being used.

## Key Files

* [`nginx`](./nginx) NGINX related components; Ingress Controller, Service
  Mesh, App Protect, etc. Each in a separate
  directory.
* [`applications`](./applications) Applications; each in it's own directory.

## Notes

None.
