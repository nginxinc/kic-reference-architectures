import os
from typing import Optional, Mapping
from configparser import ConfigParser

import stack_config_parser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..', '..', '..', 'config', 'pulumi', 'environment']))

DEFAULT_ENV_VARS = {
    'PULUMI_SKIP_UPDATE_CHECK': 'true'
}


class EnvConfig(dict):
    _stack_config: Optional[stack_config_parser.PulumiStackConfig] = None
    config_path: Optional[str] = None

    def __init__(self,
                 env_vars: Mapping[str, str],
                 file_vars: Mapping[str, str],
                 stack_config: Optional[stack_config_parser.PulumiStackConfig] = None,
                 config_path: Optional[str] = None) -> None:
        super().__init__()
        self.update(DEFAULT_ENV_VARS)
        self.update(env_vars)
        self.update(file_vars)
        self._stack_config = stack_config
        self.config_path = config_path

    def stack_name(self) -> str:
        return self.get('PULUMI_STACK')

    def no_color(self) -> bool:
        return self.get('NO_COLOR') is not None

    def pulumi_color_settings(self):
        if self.no_color():
            return 'never'
        else:
            return 'auto'


def read(config_file_path: str = DEFAULT_PATH) -> EnvConfig:
    config_parser = ConfigParser()
    config_parser.optionxform = lambda option: option

    with open(config_file_path, 'r') as f:
        content = f'[main]{os.linesep}{f.read()}'
        config_parser.read_string(content)

    return EnvConfig(env_vars=os.environ, file_vars=config_parser['main'], config_path=config_file_path)
