import json
import sys
from typing import List, Dict, Hashable, Any, Union, MutableMapping, Optional, Mapping

import yaml
from pulumi import automation as auto
from kic_util import external_process

from .base_provider import PulumiProject, Provider, InvalidConfigurationException
from .pulumi_project import PulumiProjectEventParams


class DigitalOceanProviderException(Exception):
    pass


class DoctlCli:
    access_token: str
    region: Optional[str]

    def __init__(self, access_token: str, region: Optional[str] = None):
        self.access_token = access_token
        self.region = region

    def base_cmd(self) -> str:
        cmd = 'doctl'
        cmd += f' --access-token "{self.access_token}" '
        return cmd.strip()

    def validate_credentials_cmd(self) -> str:
        return f'{self.base_cmd()} account get'

    def save_kubernetes_cluster_cmd(self, cluster_name: str) -> str:
        return f'{self.base_cmd()} kubernetes cluster config save {cluster_name}'

    def get_kubernetes_versions_json(self) -> str:
        return f'{self.base_cmd()} kubernetes options versions --output json'


class DigitalOceanProvider(Provider):
    def infra_type(self) -> str:
        return 'DO'

    def infra_execution_order(self) -> List[PulumiProject]:
        return [
            PulumiProject(path='infrastructure/digitalocean/container-registry', description='DO Container Registry'),
            PulumiProject(path='infrastructure/digitalocean/domk8s', description='DO Kubernetes',
                          on_success=DigitalOceanProvider._update_kubeconfig),
        ]

    def k8s_execution_order(self) -> List[PulumiProject]:
        # The default Kubernetes Pulumi project instantiation order must be modified because
        # the Digital Ocean Container Registry login credentials *must* be added under the
        # Ingress Controller's namespace. As such, we insert a Digital Ocean specific
        # Pulumi project that gets the credentials and adds them to the Kubernete's cluster
        # under the appropriate namespace.
        original_order = super().k8s_execution_order()

        def find_position_of_project_by_path(path: str) -> int:
            for index, project in enumerate(original_order):
                if project.path == path:
                    return index
            return -1

        namespace_project_path = 'kubernetes/nginx/ingress-controller-namespace'
        namespace_project_position = find_position_of_project_by_path(namespace_project_path)

        if namespace_project_position < 0:
            raise ValueError('Could not find project that creates the nginx-ingress namespace at '
                             f'path {namespace_project_path}')

        add_credentials_project = PulumiProject(path='infrastructure/digitalocean/add-container-registry-credentials',
                                                description='Registry Credentials')
        new_order = original_order.copy()
        new_order.insert(namespace_project_position + 1, add_credentials_project)

        return new_order

    def new_stack_config(self, env_config, defaults: Union[Dict[Hashable, Any], list, None]) -> \
            Union[Dict[Hashable, Any], list, None]:
        config = super().new_stack_config(env_config, defaults)

        if 'DIGITALOCEAN_TOKEN' not in env_config:
            config['digitalocean:token'] = input("Digital Ocean API token (this is stored in plain-text - "
                                                 "alternatively this can be specified as the environment variable "
                                                 "DIGITALOCEAN_TOKEN): ")

        config['kic-helm:fqdn'] = input(f'Fully qualified domain name (FQDN) for application: ')

        return config

    def validate_stack_config(self,
                              stack_config: Union[Dict[Hashable, Any], list, None],
                              env_config: Mapping[str, str]):
        super().validate_stack_config(stack_config=stack_config, env_config=env_config)
        token = DigitalOceanProvider.token(stack_config=stack_config, env_config=env_config)
        do_cli = DoctlCli(access_token=token)
        _, err = external_process.run(cmd=do_cli.validate_credentials_cmd())
        if err:
            print(f'Digital Ocean authentication error: {err}', file=sys.stderr)
            sys.exit(3)

    @staticmethod
    def _update_kubeconfig(params: PulumiProjectEventParams):
        if 'cluster_name' not in params.stack_outputs:
            raise DigitalOceanProviderException('Cannot find key [cluster_name] in stack output')

        kubeconfig = yaml.safe_load(params.stack_outputs['kubeconfig'].value)
        full_cluster_name = kubeconfig['clusters'][0]['name']

        res, _ = external_process.run('kubectl config get-clusters')
        clusters = filter(lambda cluster: cluster != 'NAME', res.splitlines())

        if full_cluster_name in clusters:
            print(f'Local kubectl configuration already has credentials for cluster {full_cluster_name}')
        else:
            print(f'Adding credentials for cluster {full_cluster_name} to local kubectl configuration')
            cluster_name = params.stack_outputs['cluster_name'].value
            token = DigitalOceanProvider.token(stack_config=params.config, env_config=params.env_config)
            do_cli = DoctlCli(access_token=token)

            res, _ = external_process.run(do_cli.save_kubernetes_cluster_cmd(cluster_name))
            if res:
                print(res)

    @staticmethod
    def token(stack_config: Union[Mapping[str, Any], MutableMapping[str, auto._config.ConfigValue]],
              env_config: Mapping[str, str]) -> str:
        # Token is in an environment variable or the environment variable file
        if 'DIGITALOCEAN_TOKEN' in env_config:
            return env_config['DIGITALOCEAN_TOKEN']

        # We were given a reference to a StackConfigParser object
        if 'config' in stack_config and 'digitalocean:token' in stack_config['config']:
            return stack_config['config']['digitalocean:token']

        # We were given a reference to a Pulumi Stack configuration
        if 'digitalocean:token' in stack_config:
            return stack_config['digitalocean:token'].value

        # Otherwise
        msg = 'When using the Digital Ocean provider, an API token must be specified - ' \
              'this token can be specified with the Pulumi config parameter digitalocean:token ' \
              'or the environment variable DIGITALOCEAN_TOKEN'
        raise InvalidConfigurationException(msg)


INSTANCE = DigitalOceanProvider()
