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
    chart_version = '17.6.2'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'bitnami'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://charts.bitnami.com/bitnami'


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

eks_project_name = project_name_from_project_dir('kubeconfig')
eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='logstore',
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
            "replicas": 3,
            "resources": {
                "requests": {},
                "limits": {}
            },
        },
        "coordinating": {
            "replicas": 2
        },
        "data": {
            "replicas": 3,
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
            "replicas": 2,
            "resources": {
                "requests": {},
                "limits": {}
            },
        }
    },
    # Bumping this up - default is 300
    timeout=600,
    # By default Release resource will wait till all created resources
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

elastic_fqdn = Output.concat(elastic_rname, "-coordinating-only.logstore.svc.cluster.local")
kibana_fqdn = Output.concat(elastic_rname, "-kibana.logstore.svc.cluster.local")

pulumi.export('elastic_hostname', pulumi.Output.unsecret(elastic_fqdn))
pulumi.export('kibana_hostname', pulumi.Output.unsecret(kibana_fqdn))

# Print out our status
estatus = elastic_release.status
pulumi.export("logstat_status", estatus)
