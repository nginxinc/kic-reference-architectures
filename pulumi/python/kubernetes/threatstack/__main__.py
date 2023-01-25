import os
import pulumi
import pulumi_kubernetes as k8s
from pulumi import Output
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.core.v1 import Secret
from typing import Mapping
import base64

from kic_util import pulumi_config

def project_name_from_infrastructure_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eks_project_path = os.path.join(
        script_dir, '..', '..', 'infrastructure', 'kubeconfig')
    return pulumi_config.get_pulumi_project_name(eks_project_path)

def project_name_from_kubernetes_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)

def extract_password_from_k8s_secrets(secrets: Mapping[str, str], secret_name: str) -> str:
    if secret_name not in secrets:
        raise f'Secret [{secret_name}] not found in Kubernetes secret store'
    base64_string = secrets[secret_name]
    byte_data = base64.b64decode(base64_string)
    password = str(byte_data, 'utf-8')
    return password

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
k8_project_name = project_name_from_infrastructure_dir()
pulumi_user = pulumi_config.get_pulumi_user()

k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.get_output('kubeconfig').apply(lambda c: str(c))
k8_stack_ref.get_output('cluster_name').apply(
    lambda s: pulumi.log.info(f'Cluster name: {s}'))

secrets_project_name = project_name_from_kubernetes_dir('secrets')
secrets_stack_ref_id = f"{pulumi_user}/{secrets_project_name}/{stack_name}"
secrets_stack_ref = pulumi.StackReference(secrets_stack_ref_id)
pulumi_secrets = secrets_stack_ref.require_output('pulumi_secrets')

k8s_provider = k8s.Provider(resource_name='ingress-controller')

config = pulumi.Config('threatstack')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'threatstack-agent'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '3.2.0'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'threatstack'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://pkg.threatstack.com/helm'

#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get_int('helm_timeout')
if not helm_timeout:
    helm_timeout = 300

#
# Sumo variables; these are all required; we're going to use the secrets project
# to retrieve these variables....
#
threatstack_secrets = Secret.get(resource_name='pulumi-secret-threatstack',
                            id=pulumi_secrets['threatstack'],
                            opts=pulumi.ResourceOptions(provider=k8s_provider)).data
agentDeployKey = pulumi.Output.unsecret(threatstack_secrets).apply(
    lambda secrets: extract_password_from_k8s_secrets(secrets, 'agentDeployKey'))

ns = k8s.core.v1.Namespace(resource_name='threatstack',
                           metadata={'name': 'threatstack'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

threatstack_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "agentDeployKey": agentDeployKey
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
    name="threatstack",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

threatstack_release = Release("threatstack", args=threatstack_release_args)

# Print out our status
estatus = threatstack_release.status
