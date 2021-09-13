import base64
import os

import pulumi
from pulumi_aws import ecr

from kic_util import pulumi_config
from repository_push import RepositoryPush, RepositoryPushArgs, RepositoryCredentialsArgs


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


# Get login credentials for ECR, so that we can use it to store Docker images
def get_ecr_credentials(registry_id: str):
    credentials = ecr.get_credentials(registry_id)
    token = credentials.authorization_token
    decoded = str(base64.b64decode(token), 'utf-8')
    parts = decoded.split(':', 2)
    if len(parts) != 2:
        raise ValueError("Unexpected format for decoded ECR authorization token")
    username = pulumi.Output.secret(parts[0])
    password = pulumi.Output.secret(parts[1])
    return RepositoryCredentialsArgs(username=username, password=password)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

ecr_project_name = project_name_from_project_dir('ecr')
ecr_stack_ref_id = f"{pulumi_user}/{ecr_project_name}/{stack_name}"
ecr_stack_ref = pulumi.StackReference(ecr_stack_ref_id)
ecr_repository_url = ecr_stack_ref.require_output('repository_url')
ecr_registry_id = ecr_stack_ref.require_output('registry_id')
ecr_credentials = ecr_registry_id.apply(get_ecr_credentials)

kic_image_build_project_name = project_name_from_project_dir('kic-image-build')
kic_image_build_stack_ref_id = f"{pulumi_user}/{kic_image_build_project_name}/{stack_name}"
kick_image_build_stack_ref = pulumi.StackReference(kic_image_build_stack_ref_id)
ingress_image = kick_image_build_stack_ref.require_output('ingress_image')


def select_image_name(image):
    if 'image_name_alias' in image:
        return image['image_name_alias']
    else:
        return image['image_name']


def select_image_tag_alias(image):
    if 'image_tag_alias' in image:
        return image['image_tag_alias']
    else:
        return ''


# We default to using the image name alias because it is a more precise definition
# of the image type when we build from source.
image_name = ingress_image.apply(select_image_name)
image_tag_alias = ingress_image.apply(select_image_tag_alias)

repo_args = RepositoryPushArgs(repository_url=ecr_repository_url,
                               credentials=ecr_credentials,
                               image_id=ingress_image['image_id'],
                               image_name=image_name,
                               image_tag=ingress_image['image_tag'],
                               image_tag_alias=image_tag_alias)

# Push the images to the ECR repo
ecr_repo_push = RepositoryPush(name='ingress-controller-repository-push',
                               repository_args=repo_args)

pulumi.export('ecr_repository', ecr_repo_push)
