import os
import pulumi
import pulumi_linode as linode

# Configuration details for the K8 cluster
config = pulumi.Config('linode')

api_token = config.get('token') or \
            config.get_secret('token') or \
            os.getenv('LINODE_TOKEN') or \
            os.getenv('LINODE_CLI_TOKEN')

# For whatever reason, the Linode provider does not pickup the token from the
# stack configuration nor from the environment variables, so we do that work
# here.
provider = linode.Provider(resource_name='linode_provider', token=api_token)

instance_type = config.require('instance_type')
region = config.require('region')
node_count = config.require_int('node_count')
k8s_version = config.require('k8s_version')
k8s_ha = config.require_bool('k8s_ha')

stack = pulumi.get_stack()
resource_name = f'lke-{stack}-cluster'

# Create a linode cluster
cluster = linode.LkeCluster(resource_name=resource_name,
                            k8s_version=k8s_version,
                            control_plane=linode.LkeClusterControlPlaneArgs(
                                high_availability=k8s_ha),
                            label=f'MARA [{stack}]',
                            pools=[linode.LkeClusterPoolArgs(
                                count=node_count,
                                type=instance_type,
                            )],
                            region=region,
                            tags=["mara"],
                            opts=pulumi.ResourceOptions(provider=provider))

# Export the clusters' kubeconfig
pulumi.export("cluster_name", resource_name)
pulumi.export("cluster_id", cluster.id)
pulumi.export("kubeconfig", cluster.kubeconfig)
