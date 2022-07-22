import json
import os
from typing import List, Any
from pulumi import Output, StackReference, ResourceOptions, log

from kic_util import pulumi_config
from registries.base_registry import ContainerRegistry, RegistryCredentials


class LinodeHarborRegistry(ContainerRegistry):
    @classmethod
    def instance(cls, stack_name: str, pulumi_user: str) -> Output[ContainerRegistry]:
        super().instance(stack_name, pulumi_user)
        # Pull properties from the Pulumi project that defines the Linode Harbor repository
        container_registry_project_name = LinodeHarborRegistry.project_name_from_linode_dir('harbor')
        container_registry_stack_ref_id = f"{pulumi_user}/{container_registry_project_name}/{stack_name}"
        stack_ref = StackReference(container_registry_stack_ref_id)
        harbor_hostname_output = stack_ref.require_output('harbor_hostname')
        harbor_user_output = stack_ref.require_output('harbor_user')
        harbor_password_output = stack_ref.require_output('harbor_password')

        def _make_instance(params: List[Any]) -> LinodeHarborRegistry:
            hostname = params[0]
            username = params[1]
            password = params[2]

            registry_url = f'{hostname}/library/ingress-controller'
            credentials = RegistryCredentials(username=username, password=password)

            return cls(stack_name=stack_name, pulumi_user=pulumi_user, registry_url=registry_url, credentials=credentials)

        return Output.all(harbor_hostname_output, harbor_user_output, harbor_password_output).apply(_make_instance)

    @staticmethod
    def project_name_from_linode_dir(dirname: str):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', 'linode', dirname)
        return pulumi_config.get_pulumi_project_name(project_path)

    def registry_implementation_name(self) -> str:
        return 'Harbor'


CLASS = LinodeHarborRegistry
