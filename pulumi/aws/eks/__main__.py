import os
import collections

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks

from kic_util import pulumi_config
import iam

VPCDefinition = collections.namedtuple('VPCDefinition', ['vpc_id', 'public_subnet_ids', 'private_subnet_ids'])


def pulumi_vpc_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    vpc_project_path = os.path.join(script_dir, '..', 'vpc')
    return pulumi_config.get_pulumi_project_name(vpc_project_path)


def retrieve_vpc_and_subnets(vpc) -> VPCDefinition:
    pulumi.log.info(f"vpc id: {vpc['id']}")

    _public_subnet_ids = aws.ec2.get_subnet_ids(vpc_id=vpc['id'],
                                                tags={"Project": "vpc-sample-cluster",
                                                      "Stack": stack_name,
                                                      "kubernetes.io/role/elb": "1"}).ids
    pulumi.log.info(f"public subnets: {_public_subnet_ids}")

    _private_subnet_ids = aws.ec2.get_subnet_ids(vpc_id=vpc['id'],
                                                 tags={"Project": "vpc-sample-cluster",
                                                       "Stack": stack_name,
                                                       "kubernetes.io/role/internal-elb": "1"}).ids
    pulumi.log.info(f"public subnets: {_private_subnet_ids}")

    return VPCDefinition(vpc_id=vpc['id'], public_subnet_ids=_public_subnet_ids, private_subnet_ids=_private_subnet_ids)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
vpc_project_name = pulumi_vpc_project_name()
pulumi_user = pulumi_config.get_pulumi_user()
aws_config = pulumi.Config("aws")
aws_profile = aws_config.get("profile")

provider_credential_opts = {}
if aws_profile is not None:
    pulumi.log.info(f"aws {aws_profile} profile")
    provider_credential_opts["profileName"] = aws_profile

stack_ref_id = f"{pulumi_user}/{vpc_project_name}/{stack_name}"
stack_ref = pulumi.StackReference(stack_ref_id)
vpc_definition: pulumi.Output[VPCDefinition] = stack_ref.get_output('vpc').apply(retrieve_vpc_and_subnets)

min_size = 3
max_size = 12
desired_capacity = 3
instance_type = 't2.medium'

node_group_opts = eks.ClusterNodeGroupOptionsArgs(
    min_size=min_size,
    max_size=max_size,
    desired_capacity=desired_capacity,
    instance_type=instance_type,
)

instance_profile = aws.iam.InstanceProfile(
    resource_name=f'node-group-profile-{project_name}-{stack_name}',
    role=iam.ec2_role
)

cluster_args = eks.ClusterArgs(
    node_group_options=node_group_opts,
    vpc_id=vpc_definition.vpc_id,
    public_subnet_ids=vpc_definition.public_subnet_ids,
    private_subnet_ids=vpc_definition.private_subnet_ids,
    service_role=iam.eks_role,
    create_oidc_provider=True,
    version='1.19',
    provider_credential_opts=provider_credential_opts,
    tags={"Project": project_name, "Stack": stack_name}
)

# Create an EKS cluster with the default configuration.
cluster = eks.Cluster(resource_name=f"{project_name}-{stack_name}",
                      args=cluster_args)

# Export the clusters' kubeconfig
pulumi.export("cluster_name", cluster.eks_cluster.name)
pulumi.export("kubeconfig", cluster.kubeconfig)
