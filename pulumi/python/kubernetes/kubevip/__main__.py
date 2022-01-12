from secrets import token_bytes
from base64 import b64encode
import pulumi
import ipaddress
import os
import pulumi_kubernetes as k8s
from pulumi_kubernetes.yaml import ConfigFile
from kic_util import pulumi_config

def pulumi_kube_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kube_project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', 'kubeconfig')
    return pulumi_config.get_pulumi_project_name(kube_project_path)

def pulumi_ingress_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_project_path = os.path.join(script_dir, '..', 'nginx', 'ingress-controller')
    return pulumi_config.get_pulumi_project_name(ingress_project_path)

# Where are our manifests?
def k8_manifest_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    k8_manifest_path = os.path.join(script_dir, 'manifests', 'kube-vip-cloud-controller.yaml')
    return k8_manifest_path

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
kube_project_name = pulumi_kube_project_name()
pulumi_user = pulumi_config.get_pulumi_user()

kube_stack_ref_id = f"{pulumi_user}/{kube_project_name}/{stack_name}"
kube_stack_ref = pulumi.StackReference(kube_stack_ref_id)
kubeconfig = kube_stack_ref.get_output('kubeconfig').apply(lambda c: str(c))
kube_stack_ref.get_output('cluster_name').apply(
    lambda s: pulumi.log.info(f'Cluster name: {s}'))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller', kubeconfig=kubeconfig)

config = pulumi.Config('kubevip')
thecidr = config.require('thecidr')

thenet = ipaddress.IPv4Network(thecidr, strict=False)
therange = str(thenet[0]) + "-" + str(thenet[-1])


k8_manifest = k8_manifest_location()

kubevip = ConfigFile(
    "kubevip",
    file=k8_manifest)

# Create a config map
kube_system_kubevip_config_map = k8s.core.v1.ConfigMap("kube_systemKubevipConfigMap",
    api_version="v1",
    data={
        "cidr-global": thecidr
    },
    kind="ConfigMap",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="kubevip",
        namespace="kube-system",
    ))

