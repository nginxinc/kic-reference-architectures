# Directory

`<repository-root>/config/pulumi`

## Purpose

This directory contains the yaml configuration files used for the pulumi
installation.

## Key Files

* [`Pulumi.stackname.yaml.example`](./Pulumi.stackname.yaml.example) Contains
  the list of variables that this installation understands.
* [`environmenet`](./environment) Created at runtime; this file contains details
  about the environment including the stack name, and the ASW profile and region
  (if deploying in AWS).
* `Pulumi.YOURSTACK.yaml` Contains the list of variables associated with the
  stack with the name YOURSTACK. This configuration will be created at the first
  run for the named stack, but it can be created in advance with an editor.

## Notes

Many of the variables have defaults that are enforced through the Pulumi code
for each project, however there are certain variables that are required. When
the process reaches one of these variables and it is not set the process will
abort with an error message.
