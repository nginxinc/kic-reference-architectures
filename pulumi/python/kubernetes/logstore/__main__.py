import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi import Output
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config

config = pulumi.Config('logstore')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'elasticsearch'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '19.4.4'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'bitnami'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://charts.bitnami.com/bitnami'

#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get_int('helm_timeout')
if not helm_timeout:
    helm_timeout = 300

#
# Define the default replicas for the Elastic components. If not set we default to one copy of each - master, ingest,
# data, and coordinating. This is ideal for smaller installations - K3S, Microk8s, minikube, etc. However, it may fall
# over when running with a high volume of logs.
#
master_replicas = config.get('master_replicas')
if not master_replicas:
    master_replicas = 1

ingest_replicas = config.get('ingest_replicas')
if not ingest_replicas:
    ingest_replicas = 1

data_replicas = config.get('data_replicas')
if not data_replicas:
    data_replicas = 1

coordinating_replicas = config.get('coordinating_replicas')
if not coordinating_replicas:
    coordinating_replicas = 1


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace('logstore',
                           metadata={'name': 'logstore'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

elastic_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "master": {
            "replicas": master_replicas,
            "resources": {
                "requests": {},
                "limits": {}
            },
        },
        "coordinating": {
            "replicas": coordinating_replicas
        },
        "data": {
            "replicas": data_replicas,
            "resources": {
                "requests": {},
                "limits": {}
            },
        },
        "global": {
            "kibanaEnabled": True
        },
        "ingest": {
            "enabled": True,
            "replicas": ingest_replicas,
            "resources": {
                "requests": {},
                "limits": {}
            },
        }
    },
    # User configurable timeout
    timeout=helm_timeout,
    # By default, Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    # If we fail, clean up 
    cleanup_on_fail=True,
    # Provide a name for our release
    name="elastic",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

elastic_release = Release("elastic", args=elastic_release_args)

elastic_rname = elastic_release.status.name

elastic_fqdn = Output.concat(elastic_rname, "-elasticsearch.logstore.svc.cluster.local")
kibana_fqdn = Output.concat(elastic_rname, "-kibana.logstore.svc.cluster.local")

pulumi.export('elastic_hostname', pulumi.Output.unsecret(elastic_fqdn))
pulumi.export('kibana_hostname', pulumi.Output.unsecret(kibana_fqdn))

# Print out our status
estatus = elastic_release.status
pulumi.export("logstat_status", estatus)
