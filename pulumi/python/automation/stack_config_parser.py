import json
import os
from typing import Optional, MutableMapping

from pulumi.automation import ConfigValue

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR_PATH = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..', '..', '..', 'config', 'pulumi']))


class PulumiStackConfig(dict):
    config_path: Optional[str] = None

    def to_pulumi_config_value(self) -> MutableMapping[str, ConfigValue]:
        if 'config' not in self:
            return {}

        config = self.get('config')

        pulumi_config = {}
        for key, val in config.items():
            if type(val) in [str, int, float]:
                pulumi_config[key] = ConfigValue(value=val)
            elif type(val) is dict and 'secure' in val:
                pulumi_config[key] = ConfigValue(value=val['secure'], secret=True)
            else:
                json_val = json.dumps(val)
                pulumi_config[key] = ConfigValue(value=json_val)

        return pulumi_config


def _stack_config_path(stack_name: str) -> str:
    return os.path.sep.join([DEFAULT_DIR_PATH, f'Pulumi.{stack_name}.yaml'])


def _read(config_file_path: str) -> PulumiStackConfig:
    with open(config_file_path, 'r') as f:
        stack_config = PulumiStackConfig()
        stack_config.config_path = config_file_path
        stack_config.update(yaml.safe_load(f))
        return stack_config


def read(stack_name: str) -> PulumiStackConfig:
    stack_config_path = _stack_config_path(stack_name)
    return _read(stack_config_path)
