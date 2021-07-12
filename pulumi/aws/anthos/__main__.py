import os

import pulumi
import pulumi_kubernetes as k8s
import pydevd_pycharm
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


def anthos_manifests_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    anthos_manifests_path = os.path.join(script_dir, 'manifests', '*.yaml')
    return anthos_manifests_path


def ingress_manifests_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_manifests_path = os.path.join(script_dir, 'ingress', '*.yaml')
    return ingress_manifests_path


def add_namespace(obj):
    obj['metadata']['namespace'] = 'boa'


def add_hostname(obj):
    pydevd_pycharm.settrace('localhost', port=9341, stdoutToServer=True, stderrToServer=True)
    if obj['kind'] == "Ingress" and obj['metadata']['name'] == 'bankofanthos':
        obj['spec']['rules'][0]['host'] = 'demo.example.com'


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
anthos_manifests = anthos_manifests_location()

boa = ConfigGroup(
    'boa',
    files=[anthos_manifests],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns])
)


boa_in = k8s.networking.v1beta1.Ingress("boaIngress",
    api_version="networking.k8s.io/v1beta1",
    kind="Ingress",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="bankofanthos",
        namespace=ns
    ),
    spec=k8s.networking.v1beta1.IngressSpecArgs(
        ingress_class_name="nginx",
        rules=[k8s.networking.v1beta1.IngressRuleArgs(
            host=lb_ingress_hostname,
            http=k8s.networking.v1beta1.HTTPIngressRuleValueArgs(
                paths=[k8s.networking.v1beta1.HTTPIngressPathArgs(
                    path="/",
                    backend=k8s.networking.v1beta1.IngressBackendArgs(
                        service_name="frontend",
                        service_port=80,
                    ),
                )],
            ),
        )],
    ))
