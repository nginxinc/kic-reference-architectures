import os.path
from typing import Optional, Callable, Mapping, List
import yaml

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
        self.root_path = path
        self.description = description
        self.config_keys_with_secrets = config_keys_with_secrets or []
        self.on_success = on_success

    def path(self) -> str:
        relative_path = os.path.sep.join([SCRIPT_DIR, '..', '..', self.root_path])
        return os.path.abspath(relative_path)

    def config(self) -> Mapping[str, str]:
        if not self._config_data:
            config_path = os.path.sep.join([self.path(), 'Pulumi.yaml'])
            with open(config_path, 'r') as f:
                self._config_data = yaml.safe_load(f)

        return self._config_data

    def name(self) -> str:
        config_data = self.config()

        if 'name' not in config_data.keys():
            raise PulumiConfigException('Pulumi configuration did not contain required "name" key')

        return config_data['name']