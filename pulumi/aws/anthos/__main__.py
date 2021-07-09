import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.yaml import ConfigGroup
from kic_util import pulumi_config


def pulumi_eks_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eks_project_path = os.path.join(script_dir, '..', 'eks')
    return pulumi_config.get_pulumi_project_name(eks_project_path)


def pulumi_ingress_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_project_path = os.path.join(script_dir, '..', 'kic-helm-chart')
    return pulumi_config.get_pulumi_project_name(ingress_project_path)

def add_namespace(obj):
    obj['metadata']['namespace'] = 'boa'


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

ingress_project_name = pulumi_ingress_project_name()
ingress_stack_ref_id = f"{pulumi_user}/{ingress_project_name}/{stack_name}"
ingress_stack_ref = pulumi.StackReference(ingress_stack_ref_id)
lb_ingress_hostname = ingress_stack_ref.get_output('lb_ingress_hostname')

ns = k8s.core.v1.Namespace(resource_name='boa',
                           metadata={'name': 'boa'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

# Create resources for the Bank of Anthos
boa = ConfigGroup(
    'boa',
    files=['manifests/*.yaml'],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns])
)

# Create resources from standard Kubernetes guestbook YAML example.
boain = ConfigGroup(
    'boain',
    files=['ingress/*.yaml'],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns])
)
