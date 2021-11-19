import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.yaml import ConfigGroup

from kic_util import pulumi_config

# Removes the status field from the Nginx Ingress Helm Chart, so that i#t is
# compatible with the Pulumi Chart implementation.
def remove_status_field(obj):
    if obj['kind'] == 'CustomResourceDefinition' and 'status' in obj:
        del obj['status']

def pulumi_eks_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eks_project_path = os.path.join(script_dir, '..', 'eks')
    return pulumi_config.get_pulumi_project_name(eks_project_path)


def pulumi_ingress_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_project_path = os.path.join(script_dir, '..', 'kic-helm-chart')
    return pulumi_config.get_pulumi_project_name(ingress_project_path)


def otel_operator_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    otel_operator_path = os.path.join(script_dir, 'otel-operator', '*.yaml')
    return otel_operator_path

def otel_deployment_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    otel_deployment_path = os.path.join(script_dir, 'otel-objects', '*.yaml')
    return otel_deployment_path

def add_namespace(obj):
    obj['metadata']['namespace'] = 'observability'


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
eks_project_name = pulumi_eks_project_name()
pulumi_user = pulumi_config.get_pulumi_user()

eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.get_output('kubeconfig').apply(lambda c: str(c))
eks_stack_ref.get_output('cluster_name').apply(
    lambda s: pulumi.log.info(f'Cluster name: {s}'))

k8s_provider = k8s.Provider(resource_name=f'ingress-setup-sample', kubeconfig=kubeconfig)

# Create the namespace
ns = k8s.core.v1.Namespace(resource_name='observability',
                           metadata={'name': 'observability'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

# Config Manifests: OTEL operator
otel_operator = otel_operator_location()

otel_op = ConfigGroup(
    'otel-op',
    files=[otel_operator],
    transformations=[remove_status_field], # Need to review w/ operator
    opts=pulumi.ResourceOptions(depends_on=[ns])
)

# Config Manifests: OTEL components
otel_deployment = otel_deployment_location()

otel_dep = ConfigGroup(
    'otel-dep',
    files=[otel_deployment],
    transformations=[add_namespace, remove_status_field], # Need to review w/ operator
    opts=pulumi.ResourceOptions(depends_on=[ns,otel_op])
)


