import collections
import os

import pulumi
import pulumi_digitalocean as docean
from kic_util import pulumi_config

# Configuration details for the K8 cluster
config = pulumi.Config('domk8s')
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
    k8s_version = '1.21.11-do.0'

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

# Derive our names for the cluster and the pool
resource_name = "do-" + stack_name + "-cluster"
pool_name = "do-" + stack_name + "-pool"


# Create a digital ocean cluster
cluster = docean.KubernetesCluster(resource_name=resource_name,
                                   region=region,
                                   version=k8s_version,
                                   node_pool=docean.KubernetesClusterNodePoolArgs(
                                       name=pool_name,
                                       size=instance_size,
                                       node_count=node_count,
                                   ))

# Export the clusters' kubeconfig
pulumi.export("cluster_name", resource_name)
pulumi.export("cluster_id", cluster.id)
pulumi.export("kubeconfig", pulumi.Output.unsecret(cluster.kube_configs[0].raw_config))
