## Directory

`<repository-root>/pulumi/python/tools`

## Deprecation Notice
These tools are no longer supported by the MARA team and will be removed in a future release. They *should* work
correctly, but this is not guaranteed. Any use is at your own risk.

## Purpose

This directory holds common tools that *may* be required by kubernetes installations that do not meet the minimum
requirements of MARA as checked by the [testcap.sh](../../../bin/testcap.sh) script.

These tools address two main areas:

- Ability to create persistent volumes.
- Ability to obtain an external egress IP.

Note that these tools are not specifically endorsed by the creators of MARA, and you should do your own determination of
the best way to provide these capabilities. Many kubernetes distributions have recommended approaches to solving these
problems.

To use these tools you will need to run the [kubernetes-extras.sh](../../../bin/kubernetes-extras.sh) script from the
main `bin` directory. This will walk you through the process of setting up these tools.

## Key Files

- [`common`](./common) Common directory to hold the pulumi configuration file.
- [`kubevip`](./kubevip) Install directory for the `kubevip` package. Currently WIP.
- [`metallb`](./metallb) Install directory for the `metallb` package.
- [`nfsvolumes`](./nfsvolumes) Install directory for the `nfsvolumes` package.

## Notes

Please read the comments inside the installation script, as there are some important caveats.
