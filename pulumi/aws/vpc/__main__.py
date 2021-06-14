import pulumi

from pulumi_aws import ec2, get_availability_zones

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()

vpc = ec2.Vpc(resource_name=f"eks-{project_name}-{stack_name}",
              cidr_block="10.100.0.0/16",
              enable_dns_support=True,
              enable_dns_hostnames=True,
              instance_tenancy='default',
              tags={"Project": project_name,
                    "Stack": stack_name})

igw = ec2.InternetGateway(resource_name=f'vpc-ig-{project_name}-{stack_name}',
                          vpc_id=vpc.id,
                          tags={"Project": project_name,
                                "Stack": stack_name})

route_table = ec2.RouteTable(resource_name=f'vpc-route-table-{project_name}-{stack_name}',
                             vpc_id=vpc.id,
                             routes=[ec2.RouteTableRouteArgs(
                                 cidr_block='0.0.0.0/0',
                                 gateway_id=igw.id)],
                             tags={"Project": project_name,
                                   "Stack": stack_name})

azs = get_availability_zones(state="available")

public_subnets = []
private_subnets = []

for i, az in enumerate(azs.names):
    public_subnet_addr = i
    subnet = ec2.Subnet(resource_name=f'{az}-k8s-public-{project_name}-{stack_name}',
                        availability_zone=az,
                        vpc_id=vpc.id,
                        cidr_block=f"10.100.{public_subnet_addr}.0/24",
                        map_public_ip_on_launch=True,
                        tags={"Project": project_name,
                              "Stack": stack_name,
                              "kubernetes.io/role/elb": "1"})
    ec2.RouteTableAssociation(f"route-table-assoc-public-{az}",
                              route_table_id=route_table.id,
                              subnet_id=subnet.id)
    public_subnets.append(subnet)

for i, az in enumerate(azs.names):
    private_subnet_addr = (i + 1) * 16
    subnet = ec2.Subnet(resource_name=f"{az}-k8s-private-{project_name}-{stack_name}",
                        availability_zone=az,
                        vpc_id=vpc.id,
                        cidr_block=f"10.100.{private_subnet_addr}.0/20",
                        tags={"Project": project_name,
                              "Stack": stack_name,
                              "kubernetes.io/role/internal-elb": "1"},
                        map_public_ip_on_launch=False)
    ec2.RouteTableAssociation(resource_name=f"route-table-assoc-private-{az}-{project_name}-{stack_name}",
                              route_table_id=route_table.id,
                              subnet_id=subnet.id)
    private_subnets.append(subnet)

eks_security_group = ec2.SecurityGroup(resource_name=f'eks-cluster-sg-{project_name}-{stack_name}',
                                       vpc_id=vpc.id,
                                       description="Allow all HTTP(s) traffic to EKS Cluster",
                                       tags={"Project": project_name,
                                             "Stack": stack_name},
                                       ingress=[
                                           ec2.SecurityGroupIngressArgs(
                                               cidr_blocks=['0.0.0.0/0'],
                                               from_port=443,
                                               to_port=443,
                                               protocol='tcp',
                                               description='Allow pods to communicate with the cluster API Server.'),
                                           ec2.SecurityGroupIngressArgs(
                                               cidr_blocks=['0.0.0.0/0'],
                                               from_port=80,
                                               to_port=80,
                                               protocol='tcp',
                                               description='Allow internet access to pods')])

pulumi.export("azs", azs)
pulumi.export("vpc", vpc)
