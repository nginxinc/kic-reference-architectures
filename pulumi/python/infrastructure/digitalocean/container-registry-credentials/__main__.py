import os

import pulumi
from pulumi import StackReference
from pulumi_digitalocean import ContainerRegistryDockerCredentials
from kic_util import pulumi_config
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Secret, SecretInitArgs


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()
script_dir = os.path.dirname(os.path.abspath(__file__))


def project_name_from_same_parent(directory: str):
    project_path = os.path.join(script_dir, '..', directory)
    return pulumi_config.get_pulumi_project_name(project_path)


def project_name_of_namespace_project():
    project_path = os.path.join(script_dir, '..', '..', '..', 'kubernetes', 'nginx', 'ingress-controller-namespace')
    return pulumi_config.get_pulumi_project_name(project_path)


k8_project_name = project_name_from_same_parent('domk8s')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

container_registry_stack_ref_id = f"{pulumi_user}/{project_name_from_same_parent('container-registry')}/{stack_name}"
cr_stack_ref = StackReference(container_registry_stack_ref_id)
container_registry_output = cr_stack_ref.require_output('container_registry')
registry_name_output = cr_stack_ref.require_output('container_registry_name')

namespace_stack_ref_id = f"{pulumi_user}/{project_name_of_namespace_project()}/{stack_name}"
ns_stack_ref = StackReference(namespace_stack_ref_id)
namespace_name_output = ns_stack_ref.require_output('ingress_namespace_name')

fifty_years_in_seconds = 1_576_800_000
registry_credentials = ContainerRegistryDockerCredentials(resource_name='do_k8s_docker_credentials',
                                                          expiry_seconds=fifty_years_in_seconds,
                                                          registry_name=registry_name_output,
                                                          write=False)
docker_credentials = registry_credentials.docker_credentials

k8s_provider = k8s.Provider(resource_name='kubernetes', kubeconfig=kubeconfig)

secret = Secret(resource_name='ingress-controller-registry-secret',
                args=SecretInitArgs(string_data={'.dockerconfigjson': docker_credentials},
                                    type='kubernetes.io/dockerconfigjson',
                                    metadata={'namespace': namespace_name_output,
                                              'name': 'ingress-controller-registry'}),
                opts=pulumi.ResourceOptions(provider=k8s_provider))

pulumi.export('ingress-controller-registry-secret', secret)
