from secrets import token_bytes
from base64 import b64encode
import pulumi
import ipaddress
import os
import pulumi_kubernetes as k8s
from pulumi_kubernetes.yaml import ConfigFile
from kic_util import pulumi_config

# Function to add namespace
def add_namespace(obj):
    obj['metadata']['namespace'] = 'metallb-system'
    
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
    k8_manifest_path = os.path.join(script_dir, 'manifests', 'metallb.yaml')
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

# Create the namespace for metallb
ns = k8s.core.v1.Namespace(resource_name='metallb-system',
                           metadata={'name': 'metallb-system'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

config = pulumi.Config('metallb')
thecidr = config.require('thecidr')

thenet = ipaddress.IPv4Network(thecidr, strict=False)
therange = str(thenet[0]) + "-" + str(thenet[-1])


k8_manifest = k8_manifest_location()

metallb = ConfigFile(
    "metallb",
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns]),
    file=k8_manifest)

# Generate a secret
secretkey = b64encode(token_bytes(128)).decode()

# Create a secret in K8
metallb_system_memberlist_secret = k8s.core.v1.Secret("metallb_systemMemberlistSecret",
    api_version="v1",
    data={
        "secretkey": secretkey
    },
    kind="Secret",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="memberlist",
        namespace="metallb-system",
    ),
    opts=pulumi.ResourceOptions(depends_on=[ns])
    )

##therange = "192.168.216.101-192.168.216.110"


# Create a config map
metallb_system_config_config_map = k8s.core.v1.ConfigMap("metallb_systemConfigConfigMap",
    api_version="v1",
    kind="ConfigMap",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        namespace="metallb-system",
        name="config",
    ),
    opts=pulumi.ResourceOptions(depends_on=[ns]),
    data={
        "config": """address-pools:
    - name: default
      protocol: layer2
      addresses:
      - """ + therange,
    }
    )

