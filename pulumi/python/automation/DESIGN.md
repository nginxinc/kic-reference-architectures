# MARA Runner Design

## Problem

When creating an infrastructure as code deployment in Pulumi, it is common to
have infrastructure that depends on the presence of other infrastructure. If
there are only few layers of dependencies, it is manageable. However, once you
pass three layers of dependencies, it becomes quite difficult to manage the
complexity of your deployment. This also results in deployment plans that are
almost incomprehensible.

This is the problem that was faced when using Pulumi to build MARA. Multiple
infrastructure services must be instantiated in order to get a working
Kubernetes environment. Moreover, once the Kubernetes is present, it needs
additional components that have a web of dependencies. For example, if we use
AWS, a full deployment looks something like the following:

```console
 ┌── infrastructure/aws
 │   ├── vpc [VPC]
 │   ├── eks [EKS]
 │   ├── ecr [ECR]
 ├── infrastructure
 │   └── kubeconfig [Kubeconfig]
 ├── kubernetes
 │   └── secrets [Secrets]
 ├── utility
 │   ├── kic-image-build [KIC Image Build]
 │   ├── kic-image-push [KIC Image Push]
 ├── kubernetes/nginx
 │   ├── ingress-controller-namespace [K8S Ingress NS]
 │   ├── ingress-controller [Ingress Controller]
 ├── kubernetes
 │   ├── logstore [Logstore]
 │   ├── logagent [Log Agent]
 │   ├── certmgr [Cert Manager]
 │   ├── prometheus [Prometheus]
 │   ├── observability [Observability]
 └── kubernetes/applications
     └── application
```

EKS cannot be instantiated until the VPC is configured. The Ingress Controller
cannot be pushed until a container registry is available. The application
cannot be started until log management, certificate management, and
observability services have been instantiated. A non-trivial Kubernetes
deployment is truly a web of dependencies!

The above example shows the dependencies for a single infrastructure provider
(AWS) that is hosting a Kubernetes environment and a container registry.
However, if the infrastructure provider is changed, then the content and order
of dependencies also changes. As such, this introduces a conditional element
that needs to be managed.

## Solution

The approach taken in MARA to mitigate the Pulumi dependency problem is to
break apart Pulumi deployments (projects) into bite sized pieces that each did
one thing. Pulumi projects pass state to each other by executing sequentially
and using
[stack references](https://www.pulumi.com/learn/building-with-pulumi/stack-references/)
.

Initially, sequential execution was implemented through a bash script that
would run `pulumi up` across a series of directories in a set order. Each
directory was a Pulumi project. If a given project had dependent state on
another project, it would use a stack reference to pull state out of the
dependent project that was previously executed. When additional infrastructure
providers were added, they were supported by different bash scripts that were
conditionally called.

This approach has proven to be unmanageable as it lacks flexibility and
configurability as well as makes adding new infrastructure providers difficult.
For example, if the content and/or ordering of infrastructure deployed to
Kubernetes needs to change based on the infrastructure provider, then this is
difficult or impossible with the bash script approach. Moreover, if you want to
read configuration and change what or how things are deployed, this also becomes
difficult using just bash scripting. Lastly, due to differences in execution
environments such as Linux and MacOS, it is difficult to write portable bash
scripting.

When Pulumi released the
[Automation API](https://www.pulumi.com/docs/guides/automation-api/)
it presented an opportunity to resolve the shortcomings mentioned above. Using
the Automation API, the MARA Runner was created to provide a framework for
gluing together multiple Pulumi Projects such that they can all be deployed as
one single unit of execution and at the same time allow for piecemeal
deployment using `pulumi up`.

The MARA Runner is a CLI program written in Python that provides the following:

* The selection of an infrastructure provider
* Configuration using configuration files that control all Pulumi projects
* Pulumi operations such as up, refresh, destroy to be propagated across all
  projects
* Visualizing which Pulumi projects will be executed for a given
  infrastructure provider

## Terms

The following terms are used repeatedly in the MARA runner. For clarity, they
are defined below.

### Pulumi Project

A Pulumi [Project](https://www.pulumi.com/docs/intro/concepts/project/) is a
folder/directory that contains a `Pulumi.yaml` file. It is a stand-alone single
unit of execution. Multiple projects execution is tied together by the MARA
Runner.

### Infrastructure Provider

The term Infrastructure provider (or provider for short) within the context of
the MARA Runner, is referring to what will be hosting a Kubernetes environment
and a container registry. Infrastructure providers are implemented as a
subclass of the [Provider](providers/base_provider.py) class. They contain a
collection references to the directories of Pulumi projects which are
categorized as either "infrastructure" or "kubernetes". The categorization of
"infrastructure" means that a project is a requirement for having a working
Kubernetes cluster and container registry.

### Execution

Execution is referring to the running of a Pulumi project by doing `pulumi up`.

### Environment Configuration

The environment configuration file by default is located at:
`<project root>/config/pulumi/environment`.
It is used to define the environment variables needed when executing a Pulumi
project. When executing Pulumi projects, the system environment is used AND the
values from the environment configuration are appended/overwritten over the
system environment. The file format is a simple key value mapping where each
line contains a single: `<KEY>=<VALUE>`.

### Stack Configuration

The stack configuration is a Pulumi native configuration file that is specific for
a single Pulumi [Stack](https://www.pulumi.com/docs/intro/concepts/stack/). The
stack configuration is located by default at
`<project root>/config/pulumi/Pulumi.<stack name>.yaml`.

## Design

Below is a rough outline of the major components of the Runner and their order
of execution.

```console
Validate         Prompt User for            Prompt User for
Configuration───►Provider Configuration────►Secrets       │
                                                          │
┌─────────────────────────────────────────────────────────┘
▼
Provider         Provider     Infrastructure
Selection ──────►Execution───►Project
                              Execution───────────────────────┐
                              │                               │
                              └─►Infrastructure Project(s)... │
                                                              │
┌─────────────────────────────────────────────────────────────┘
▼
Write Secrets    Kubernetes
to Kubernetes───►Project
                 Execution
                 │
                 └─►Kubernetes Projects(s)...
```

### Assumptions

There are some assumptions for how Pulumi is used by the Runner that differ
from what is possible using Pulumi directly.

* All Pulumi projects use the same name for their stack
* All Pulumi projects use the same stack configuration file (except the
  [secrets](../kubernetes/secrets) project)
* All secrets are stored encrypted in the [secrets](../kubernetes/secrets)
  project and loaded into Kubernetes as secrets
* Infrastructure providers cannot be changed on a stack after the first run,
  and as such a new stack will need to be made when using multiple
  infrastructure providers
* Stack references are used to pass state between Pulumi projects
* The configuration key `kubernetes:infra_type` contains the name of the
  infrastructure provider as used in the Runner
* If there is any error running a Pulumi project, the Runner will exit, and it
  is up to the user to try again or fix the issue
* The order of execution may change between different infrastructure providers
* All required external programs are installed
* The Runner is invoked from a virtual environment as set up by the
  [setup_venv.sh](../../../bin/setup_venv.sh) script
* After a Kubernetes cluster is stood up, the relevant configuration files are
  added to the system such that it can be managed with the `kubectl` tool

### Configuration

The initial phase of the Runner's execution reads, parses and validates the
environment and stack configuration files. If the stack configuration is missing
or empty, it is assumed that it is the first time starting up the environment
and the user is prompted for required configuration parameters.

After configuration validation, the user is prompted to input any required
secrets that are not currently persisted. These secrets are encrypted using
Pulumi's local secret handling and stored in ciphertext in the
[secrets](../kubernetes/secrets) project.

### Provider

After configuration has completed, a provider is selected based on the options
specified by the user when invoking the Runner. This provider is used as the
source of data for what Pulumi projects are executed and in what order. When
standing up an environment, the provider executes first the Pulumi projects that
are categorized as "infrastructure". Infrastructure in this context means that
these projects are required to have been executed successfully
in order to have a working Kubernetes cluster and container registry.

A Pulumi project reference within a provider may optionally have an
`on_success` event registered which is run when the project executes
successfully. Typically, these events do things like add configuration for a
cluster to the kubectl configuration directory.

After the infrastructure projects have completed executing, the Runner then
executes the [secrets](../kubernetes/secrets) project which stores the locally
encrypted secrets as
[Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
on the newly created Kubernetes cluster.

Once the required secrets are in place, the Runner then executes all the
projects categorized as "kubernetes" including the final application to be
deployed.

At this point, the application should be deployed.
