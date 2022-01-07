import pulumi

config = pulumi.Config('kubernetes')
cluster_name = config.require('cluster_name')
kubeconfig = config.require('kubeconfig')



# Export the clusters' kubeconfig
pulumi.export("cluster_name", cluster_name)
pulumi.export("kubeconfig",kubeconfig )
