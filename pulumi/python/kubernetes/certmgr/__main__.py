import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config


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

ns = k8s.core.v1.Namespace(resource_name='cert-manager',
                           metadata={'name': 'cert-manager'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

config = pulumi.Config('certmgr')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'cert-manager'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = 'v1.7.0'
helm_repo_name = config.get('certmgr_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'jetstack'

helm_repo_url = config.get('certmgr_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://charts.jetstack.io'

certmgr_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "installCRDs": True
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
    name="certmgr",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)
certmgr_release = Release("certmgr", args=certmgr_release_args)

status = certmgr_release.status
pulumi.export("certmgr_status", status)
