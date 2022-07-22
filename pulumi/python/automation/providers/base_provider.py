"""
This file is provides the super class for all infrastructure providers.
"""

import abc
import os
import pathlib
import sys
from typing import List, Mapping, Iterable, TextIO, Union, Dict, Any, Hashable, Optional

from .pulumi_project import PulumiProject, SecretConfigKey

# Directory in which script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class InvalidConfigurationException(Exception):
    key: Optional[str]

    def __init__(self, msg: str, key: Optional[str] = None) -> None:
        super().__init__(msg)
        self.key = key


class Provider:
    """Super class for all infrastructure providers"""
    @staticmethod
    def list_providers() -> Iterable[str]:
        """returns an iterable of the providers available derived from the files in the providers directory
        :return all the usable providers"""
        def is_provider(file: pathlib.Path) -> bool:
            # Filter out the non-provider files
            return file.is_file() and \
                   not file.stem.endswith('base_provider') and \
                   not file.stem.endswith('pulumi_project') and \
                   not file.stem.endswith('update_kubeconfig')

        path = pathlib.Path(SCRIPT_DIR)
        return [os.path.splitext(file.stem)[0] for file in path.iterdir() if is_provider(file)]

    @staticmethod
    def validate_env_config_required_keys(required_keys: List[str], config: Mapping[str, str]):
        """Validates that the required environment variables as defined by file or runtime environment are present"""

        for key in required_keys:
            if key not in config.keys():
                raise InvalidConfigurationException(msg=f'Required configuration key [{key}] not found', key=key)

    @abc.abstractmethod
    def infra_type(self) -> str:
        """
        :return string representing the type of underlying infrastructure used to stand up Kubernetes
        """
        pass

    @abc.abstractmethod
    def infra_execution_order(self) -> List[PulumiProject]:
        """Pulumi infrastructure (not Kubernetes) projects to be executed in sequential order"""
        pass

    def new_stack_config(self, env_config: Mapping[str, str],
                         defaults: Union[Dict[Hashable, Any], list, None]) -> Union[Dict[Hashable, Any], list, None]:
        """Creates a new Pulumi stack configuration"""
        config = {
            'kubernetes:infra_type': self.infra_type()
        }
        return config

    def validate_env_config(self, env_config: Mapping[str, str]):
        """Validates that the passed environment variables are correct"""
        Provider.validate_env_config_required_keys(['PULUMI_STACK'], env_config)

    def validate_stack_config(self,
                              stack_config: Union[Dict[Hashable, Any], list, None],
                              env_config: Mapping[str, str]):
        """Validates that the passed stack configuration is correct"""
        pass

    def k8s_execution_order(self) -> List[PulumiProject]:
        """Pulumi Kubernetes projects to be executed in sequential order"""
        return [
            PulumiProject(path='infrastructure/kubeconfig', description='Kubeconfig'),
            PulumiProject(path='kubernetes/secrets', description='Secrets'),
            PulumiProject(path='utility/kic-image-build', description='KIC Image Build'),
            PulumiProject(path='utility/kic-image-push', description='KIC Image Push'),
            PulumiProject(path='kubernetes/nginx/ingress-controller-namespace',
                          description='K8S Ingress NS'),
            PulumiProject(path='kubernetes/nginx/ingress-controller', description='Ingress Controller'),
            PulumiProject(path='kubernetes/logstore', description='Logstore'),
            PulumiProject(path='kubernetes/logagent', description='Log Agent'),
            PulumiProject(path='kubernetes/certmgr', description='Cert Manager'),
            PulumiProject(path='kubernetes/prometheus', description='Prometheus',
                          config_keys_with_secrets=[SecretConfigKey(key_name='prometheus:adminpass',
                                                                    prompt='Prometheus administrator password')]),
            PulumiProject(path='kubernetes/observability', description='Observability'),
            PulumiProject(path='kubernetes/applications/sirius', description='Bank of Sirius',
                          config_keys_with_secrets=[SecretConfigKey(key_name='sirius:accounts_pwd',
                                                                    prompt='Bank of Sirius Accounts Database password'),
                                                    SecretConfigKey(key_name='sirius:ledger_pwd',
                                                                    prompt='Bank of Sirius Ledger Database password'),
                                                    SecretConfigKey(key_name='sirius:demo_login_user',
                                                                    prompt='Bank of Sirius demo site login username',
                                                                    default='testuser'),
                                                    SecretConfigKey(key_name='sirius:demo_login_pwd',
                                                                    prompt='Bank of Sirius demo site login password',
                                                                    default='password')])
        ]

    def execution_order(self) -> List[PulumiProject]:
        """Full list of Pulumi projects to be executed in sequential order (including both infrastructure and
        Kubernetes"""
        return self.infra_execution_order() + self.k8s_execution_order()

    def display_execution_order(self, output: TextIO = sys.stdout):
        """Writes the execution order of Pulumi projects in a visual tree to an output stream"""
        execution_order = self.execution_order()
        last_prefix = ''

        for index, pulumi_project in enumerate(execution_order):
            path_parts = pulumi_project.path.split(os.path.sep)
            project = f'{path_parts[-1]} [{pulumi_project.description}]'
            prefix = os.path.sep.join(path_parts[:-1])

            # First item in the list
            if last_prefix != prefix and index == 0:
                print(f' ┌── {prefix}', file=output)
                print(f' │   ├── {project}', file=output)
            # Last item in the list with a new prefix
            elif last_prefix != prefix and index == len(execution_order) - 1:
                print(f' └── {prefix}', file=output)
                print(f'     └── {project}', file=output)
            # Any other item with a new prefix
            elif last_prefix != prefix and index != 0:
                print(f' ├── {prefix}', file=output)

                peek = execution_order[index + 1]
                splitted = peek.path.split(f'{prefix}{os.path.sep}')[0]
                # item is not the last item with the prefix
                if os.path.sep not in splitted:
                    print(f' │   ├── {project}', file=output)
                # item is the last item with the prefix
                else:
                    print(f' │   └── {project}', file=output)
            elif last_prefix == prefix:
                print(f' │   ├── {project}', file=output)
            elif last_prefix == prefix and index == len(execution_order) - 1:
                print(f' │   └── {project}', file=output)

            if last_prefix != prefix:
                last_prefix = prefix

    @staticmethod
    def _find_position_of_project_by_path(path: str, k8s_execution_order: List[PulumiProject]) -> int:
        for index, project in enumerate(k8s_execution_order):
            if project.path == path:
                return index
        return -1

    @staticmethod
    def _insert_project(project_path_to_insert_after: str,
                        project: PulumiProject,
                        k8s_execution_order: List[PulumiProject]):
        project_position = Provider._find_position_of_project_by_path(project_path_to_insert_after,
                                                                      k8s_execution_order)

        if project_position < 0:
            raise ValueError(f'Could not find project at path {project_path_to_insert_after}')

        k8s_execution_order.insert(project_position + 1, project)
