from secrets import token_bytes
from base64 import b64encode
import pulumi
import os
import pulumi_kubernetes as k8s
from pulumi_kubernetes.yaml import ConfigFile
from kic_util import pulumi_config
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

# We need the kubeconfig and cluster name.
config = pulumi.Config('kubernetes')
cluster_name = config.require('cluster_name')
context_name = config.require('context_name')
kubeconfig = config.require('kubeconfig')

# Function to add namespace
def add_namespace(obj):
    obj['metadata']['namespace'] = 'nfsvols'


def pulumi_kube_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kube_project_path = os.path.join(script_dir, '..', 'common')
    return pulumi_config.get_pulumi_project_name(kube_project_path)

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
kube_project_name = pulumi_kube_project_name()
pulumi_user = pulumi_config.get_pulumi_user()

kube_stack_ref_id = f"{pulumi_user}/{kube_project_name}/{stack_name}"
kube_stack_ref = pulumi.StackReference(kube_stack_ref_id)


k8s_provider = k8s.Provider(resource_name=f'ingress-controller', kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='nfsvols',
                           metadata={'name': 'nfsvols'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

config = pulumi.Config('nfsvols')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'nfs-subdir-external-provisioner'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '4.0.14'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'nfs-subdir-external-provisioner'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner'
nfsserver = config.require('nfsserver')
nfspath = config.require('nfspath')
nfsopts = '{nolock,nfsvers=3}'

nfsvols_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "storageClass": {
            "defaultClass": True
            },
        "nfs": {
            "server": nfsserver,
            "path": nfspath,
            "mountOptions": [
                "nolock",
                "nfsvers=3"
            ]
        }
    },
    # Bumping this up - default is 300
    timeout=600,
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    cleanup_on_fail=True,
    # Provide a name for our release
    name="nfsvols",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

nfsvols_release = Release("nfsvols", args=nfsvols_release_args)

nfsvols_status = nfsvols_release.status

pulumi.export('nfsvols_status', pulumi.Output.unsecret(nfsvols_status))
