# Directory

`<repository-root>/pulumi/python/kubernetes/observablity/otel-operator`

## Purpose

Deploys the OpenTelemetry Operator via a YAML manifest.

## Key Files

* [`opentelemetry-operator.yaml`](./opentelemetry-operator.yaml) This file is
  used by the Pulumi code in the directory above to deploy the OTEL operator.
  Note that this file is pulled from the 
  [OpenTelemetry Operator](https://opentelemetry.io/docs/k8s-operator/) install
  documentation. It is included as a static resource in order to manage the 
  version within MARA.

## Notes

The OTEL operator had dependencies on [cert-manager](../../certmgr)
