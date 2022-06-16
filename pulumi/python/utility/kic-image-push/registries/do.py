import json
import os
from typing import List, Any
from pulumi import Output, StackReference, ResourceOptions, log
from pulumi_digitalocean import ContainerRegistry as DoContainerRegistry, ContainerRegistryDockerCredentials

from kic_util import pulumi_config
from registries.base_registry import ContainerRegistry, RegistryCredentials


class DigitalOceanContainerRegistry(ContainerRegistry):
    @classmethod
    def instance(cls, stack_name: str, pulumi_user: str) -> Output[ContainerRegistry]:
        super().instance(stack_name, pulumi_user)
        # Pull properties from the Pulumi project that defines the Digital Ocean repository
        container_registry_project_name = DigitalOceanContainerRegistry.do_project_name_from_project_dir(
            'container-registry')
        container_registry_stack_ref_id = f"{pulumi_user}/{container_registry_project_name}/{stack_name}"
        stack_ref = StackReference(container_registry_stack_ref_id)
        container_registry_output = stack_ref.require_output('container_registry')
        registry_name_output = stack_ref.require_output('container_registry_name')

        def _docker_credentials() -> Output[str]:
            one_hour = 3_600 * 4
            registry_credentials = ContainerRegistryDockerCredentials(resource_name='do_docker_credentials',
                                                                      registry_name=registry_name_output,
                                                                      expiry_seconds=one_hour,
                                                                      write=True,
                                                                      opts=ResourceOptions(delete_before_replace=True))
            return registry_credentials.docker_credentials

        def _make_instance(params: List[Any]) -> DigitalOceanContainerRegistry:
            container_registry = params[0]
            do_docker_creds = params[1]
            server_url = container_registry['server_url']
            endpoint = container_registry['endpoint']
            registry_url = f'{endpoint}/nginx-ingress'
            _credentials = DigitalOceanContainerRegistry._decode_docker_credentials(server_url, do_docker_creds)

            return cls(stack_name=stack_name, pulumi_user=pulumi_user,
                       registry_url=registry_url, credentials=_credentials)

        return Output.all(container_registry_output, _docker_credentials()).apply(_make_instance)

    def registry_implementation_name(self) -> str:
        return 'Digital Ocean Container Registry'

    @staticmethod
    def do_project_name_from_project_dir(dirname: str):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', 'digitalocean', dirname)
        return pulumi_config.get_pulumi_project_name(project_path)

    @staticmethod
    def _decode_docker_credentials(server_url: str,
                                   docker_credentials_json: str) -> RegistryCredentials:
        credential_json = json.loads(docker_credentials_json)
        auths_json = credential_json['auths']
        return ContainerRegistry.decode_credentials(auths_json[server_url]['auth'])


CLASS = DigitalOceanContainerRegistry
