import importlib
import os
import pulumi
from pulumi import Output
from kic_util import pulumi_config
from registries.base_registry import ContainerRegistry

from repository_push import RepositoryPush, RepositoryPushArgs


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


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


def select_image_id(image):
    if 'image_id' not in image or not image['image_id']:
        raise ValueError(f'no image id found in kic-image-build-stack: {image}')
    return image['image_id']


def select_image_tag(image):
    if 'image_tag' not in image or not image['image_tag']:
        raise ValueError(f'no image tag found in kic-image-build-stack: {image}')
    return image['image_tag']


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()
k8s_config = pulumi.Config('kubernetes')

kic_image_build_project_name = project_name_from_project_dir('kic-image-build')
kic_image_build_stack_ref_id = f"{pulumi_user}/{kic_image_build_project_name}/{stack_name}"
kick_image_build_stack_ref = pulumi.StackReference(kic_image_build_stack_ref_id)
ingress_image = kick_image_build_stack_ref.require_output('ingress_image')

# We default to using the image name alias because it is a more precise definition
# of the image type when we build from source.
image_name = ingress_image.apply(select_image_name)
image_tag_alias = ingress_image.apply(select_image_tag_alias)
image_id = ingress_image.apply(select_image_id)
image_tag = ingress_image.apply(select_image_tag)


def push_to_container_registry(container_registry: ContainerRegistry) -> RepositoryPush:
    if container_registry.login_to_registry():
        repo_args = RepositoryPushArgs(repository_url=container_registry.registry_url,
                                       image_id=image_id,
                                       image_name=image_name,
                                       image_tag=image_tag,
                                       image_tag_alias=image_tag_alias)

        # Push the images to the container registry
        _repo_push = RepositoryPush(name='ingress-controller-registry-push',
                                    repository_args=repo_args,
                                    check_if_id_matches_tag_func=container_registry.check_if_id_matches_tag)
        return _repo_push
    else:
        raise 'Unable to log into container registry'


# Dynamically determine the infrastructure provider and instantiate the
# correlated class, then apply the pulumi async closures.
infra_type = k8s_config.require('infra_type').lower()
module = importlib.import_module(name=f'registries.{infra_type}')
container_registry_class = module.CLASS
repo_push: Output[RepositoryPush] = container_registry_class.instance(stack_name, pulumi_user)\
    .apply(push_to_container_registry)

pulumi.export('container_repo_push', Output.unsecret(repo_push))
