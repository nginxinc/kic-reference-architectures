## Directory

`<repository-root>/extras`

## Purpose

This directory is for files that, although important, don't have a clearly defined home. Files from this directory will
most likely be moved as the project matures.

## Key Files

- [`jwt.token`](./jwt.token) This file contains the JWT required to pull the NGINX IC from the NGINX, Inc registry.
  See [this webpage](https://docs.nginx.com/nginx-ingress-controller/installation/using-the-jwt-token-docker-secret)
  for details and examples.
- [`jenkins`](./jenkins) This directory contains sample jenkinsfiles. Note that these are not guaranteed to be production
  ready. These files are named according to the specific type of build they manage; for example, AWS, K3S, MicroK8s, Linode, Minikube and
  DO (Digital Ocean). 

## Notes

None.
