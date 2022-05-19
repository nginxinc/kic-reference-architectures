import os
from typing import Optional, Mapping
from configparser import ConfigParser

import stack_config_parser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..', '..', '..', 'config', 'pulumi', 'environment']))


class EnvConfigParser(ConfigParser):
    _stack_config: Optional[stack_config_parser.PulumiStackConfig] = None
    config_path: Optional[str] = None

    def __init__(self) -> None:
        super().__init__()
        self.optionxform = lambda option: option

    def stack_name(self) -> str:
        return self.get(section='main', option='PULUMI_STACK')

    def no_color(self) -> bool:
        return 'NO_COLOR' in self.main_section()

    def main_section(self) -> Mapping[str, str]:
        return self['main']


def read(config_file_path: str = DEFAULT_PATH) -> EnvConfigParser:
    config_parser = EnvConfigParser()
    config_parser.optionxform = lambda option: option

    with open(config_file_path, 'r') as f:
        content = f'[main]{os.linesep}{f.read()}'
        config_parser.read_string(content)
        config_parser.config_path = config_file_path

    return config_parser
