"""
File containing the Digital Ocean infrastructure provider for the MARA runner.
"""

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
    """Digital Ocean CLI execution helper class"""
    access_token: str
    region: Optional[str]

    def __init__(self, access_token: str, region: Optional[str] = None):
        self.access_token = access_token
        self.region = region

    def base_cmd(self) -> str:
        """
        :return: returns the base command and any required flags
        """
        cmd = 'doctl'
        cmd += f' --access-token "{self.access_token}" '
        return cmd.strip()

    def validate_credentials_cmd(self) -> str:
        """
        Returns the command that validates if the doctl command can authenticate correctly.
        :return: command to be executed
        """
        return f'{self.base_cmd()} account get'

    def save_kubernetes_cluster_cmd(self, cluster_name: str) -> str:
        """
        Returns the command used to update the kubeconfig with the passed cluster name
        :param cluster_name: name of the cluster to add to the kubeconfig
        :return: command to be executed
        """
        return f'{self.base_cmd()} kubernetes cluster config save {cluster_name}'

    def get_kubernetes_versions_json(self) -> str:
        """
        Returns the command that lists the Kubernetes versions available.
        :return: command to be executed
        """
        return f'{self.base_cmd()} kubernetes options versions --output json'

    def get_kubernetes_regions_json(self) -> str:
        """
        Returns the command that lists the regions available to run Kubernetes.
        :return: command to be executed
        """
        return f'{self.base_cmd()} kubernetes options regions --output json'

    def get_kubernetes_instance_sizes_json(self) -> str:
        """
        Returns the command that lists the instance sizes available for Kubernetes nodes.
        :return: command to be executed
        """
        return f'{self.base_cmd()} kubernetes options sizes --output json'


class DigitalOceanProvider(Provider):
    """Digital Ocean infrastructure provider"""
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
        new_order = original_order.copy()

        # Add container registry credentials project after ingress controller namespace project
        add_credentials_project = PulumiProject(path='infrastructure/digitalocean/container-registry-credentials',
                                                description='Registry Credentials')
        Provider._insert_project(project_path_to_insert_after='kubernetes/nginx/ingress-controller-namespace',
                                 project=add_credentials_project,
                                 k8s_execution_order=new_order)

        # Add DNS record project after ingress controller project
        dns_record_project = PulumiProject(path='infrastructure/digitalocean/dns-record', description='DNS Record')
        Provider._insert_project(project_path_to_insert_after='kubernetes/nginx/ingress-controller',
                                 project=dns_record_project,
                                 k8s_execution_order=new_order)

        return new_order

    def new_stack_config(self, env_config, defaults: Union[Dict[Hashable, Any], list, None]) -> \
            Union[Dict[Hashable, Any], list, None]:
        config = super().new_stack_config(env_config, defaults)

        if 'DIGITALOCEAN_TOKEN' not in env_config:
            config['digitalocean:token'] = input("Digital Ocean API token (this is stored in plain-text - "
                                                 "alternatively this can be specified as the environment variable "
                                                 "DIGITALOCEAN_TOKEN): ")

        token = DigitalOceanProvider.token(stack_config={'config': config}, env_config=env_config)
        do_cli = DoctlCli(access_token=token)

        # FQDN
        config['kic-helm:fqdn'] = input(f'Fully qualified domain name (FQDN) for application: ')

        # Kubernetes versions
        k8s_versions_json_str, _ = external_process.run(do_cli.get_kubernetes_versions_json())
        k8s_versions_json = json.loads(k8s_versions_json_str)
        k8s_version_slugs = [version['slug'] for version in k8s_versions_json]

        print('Supported Kubernetes versions:')
        for slug in k8s_version_slugs:
            print(f'  {slug}')
        default_version = defaults['digitalocean:k8s_version'] or k8s_version_slugs[0]
        config['digitalocean:k8s_version'] = input(f'Kubernetes version [{default_version}]: ').strip() or default_version
        print(f"Kubernetes version: {config['digitalocean:k8s_version']}")

        # Kubernetes regions
        k8s_regions_json_str, _ = external_process.run(do_cli.get_kubernetes_regions_json())
        k8s_regions_json = json.loads(k8s_regions_json_str)
        default_region = defaults['digitalocean:region'] or k8s_regions_json[-1]['slug']

        print('Supported Regions:')
        for item in k8s_regions_json:
            print(f"  {item['name']}: {item['slug']}")
        config['digitalocean:region'] = input(f'Region [{default_region}]: ').strip() or default_region
        print(f"Region: {config['digitalocean:region']}")

        # Kubernetes instance size
        k8s_sizes_json_str, _ = external_process.run(do_cli.get_kubernetes_instance_sizes_json())
        k8s_sizes_json = json.loads(k8s_sizes_json_str)
        k8s_sizes_slugs = [size['slug'] for size in k8s_sizes_json]
        default_size = defaults['digitalocean:instance_size'] or 's-2vcpu-4gb'

        print('Supported Instance Sizes:')
        for slug in k8s_sizes_slugs:
            print(f'  {slug}')

        config['digitalocean:instance_size'] = input(f'Instance size [{default_size}]: ').strip() or default_size
        print(f"Instance size: {config['digitalocean:instance_size']}")

        # Kubernetes instance count
        default_node_count = defaults['digitalocean:node_count'] or 3
        while 'digitalocean:node_count' not in config:
            node_count = input('Node count for Kubernetes cluster '
                               f'[{default_node_count}]: ').strip() or default_node_count
            if type(node_count) == int or node_count.isdigit():
                config['digitalocean:node_count'] = int(node_count)
        print(f"Node count: {config['digitalocean:node_count']}")

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
        """Looks into multiple configuration sources for a valid Digital Ocean authentication token.
        :param stack_config: reference to stack configuration
        :param env_config: reference to environment configuration
        :return: authentication token
        """
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
