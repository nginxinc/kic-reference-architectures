import base64
from typing import List, Union, Dict, Hashable, Any, Mapping, MutableMapping

import yaml
from pulumi import automation as auto

from kic_util import external_process

from .base_provider import PulumiProject, Provider, InvalidConfigurationException
from .pulumi_project import PulumiProjectEventParams, SecretConfigKey

from .update_kubeconfig import update_kubeconfig


class LinodeProviderException(Exception):
    pass


class LinodeCli:
    def base_cmd(self) -> str:
        return 'linode-cli'

    def get_regions(self) -> str:
        return f'{self.base_cmd()} regions list --suppress-warnings'

    def get_k8s_versions(self) -> str:
        return f'{self.base_cmd()} lke versions-list --suppress-warnings'

    def get_instance_sizes(self) -> str:
        return f'{self.base_cmd()} linodes types --suppress-warnings'


class LinodeProvider(Provider):
    def infra_type(self) -> str:
        return 'LKE'

    def infra_execution_order(self) -> List[PulumiProject]:
        return [
            PulumiProject(path='infrastructure/linode/lke', description='LKE',
                          on_success=LinodeProvider._update_kubeconfig),
        ]

    def k8s_execution_order(self) -> List[PulumiProject]:
        original_order = super().k8s_execution_order()
        new_order = original_order.copy()

        harbor_secrets = [SecretConfigKey(key_name='linode:harbor_password',
                                          prompt='Harbor administrator password'),
                          SecretConfigKey(key_name='linode:harbor_db_password',
                                          prompt='Harbor database password'),
                          SecretConfigKey(key_name='linode:harbor_sudo_user_password',
                                          prompt='Harbor instance sudo user password')]
        harbor_project = PulumiProject(path='infrastructure/linode/harbor',
                                       description='Harbor',
                                       config_keys_with_secrets=harbor_secrets)

        Provider._insert_project(project_path_to_insert_after='kubernetes/secrets',
                                 project=harbor_project,
                                 k8s_execution_order=new_order)

        # Add container registry credentials project after ingress controller namespace project
        # Harbor is configured some time after it is stood up in order to give it time to
        # instantiate.
        add_credentials_project = PulumiProject(path='infrastructure/linode/container-registry-credentials',
                                                description='Registry Credentials')
        Provider._insert_project(project_path_to_insert_after='kubernetes/nginx/ingress-controller-namespace',
                                 project=add_credentials_project,
                                 k8s_execution_order=new_order)

        # Add project that configures Harbor for use in the cluster
        harbor_config_project = PulumiProject(path='infrastructure/linode/harbor-configuration',
                                              description='Harbor Config')
        Provider._insert_project(project_path_to_insert_after='utility/kic-image-build',
                                 project=harbor_config_project,
                                 k8s_execution_order=new_order)

        return new_order

    def new_stack_config(self, env_config, defaults: Union[Dict[Hashable, Any], list, None]) -> \
            Union[Dict[Hashable, Any], list, None]:
        config = super().new_stack_config(env_config, defaults)

        if 'LINODE_TOKEN' not in env_config:
            config['linode:token'] = input('Linode API token (this is stored in plain-text - '
                                           'alternatively this can be specified as the environment variable '
                                           'LINODE_TOKEN): ')

        token = LinodeProvider.token(stack_config={'config': config}, env_config=env_config)
        linode_cli = LinodeCli()

        cli_env = {}
        cli_env.update(env_config)
        cli_env['LINODE_CLI_TOKEN'] = token

        # FQDN
        config['kic-helm:fqdn'] = input(f'Fully qualified domain name (FQDN) for application: ')
        print(f"FQDN: {config['kic-helm:fqdn']}")

        # SOA Email
        config['linode:soa_email'] = input(f'DNS Start of Authority (SOA) email address for container registry domain: ').strip()
        print(f"SOA email address: {config['linode:soa_email']}")

        # Kubernetes versions
        k8s_version_list, _ = external_process.run(cmd=linode_cli.get_k8s_versions(),
                                                   env=cli_env)
        print(f'Supported Kubernetes versions:\n{k8s_version_list}')
        default_version = defaults['linode:k8s_version'] or '1.22'
        config['linode:k8s_version'] = input(f'Kubernetes version [{default_version}]: ').strip() or default_version
        print(f"Kubernetes version: {config['linode:k8s_version']}")

        # Region
        regions_list, _ = external_process.run(cmd=linode_cli.get_regions(),
                                               env=cli_env)
        print(f'Supported regions:\n{regions_list}')
        default_region = defaults['linode:region'] or 'us-central'
        config['linode:region'] = input(f'Region [{default_region}]: ').strip() or default_region
        print(f"Region: {config['linode:region']}")

        # Instance Type
        instance_type_list, _ = external_process.run(cmd=linode_cli.get_instance_sizes(),
                                                     env=cli_env)
        print(f'Supported instance types:\n{instance_type_list}')
        default_type = defaults['linode:instance_type'] or 'g6-standard-8'
        config['linode:instance_type'] = input(f'Instance type [{default_type}]: ').strip() or default_type
        print(f"Instance type: {config['linode:instance_type']}")

        # Node Count
        default_node_count = defaults['linode:node_count'] or 3
        while 'linode:node_count' not in config:
            node_count = input('Node count for Kubernetes cluster '
                               f'[{default_node_count}]: ').strip() or default_node_count
            if type(node_count) == int or node_count.isdigit():
                config['linode:node_count'] = int(node_count)
        print(f"Node count: {config['linode:node_count']}")

        # HA Enabled
        k8s_ha_input = input('Enable Kubernetes HA mode [Y]: ').strip().lower()
        k8s_ha = k8s_ha_input in ['', 'y', 'yes', 't', 'true', '1']
        config['linode:k8s_ha'] = k8s_ha
        print(f'HA mode enabled: {k8s_ha}')

        return config

    @staticmethod
    def token(stack_config: Union[Mapping[str, Any], MutableMapping[str, auto._config.ConfigValue]],
              env_config: Mapping[str, str]) -> str:
        # Token is in an environment variable or the environment variable file
        if 'LINODE_TOKEN' in env_config:
            return env_config['LINODE_TOKEN']

        # We were given a reference to a StackConfigParser object
        if 'config' in stack_config and 'linode:token' in stack_config['config']:
            return stack_config['config']['linode:token']

        # We were given a reference to a Pulumi Stack configuration
        if 'linode:token' in stack_config:
            return stack_config['linode:token'].value

        # Otherwise
        msg = 'When using the Linode provider, an API token must be specified - ' \
              'this token can be specified with the Pulumi config parameter linode:token ' \
              'or the environment variable LINODE_TOKEN'
        raise InvalidConfigurationException(msg)

    @staticmethod
    def _update_kubeconfig(params: PulumiProjectEventParams):
        if 'cluster_name' not in params.stack_outputs:
            raise LinodeProviderException('Cannot find key [cluster_name] in stack output')

        cluster_name = params.stack_outputs['cluster_name'].value
        kubeconfig_encoded = params.stack_outputs['kubeconfig'].value
        kubeconfig_bytes = base64.b64decode(kubeconfig_encoded)
        kubeconfig = yaml.safe_load(kubeconfig_bytes)

        update_kubeconfig(env=params.env_config, cluser_name=cluster_name, kubeconfig=kubeconfig)


INSTANCE = LinodeProvider()
