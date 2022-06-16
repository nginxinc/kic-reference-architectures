import base64
import urllib
from urllib import parse
from typing import Optional, List

import pulumi.log
from pulumi import Input, Output
import pulumi_docker as docker

from kic_util import external_process


class RegistryCredentials:
    username: Input[str]
    password: Input[str]

    def __init__(self,
                 username: Input[str],
                 password: Input[str]):
        self.username = username
        self.password = password


class ContainerRegistry:
    stack_name: str
    pulumi_user: str
    credentials: Optional[RegistryCredentials]
    registry_url: str

    def __init__(self,
                 stack_name: str,
                 pulumi_user: str,
                 registry_url: str,
                 credentials: Optional[RegistryCredentials]) -> None:
        super().__init__()
        self.stack_name = stack_name
        self.pulumi_user = pulumi_user
        self.registry_url = registry_url
        self.credentials = credentials

    def format_registry_url_for_docker_login(self):
        # We assume that the scheme is https because that's what is used most everywhere
        registry_host_url = urllib.parse.urlparse(f'https://{self.registry_url}')
        # We strip out the path from the URL because it isn't used when logging into a repository
        return f'{registry_host_url.scheme}://{registry_host_url.hostname}'

    def login_to_registry(self) -> Optional[docker.LoginResult]:
        registry = docker.Registry(registry=self.format_registry_url_for_docker_login(),
                                   username=self.credentials.username,
                                   password=self.credentials.password)

        docker.login_to_registry(registry=registry, log_resource=None)
        pulumi.log.info(f'Logged into container registry: {registry.registry}')

        if not docker.login_results:
            return None
        if docker.login_results[0]:
            return docker.login_results[0]

    def logout_of_registry(self):
        docker_cmd = f'docker logout {self.format_registry_url_for_docker_login()}'
        res, _ = external_process.run(cmd=docker_cmd)
        pulumi.log.info(res)

    def check_if_id_matches_tag(self, image_tag: str, new_image_id: str) -> bool:
        return False

    def registry_implementation_name(self) -> str:
        raise NotImplemented

    @classmethod
    def instance(cls, stack_name: str, pulumi_user: str):
        pass

    @staticmethod
    def decode_credentials(encoded_token: str) -> RegistryCredentials:
        decoded = str(base64.b64decode(encoded_token), 'utf-8')
        parts = decoded.split(':', 2)
        if len(parts) != 2:
            raise ValueError("Unexpected format for decoded ECR authorization token")
        username = parts[0]
        password = parts[1]
        return RegistryCredentials(username=username, password=password)
