import os

import pulumi
from pulumi_digitalocean import KubernetesCluster, KubernetesClusterNodePoolArgs

from kic_util import pulumi_config
# Configuration details for the K8 cluster
config = pulumi.Config('digitalocean')
instance_size = config.get('instance_size')
if not instance_size:
    instance_size = 's-2vcpu-4gb'
region = config.get('region')
if not region:
    region = 'sfo3'
node_count = config.get('node_count')
if not node_count:
    node_count = 3
k8s_version = config.get('k8s_version')
if not k8s_version:
    k8s_version = '1.22.8-do.1'

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()


def container_registry_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', 'container-registry')
    return pulumi_config.get_pulumi_project_name(project_path)


# Derive our names for the cluster and the pool
resource_name = f'do-{stack_name}-cluster'
pool_name = f'do-{stack_name}-pool'

# Create a digital ocean cluster
cluster = KubernetesCluster(resource_name=resource_name,
                            region=region,
                            version=k8s_version,
                            node_pool=KubernetesClusterNodePoolArgs(
                                name=pool_name,
                                size=instance_size,
                                node_count=node_count,
                            ))

kubeconfig = cluster.kube_configs[0].raw_config

# Export the clusters' kubeconfig
pulumi.export("cluster_name", cluster.name)
pulumi.export("cluster_id", cluster.id)
pulumi.export("kubeconfig", pulumi.Output.unsecret(kubeconfig))
