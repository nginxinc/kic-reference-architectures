"""
This file contains classes related to modeling Pulumi projects as discrete directories that
are invoked individually in sequence by the Pulumi Automation API.
"""

import os.path
from typing import Optional, Callable, Mapping, List, MutableMapping
import yaml
from pulumi import automation as auto

# Directory in which script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class PulumiConfigException(Exception):
    """Generic exception thrown when Pulumi configuration errors are encountered"""
    pass


class SecretConfigKey:
    """
    Class representing a secret that the user will be prompted to enter and subsequently stored in the Pulumi
    secrets store.
    """
    key_name: str
    prompt: str
    default: Optional[str]

    def __init__(self, key_name: str, prompt: str, default: Optional[str] = None) -> None:
        super().__init__()
        self.key_name = key_name
        self.prompt = prompt
        self.default = default


class PulumiProject:
    """
    Class representing a Pulumi project that is associated with a directory and containing properties regarding the
    secrets used, description and the operation to run when it is successfully stood up.
    """
    path: str
    description: str
    config_keys_with_secrets: List[SecretConfigKey]
    on_success: Optional[Callable] = None
    _config_data: Optional[Mapping[str, str]] = None

    def __init__(self,
                 path: str,
                 description: str,
                 config_keys_with_secrets: Optional[List[SecretConfigKey]] = None,
                 on_success: Optional[Callable] = None) -> None:
        super().__init__()
        self.path = path
        self.description = description
        self.config_keys_with_secrets = config_keys_with_secrets or []
        self.on_success = on_success

    def abspath(self) -> str:
        relative_path = os.path.sep.join([SCRIPT_DIR, '..', '..', self.path])
        return os.path.abspath(relative_path)

    def config(self) -> Mapping[str, str]:
        if not self._config_data:
            config_path = os.path.sep.join([self.abspath(), 'Pulumi.yaml'])
            with open(config_path, 'r') as f:
                self._config_data = yaml.safe_load(f)

        return self._config_data

    def name(self) -> str:
        config_data = self.config()

        if 'name' not in config_data.keys():
            raise PulumiConfigException('Pulumi configuration did not contain required "name" key')

        return config_data['name']


class PulumiProjectEventParams:
    """Object containing the state passed to an on_success event after the successful stand up of a Pulumi project."""
    stack_outputs: MutableMapping[str, auto._output.OutputValue]
    config: MutableMapping[str, auto._config.ConfigValue]
    env_config: Mapping[str, str]

    def __init__(self,
                 stack_outputs: MutableMapping[str, auto._output.OutputValue],
                 config: MutableMapping[str, auto._config.ConfigValue],
                 env_config: Mapping[str, str]) -> None:
        self.stack_outputs = stack_outputs
        self.config = config
        self.env_config = env_config
