# Directory

`<repository-root>/pulumi/python/kubernetes/observablity/otel-operator`

## Purpose

Deploys the OpenTelemetry Operator via a YAML manifest.

## Key Files

* [`opentelemetry-operator.yaml`](./opentelemetry-operator.yaml) This file is
  used by the Pulumi code in the directory above to deploy the OTEL operator.

## Notes

The OTEL operator had dependencies on [cert-manager](../../certmgr)
