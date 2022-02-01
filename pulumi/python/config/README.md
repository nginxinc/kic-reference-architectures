## Directory

`<repository-root>/pulumi/python/config`

## Purpose

This directory is used for configuration management in Pulumi. In previous versions of this project, the
`vpc` directory was used to manage writes to the configuration file. This is required because you can only run
the `pulumi config` command if you have a `Pulumi.yaml` somewhere in your directory or above that allows you to use the
Pulumi tooling.

Why not use each stack directory as it's own configuration? Using different directories will result in failures
encrypting/decrypting the values in the main configuration file if different stacks are used. This is a stopgap
workaround that will be obsoleted at such time that Pulumi provides nested/included configuration files.

## Key Files

- [`Pulumi.yaml`](./Pulumi.yaml) This file tells the `pulumi` command where to find it's virtual envrionment and it's
  configuration.

## Notes

Once Pulumi adds nested configuration files to the product we should be able to remove this work-around.

