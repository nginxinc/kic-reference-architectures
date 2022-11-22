import pulumi
from pulumi_aws import ecr

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()

# Build a new ECR instance for storing KIC Docker images
ecr_repo = ecr.Repository(name=f'ingress-controller-{stack_name}',
                          resource_name=f'nginx-ingress-repository-{stack_name}',
                          image_tag_mutability="MUTABLE",
                          force_delete=True,
                          tags={"Project": project_name, "Stack": stack_name})

pulumi.export('repository_url', ecr_repo.repository_url)
pulumi.export('registry_id', ecr_repo.registry_id)
