import os

import requests
from typing import List, Any

from pulumi import Output, StackReference, log
from pulumi_aws import ecr
from kic_util import pulumi_config
from registries.base_registry import ContainerRegistry, RegistryCredentials


class ElasticContainerRegistry(ContainerRegistry):
    @classmethod
    def instance(cls, stack_name: str, pulumi_user: str) -> Output[ContainerRegistry]:
        super().instance(stack_name, pulumi_user)
        ecr_project_name = ElasticContainerRegistry.aws_project_name_from_project_dir('ecr')
        ecr_stack_ref_id = f"{pulumi_user}/{ecr_project_name}/{stack_name}"
        stack_ref = StackReference(ecr_stack_ref_id)
        # Async query for credentials from stack reference
        ecr_registry_id = stack_ref.require_output('registry_id')
        credentials_output = ecr_registry_id.apply(ElasticContainerRegistry.get_ecr_credentials)
        # Async query for registry url from stack reference
        registry_url_output = stack_ref.require_output('registry_url')

        def _make_instance(params: List[Any]) -> ElasticContainerRegistry:
            return cls(stack_name=stack_name, pulumi_user=pulumi_user, registry_url=params[0], credentials=params[1])

        return Output.all(registry_url_output, credentials_output).apply(_make_instance)

    @staticmethod
    def aws_project_name_from_project_dir(dirname: str):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', 'aws', dirname)
        return pulumi_config.get_pulumi_project_name(project_path)

    @staticmethod
    def get_ecr_credentials(registry_id: str) -> RegistryCredentials:
        credentials = ecr.get_credentials(registry_id)
        token = credentials.authorization_token
        return ContainerRegistry.decode_credentials(token)

    def _ecr_docker_api_url(self, ) -> str:
        registry_url_parts = self.registry_url.split('/')
        ecr_host = registry_url_parts[0]
        ecr_path = registry_url_parts[1]
        return f'https://{ecr_host}/v2/{ecr_path}'

    def check_if_id_matches_tag(self, image_tag: str, new_image_id: str) -> bool:
        docker_api_url = self._ecr_docker_api_url()
        auth_tuple = (self.credentials.username, self.credentials.password)

        log.debug(f'Querying for latest image id: {docker_api_url}/manifests/{image_tag}')
        with requests.get(f'{docker_api_url}/manifests/{image_tag}', auth=auth_tuple) as response:
            if response.status_code != 200:
                log.warn(f'Unable to query ECR directly for image id')
                return False
            json_response = response.json()
            if 'config' in json_response and 'digest' in json_response['config']:
                remote_image_id = json_response['config']['digest']
                return remote_image_id != new_image_id
            else:
                return True


CLASS = ElasticContainerRegistry
