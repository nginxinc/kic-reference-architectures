import pulumi
import os
from kic_util import pulumi_config


config = pulumi.Config('kubernetes')

# For AWS
def aws_project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', 'aws', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)

# Are we doing standalone or AWS?
infra_type = config.require('infra_type')
if infra_type == 'AWS':
    stack_name = pulumi.get_stack()
    project_name = pulumi.get_project()
    pulumi_user = pulumi_config.get_pulumi_user()

    eks_project_name = aws_project_name_from_project_dir('eks')
    eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
    eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
    kubeconfig = eks_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
    #kubeconfig = config.require('kubeconfig')
    cluster_name = eks_stack_ref.require_output('cluster_name').apply(lambda c: str(c))
    #
    # Export the clusters' kubeconfig
    #
    pulumi.export("cluster_name", cluster_name)
    pulumi.export("kubeconfig", kubeconfig)
else:
    #
    # Get the cluster name and the config
    #
    cluster_name = config.require('cluster_name')
    kubeconfig = config.require('kubeconfig')
    #
    # Export the clusters' kubeconfig
    #
    pulumi.export("cluster_name", cluster_name)
    pulumi.export("kubeconfig",kubeconfig)
