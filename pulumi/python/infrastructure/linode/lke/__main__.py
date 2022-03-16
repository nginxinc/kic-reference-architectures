import collections
import base64

import pulumi
import pulumi_linode as linode
from kic_util import pulumi_config

# Configuration details for the K8 cluster
config = pulumi.Config('lke')
instance_size = config.get('instance_size')
if not instance_size:
    instance_size = 'g6-standard-4'
region = config.get('region')
if not region:
    region = 'us-west'
node_count = config.get('node_count')
if not node_count:
    node_count = 3
k8s_version = config.get('k8s_version')
if not k8s_version:
    k8s_version = '1.22'
k8s_ha = config.get('k8s_ha')
if not k8s_ha:
    k8s_ha = True

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

# Derive our names for the cluster and the pool
resource_name = "lke-" + stack_name + "-cluster"

# Create a linode cluster
cluster = linode.LkeCluster(resource_name,
                            k8s_version=k8s_version,
                            control_plane=linode.LkeClusterControlPlaneArgs(
                                high_availability=k8s_ha),
                            label=resource_name,
                            pools=[linode.LkeClusterPoolArgs(
                                count=node_count,
                                type=instance_size,
                            )],
                            region=region,
                            tags=["mara"])

# Export the clusters' kubeconfig
pulumi.export("cluster_name", resource_name)
pulumi.export("cluster_id", cluster.id)
pulumi.export("kubeconfig", cluster.kubeconfig)
