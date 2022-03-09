## Directory

`<repository-root>/extras/jenkins`

## Purpose

This directory contains several subdirectories, each of which contains a 
[Jenkinsfile](https://www.jenkins.io/doc/book/pipeline/jenkinsfile/). These are designed to be used by the  
[Jenkins](https://www.jenkins.io/) CI system to run builds of the MARA project. These can be used as-is from the 
repository using the ability of Jenkins to pull its pipeline configuration from SCM, as described in 
[this article](https://www.jenkins.io/doc/book/pipeline/getting-started/#defining-a-pipeline-in-scm ) 

Please note that these should be considered to be in a "draft" status, and should be reviewed and modified if you plan 
on using them. As always, pull requests, issues, and comments are welcome.

## Key Files

- [`AWS`](./AWS) This directory contains the [`Jenkinsfile`](./AWS/Jenkinsfile) to deploy to AWS. Please see the 
  file for additional information regarding the configuration. 
- [`DigitalOcean`](./DigitalOcean) This directory contains the [`Jenkinsfile`](./DigitalOcean/Jenkinsfile) to deploy to
  Digital Ocean. Please see the file for additional information regarding the configuration.
- [`K3S`](./K3S) This directory contains the [`Jenkinsfile`](./AWS/Jenkinsfile) to deploy to K3S. Please see the
  file for additional information regarding the configuration.
- [`MicroK8s`](./MicroK8s) This directory contains the [`Jenkinsfile`](./AWS/MicroK8s) to deploy to MicroK8s. Please see 
  the file for additional information regarding the configuration.

## Notes

None.
